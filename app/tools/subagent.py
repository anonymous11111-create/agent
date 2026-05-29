import logging
import time
from pathlib import Path

from langchain_core.tools import tool
from langgraph.config import get_config

from app.tasks.manager import TaskManager

logger = logging.getLogger(__name__)


@tool
async def delegate_task(task_prompt: str) -> str:
    """将任务委派给子智能体执行。子智能体拥有独立的上下文和工具集，会完整执行任务并返回最终结果摘要。参数：taskPrompt（任务描述，必填）。"""
    config = get_config()
    agent_id = config["configurable"]["agent_id"]
    parent_session_id = config["configurable"].get("parent_session_id")
    parent_persist_fn = config["configurable"].get("persist_fn")

    from app.services.chat_service import ChatService
    from app.agent.graph import build_agent_graph
    from app.tools.registry import get_tools_for_agent
    from app.llm.registry import get_chat_model
    from app.services.skill_service import skill_registry
    from app.services.sse_service import sse_service
    from app.schemas.sse_event import SseMessage, SsePayload, SseMetadata
    from app.config import settings
    from app.db.engine import async_session_factory
    from langchain_core.messages import HumanMessage

    def notify_parent(status_text: str, msg_type: str = "AI_EXECUTING"):
        if parent_session_id:
            try:
                sse_service.send(
                    parent_session_id,
                    SseMessage(
                        type=msg_type,
                        payload=SsePayload(statusText=status_text),
                        metadata=SseMetadata(),
                    ),
                )
            except Exception:
                pass

    # Each sub-agent gets its own db session to avoid concurrent access errors
    async with async_session_factory() as sub_db:
        chat_service = ChatService(sub_db)

        # 1. Create sub session
        sub_session = await chat_service.create_session(
            agent_id=agent_id, title="子智能体任务", session_type="SUBAGENT"
        )
        sub_session_id = str(sub_session.id)

        logger.info("Sub-agent created: agent=%s, session=%s", agent_id, sub_session_id)
        notify_parent(f"子智能体已启动: {task_prompt[:50]}...")

        try:
            # 2. Persist task prompt as user message
            await chat_service.create_message(
                session_id=sub_session_id,
                role="user",
                content=task_prompt,
            )

            # 3. Build sub-agent graph (exclude delegate_task to prevent recursion)
            agent_model = await chat_service.get_agent_model(agent_id)
            chat_model = get_chat_model(agent_model)
            tools = get_tools_for_agent(
                await chat_service.get_agent_entity(agent_id),
                exclude_tool_names={"delegate_task"},
            )
            tools_map = {t.name: t for t in tools}

            # Load memory
            memory_messages = await chat_service.load_memory(
                sub_session_id, message_length=settings.CHAT_MEMORY_WINDOW_SIZE
            )

            graph = build_agent_graph()

            initial_state = {
                "messages": memory_messages + [HumanMessage(content=task_prompt)],
                "step_count": 0,
                "terminated": False,
                "tool_call_history": [],
                "start_time": time.monotonic(),
                "error": None,
            }

            sub_config = {
                "configurable": {
                    "chat_model": chat_model,
                    "tools": tools,
                    "tools_map": tools_map,
                    "agent_id": agent_id,
                    "db_session": sub_db,
                    "kb_list": config["configurable"].get("kb_list", "[]"),
                    "skill_catalog": skill_registry.describe_available(),
                    "parent_session_id": sub_session_id,
                    "persist_fn": parent_persist_fn,
                    "task_manager": TaskManager(Path.cwd() / ".tasks"),
                    "hook_manager": config["configurable"].get("hook_manager"),
                    "memory_manager": config["configurable"].get("memory_manager"),
                }
            }

            # Stream events for progress + collect final state
            final_state = initial_state
            step_count = 0
            async for event in graph.astream(initial_state, sub_config, stream_mode="updates"):
                step_count += 1
                if "think" in event:
                    think_data = event["think"]
                    final_state["step_count"] = think_data.get("step_count", step_count)
                    msgs = think_data.get("messages", [])
                    if msgs:
                        final_state["messages"] = final_state.get("messages", []) + msgs
                        last = msgs[-1]
                        tc_names = [tc["name"] for tc in getattr(last, "tool_calls", [])]
                        if tc_names:
                            notify_parent(f"子智能体步骤 {step_count}: 调用 {', '.join(tc_names)}")
                        else:
                            notify_parent(f"子智能体步骤 {step_count}: 生成回复...")
                elif "execute" in event:
                    exec_data = event["execute"]
                    msgs = exec_data.get("messages", [])
                    if msgs:
                        final_state["messages"] = final_state.get("messages", []) + msgs
                    notify_parent(f"子智能体步骤 {step_count}: 处理工具结果...")

            logger.info("Sub-agent completed: session=%s, steps=%d", sub_session_id, step_count)

            # Extract last assistant text, capped to prevent excessive output
            messages = final_state.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content and msg.type == "ai":
                    text = msg.content
                    if len(text) > 3000:
                        text = text[:3000] + "\n\n...(输出已截断，共 %d 字)" % len(msg.content)
                    return text

            return "子智能体执行完成，但未生成文本回复"

        except Exception as e:
            logger.error("Sub-agent failed: %s", e, exc_info=True)
            return f"子智能体执行失败: {e}"
