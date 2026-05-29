import logging
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState
from app.config import settings
from app.context_compact import ContextCompactor

logger = logging.getLogger(__name__)


def _ensure_tool_call_consistency(messages: list) -> list:
    """Ensure every AIMessage with tool_calls has matching ToolMessages following it.

    If an AIMessage has tool_calls but not all corresponding ToolMessages are present,
    remove that AIMessage and any preceding orphan ToolMessages.
    """
    if not messages:
        return messages

    result = list(messages)
    i = 0
    while i < len(result):
        msg = result[i]
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            tool_call_ids = {tc.get("id") for tc in msg.tool_calls}
            # Find corresponding ToolMessages immediately after
            j = i + 1
            found_ids = set()
            while j < len(result) and isinstance(result[j], ToolMessage):
                if result[j].tool_call_id in tool_call_ids:
                    found_ids.add(result[j].tool_call_id)
                j += 1
            # If some tool_call_ids are missing responses, remove this AIMessage
            if tool_call_ids - found_ids:
                logger.warning(
                    "Removing AIMessage at index %d with incomplete tool responses: "
                    "expected %s, found %s",
                    i, tool_call_ids, found_ids,
                )
                result.pop(i)
                continue
        i += 1

    # Remove orphan ToolMessages (no preceding AIMessage with matching tool_call_id)
    ai_tool_call_ids = set()
    for msg in result:
        if isinstance(msg, AIMessage):
            for tc in getattr(msg, "tool_calls", []) or []:
                ai_tool_call_ids.add(tc.get("id"))
    result = [
        msg for msg in result
        if not (isinstance(msg, ToolMessage) and msg.tool_call_id not in ai_tool_call_ids)
    ]

    return result

MEMORY_GUIDANCE = """
何时保存记忆（saveMemory）：
- 用户表达偏好（"我喜欢用 tabs"、"总是用 pytest"） -> type: user
- 用户纠正你（"不要这么做"、"那错了因为..."） -> type: feedback
- 你学到无法从代码直接推断的项目约定（合规要求、遗留模块不可碰等） -> type: project
- 你了解到外部资源地址（看板、监控、文档 URL） -> type: reference
- 不要保存：代码结构、临时状态、密钥凭证
"""

TASK_GUIDANCE = """
何时使用任务（task_create/task_update/task_list/task_get）：
- 当用户要求完成复杂多步骤工作时，先用 task_create 将工作拆分为可追踪的任务图
- 任务有依赖关系（blockedBy / blocks），完成一个任务会自动解除对后续任务的阻塞
- task_update 可将任务状态设为 pending、in_progress、completed、deleted
- 在每次行动前用 task_list 检查当前任务状态，确保按依赖顺序推进
"""

THINK_PROMPT_TEMPLATE = """你是智能体的「决策模块」。请根据对话上下文，决定下一步动作。

【决策规则】
1. 如果用户要求编写代码、完成复杂任务、或需要多步骤执行 → 调用 delegate_task 委派给子智能体完成。多个子任务可以在同一次回复中同时调用多个 delegate_task，它们会并行执行。
2. 如果知识库列表不为空，优先使用 knowledge_query 搜索知识库获取相关专业内容。通用编程、数学、算法问题不需要搜索知识库。
3. 必须先给出完整的回答/结果，再考虑结束对话。禁止在未回答用户的情况下直接调用 terminate。
4. terminate 工具仅用于用户明确说"结束"/"再见"/"不聊了"时。

{memory_section}

【额外信息】
- 你的 Agent ID：{agent_id}
- 知识库列表：{kb_list}
- 可用技能列表：
  {skill_catalog}

{task_guidance}

{memory_guidance}"""


async def think_node(state: AgentState, config: RunnableConfig) -> dict:
    """Think node: call LLM with conversation history + think prompt + tools."""
    chat_model = config["configurable"]["chat_model"]
    tools = config["configurable"]["tools"]
    agent_id = config["configurable"]["agent_id"]
    kb_list = config["configurable"].get("kb_list", "[]")
    skill_catalog = config["configurable"].get("skill_catalog", "(无可用技能)")

    # Inject memory section if available
    memory_manager = config["configurable"].get("memory_manager")
    memory_section = ""
    if memory_manager:
        mem_prompt = memory_manager.load_memory_prompt()
        if mem_prompt:
            memory_section = mem_prompt

    think_prompt = THINK_PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        kb_list=kb_list,
        skill_catalog=skill_catalog,
        memory_section=memory_section,
        task_guidance=TASK_GUIDANCE,
        memory_guidance=MEMORY_GUIDANCE,
    )

    messages = list(state.get("messages", []))

    # -- Context compaction: work on a copy for LLM input --
    llm_messages = ContextCompactor.micro_compact(
        list(messages),
        keep_recent=settings.CONTEXT_COMPACT_KEEP_RECENT,
    )
    size = ContextCompactor.estimate_context_size(llm_messages)
    compacted_summary = state.get("compacted_summary")

    if size > settings.CONTEXT_COMPACT_LIMIT:
        logger.warning(
            "Context size %d exceeds limit %d, compacting...",
            size, settings.CONTEXT_COMPACT_LIMIT,
        )
        if not compacted_summary:
            compacted_summary = await ContextCompactor.compact_history(
                llm_messages, chat_model,
                context_limit=settings.CONTEXT_COMPACT_LIMIT,
            )
        # Build compacted input: summary + recent messages
        recent = llm_messages[-4:] if len(llm_messages) >= 4 else llm_messages
        llm_messages = [
            HumanMessage(
                content=(
                    "This conversation was compacted so the agent can continue working.\n\n"
                    f"{compacted_summary}"
                )
            )
        ] + recent
    elif compacted_summary:
        # Context shrank below limit; clear cached summary
        compacted_summary = None

    # Drain background task notifications and inject into context
    background_manager = config["configurable"].get("background_manager")
    if background_manager:
        notifs = await background_manager.drain_notifications()
        if notifs:
            lines = ["后台任务状态更新："]
            for n in notifs:
                lines.append(
                    f"- 任务 {n['task_id']}: {n['status']} | 命令: {n['command']} | "
                    f"预览: {n['preview'][:120]}"
                )
            messages.append(HumanMessage(content="\n".join(lines)))
            # Also append to llm_messages so LLM sees it
            llm_messages.append(HumanMessage(content="\n".join(lines)))

    # Add think prompt as a system message
    system_msg = SystemMessage(content=think_prompt)

    # Log summary of recent context to avoid repetitive full dumps
    recent = llm_messages[-3:] if len(llm_messages) >= 3 else llm_messages
    summary = ", ".join(
        f"{type(m).__name__}(tc={len(getattr(m, 'tool_calls', []) or [])})"
        for m in recent
    )
    logger.info("Context: %d messages (raw), %d (compacted), recent: %s", len(messages), len(llm_messages), summary)
    if logger.isEnabledFor(logging.DEBUG):
        for i, msg in enumerate(messages):
            tc = getattr(msg, 'tool_calls', None)
            tci = getattr(msg, 'tool_call_id', None)
            logger.debug("  msg[%d]: type=%s, tool_calls=%s, tool_call_id=%s", i, type(msg).__name__, tc, tci)

    # Ensure tool call / tool response pairs are complete after compaction
    llm_messages = _ensure_tool_call_consistency(llm_messages)

    tool_names = [t.name for t in tools]
    print(f"[DEBUG] Binding {len(tools)} tools: {tool_names}", flush=True)
    logger.info("Binding %d tools: %s", len(tools), tool_names)
    llm_with_tools = chat_model.bind_tools(tools)
    response = await llm_with_tools.ainvoke([system_msg] + llm_messages)

    new_step = state.get("step_count", 0) + 1

    has_tool_calls = bool(response.tool_calls)
    logger.info(
        "think_node step=%d, tool_calls=%s",
        new_step,
        [tc["name"] for tc in response.tool_calls] if has_tool_calls else "none",
    )

    # Persist assistant message (with optional SSE)
    persist_fn = config["configurable"].get("persist_fn")
    if persist_fn:
        await persist_fn(response)

    return_value = {
        "messages": [response],
        "step_count": new_step,
    }
    if compacted_summary is not None:
        return_value["compacted_summary"] = compacted_summary
    return return_value
