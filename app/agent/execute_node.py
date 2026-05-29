import asyncio
import hashlib
import json
import logging
import time

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from app.agent.state import AgentState
from app.config import settings
from app.hooks import HookManager
from app.context_compact import ContextCompactor
from app.mcp import CapabilityPermissionGate

logger = logging.getLogger(__name__)

permission_gate = CapabilityPermissionGate()

RETRYABLE_TOOLS = {"knowledge_query", "database_query", "send_email"}
MAX_DUPLICATE_CALLS = settings.AGENT_MAX_DUPLICATE_CALLS
MAX_RETRY_ATTEMPTS = settings.AGENT_MAX_RETRY_ATTEMPTS
TOOL_TIMEOUT_SECONDS = 30.0
# 子智能体需要更长的超时时间（运行完整的 think-execute 循环）

TOOL_TIMEOUT_OVERRIDES = {
    "delegate_task": 180.0,  # 3 分钟
    "tavily_search": 60.0,   # Tavily 网络搜索
    "tavily_extract": 60.0,  # Tavily 网页提取
    "tavily_crawl": 90.0,    # Tavily 网站爬取
    "tavily_research": 120.0, # Tavily 深度研究
}


def _make_dedup_key(tool_name: str, args: dict) -> str:
    args_str = json.dumps(args, sort_keys=True, ensure_ascii=False)
    return f"{tool_name}:{hashlib.md5(args_str.encode()).hexdigest()}"


def _get_tool_timeout(tool_name: str) -> float:
    return TOOL_TIMEOUT_OVERRIDES.get(tool_name, TOOL_TIMEOUT_SECONDS)


async def _execute_tool_with_retry(
    tool: BaseTool, tool_input: dict, config: RunnableConfig, max_retries: int = MAX_RETRY_ATTEMPTS
) -> str:
    """Execute tool with retry for network-reliant tools."""
    timeout = _get_tool_timeout(tool.name)
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            result = await asyncio.wait_for(tool.ainvoke(tool_input, config=config), timeout=timeout)
            return str(result)
        except asyncio.TimeoutError:
            last_exc = asyncio.TimeoutError(f"Tool {tool.name} timed out after {timeout}s")
            logger.warning("Tool %s attempt %d/%d timed out", tool.name, attempt, max_retries)
            if attempt < max_retries:
                await asyncio.sleep(1.0 * attempt)
        except Exception as e:
            last_exc = e
            logger.warning("Tool %s attempt %d/%d failed: %s", tool.name, attempt, max_retries, e)
            if attempt < max_retries:
                await asyncio.sleep(1.0 * attempt)
    return f"工具调用失败: {type(last_exc).__name__} - {last_exc}\n请尝试其他方式完成任务。"


async def _preprocess_tool_call(
    tc: dict, history: list[str], hook_manager, tools_map: dict
) -> tuple[dict, str | None]:
    """Run pre-checks (hooks, permission, dedup) for a tool call.

    Returns (processed_tc, error_message_or_None).
    If error_message is not None, the tool should be skipped.
    """
    tool_name = tc["name"]
    tool_args = tc.get("args", {})
    tool_call_id = tc.get("id", "")

    # -- PreToolUse hooks --
    if hook_manager:
        ctx = {"tool_name": tool_name, "tool_input": dict(tool_args)}
        pre_result = await hook_manager.run_hooks("PreToolUse", ctx)
        if pre_result.get("blocked"):
            reason = pre_result.get("block_reason", "Blocked by hook")
            return tc, f"Tool blocked by PreToolUse hook: {reason}"
        updated_input = ctx.get("tool_input")
        if updated_input and isinstance(updated_input, dict):
            tc = {**tc, "args": updated_input}
            tool_args = updated_input

    # -- Permission gate --
    decision = permission_gate.check(tool_name, tool_args)
    if decision.get("behavior") == "deny":
        return tc, f"Permission denied: {decision.get('reason', 'Blocked by permission gate')}"

    # -- Dedup check --
    dedup_key = _make_dedup_key(tool_name, tool_args)
    count = history.count(dedup_key)
    if count >= MAX_DUPLICATE_CALLS:
        logger.warning("Dedup: tool=%s count=%d", tool_name, count)
        return tc, (
            f"重复调用拦截：你已经使用完全相同的参数调用了工具 {tool_name} "
            f"超过最大重试次数。请换一种策略来解决问题。"
        )
    history.append(dedup_key)

    # -- Tool existence --
    if tools_map.get(tool_name) is None:
        return tc, f"未知工具: {tool_name}"

    return tc, None


async def _run_single_tool(
    tool: BaseTool, tool_args: dict, tool_name: str, tool_call_id: str,
    config: RunnableConfig, hook_manager
) -> str:
    """Execute a single tool and return the result string."""
    tool_timeout = _get_tool_timeout(tool_name)
    if tool_name in RETRYABLE_TOOLS:
        result = await _execute_tool_with_retry(tool, tool_args, config)
    else:
        try:
            result = str(await asyncio.wait_for(
                tool.ainvoke(tool_args, config=config), timeout=tool_timeout
            ))
        except asyncio.TimeoutError:
            logger.error("Tool %s timed out after %ss", tool_name, tool_timeout)
            result = (
                f"工具调用超时: {tool_name} 执行超过 {tool_timeout}s\n"
                f"请尝试其他方式完成任务，或告知用户该工具暂不可用。"
            )
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e)
            result = (
                f"工具调用失败: {type(e).__name__} - {e}\n"
                f"请尝试其他方式完成任务，或告知用户该工具暂不可用。"
            )

    # Persist large output
    result = ContextCompactor.persist_large_output(
        tool_call_id, result,
        persist_threshold=settings.CONTEXT_COMPACT_PERSIST_THRESHOLD,
        preview_chars=settings.CONTEXT_COMPACT_PREVIEW_CHARS,
    )

    # -- PostToolUse hooks --
    if hook_manager:
        ctx = {"tool_name": tool_name, "tool_input": dict(tool_args), "tool_output": result}
        post_result = await hook_manager.run_hooks("PostToolUse", ctx)
        for msg in post_result.get("messages", []):
            result += f"\n[Hook note]: {msg}"

    return result


async def execute_node(state: AgentState, config: RunnableConfig) -> dict:
    """Execute tool calls from the last AIMessage.

    Multiple delegate_task calls are executed in parallel.
    Other tools are executed sequentially.
    """
    tools_map: dict[str, BaseTool] = config["configurable"]["tools_map"]
    persist_fn = config["configurable"].get("persist_fn")
    hook_manager: HookManager = config["configurable"].get("hook_manager")

    messages = state.get("messages", [])
    if not messages:
        return {"terminated": True}

    last_ai = messages[-1]
    tool_calls = getattr(last_ai, "tool_calls", [])
    if not tool_calls:
        return {"terminated": True}

    history: list[str] = list(state.get("tool_call_history", []))
    terminated = state.get("terminated", False)
    new_messages: list[ToolMessage] = []

    # Phase 1: Pre-process all tool calls (sequential, fast)
    # Separate into sequential tasks and parallelizable delegate_task calls
    sequential_tasks = []  # [(tc, tool, result_or_None)]
    parallel_tasks = []    # [(tc, tool)]

    for tc in tool_calls:
        tc, error = await _preprocess_tool_call(tc, history, hook_manager, tools_map)
        tool_name = tc["name"]
        tool_call_id = tc.get("id", "")

        if error:
            new_messages.append(ToolMessage(content=error, tool_call_id=tool_call_id))
            continue

        tool = tools_map[tool_name]

        if tool_name == "delegate_task" and sum(
            1 for t in tool_calls if t["name"] == "delegate_task"
        ) > 1:
            # Multiple delegate_task calls -> parallel execution
            parallel_tasks.append((tc, tool))
        else:
            sequential_tasks.append((tc, tool))

    # Phase 2a: Execute sequential tools
    for tc, tool in sequential_tasks:
        tool_name = tc["name"]
        tool_args = tc.get("args", {})
        tool_call_id = tc.get("id", "")

        result = await _run_single_tool(
            tool, tool_args, tool_name, tool_call_id, config, hook_manager
        )
        new_messages.append(
            ToolMessage(content=result, tool_call_id=tool_call_id, name=tool_name)
        )
        if tool_name == "terminate":
            terminated = True

    # Phase 2b: Execute delegate_task calls in parallel
    if parallel_tasks:
        logger.info("Running %d delegate_task calls in parallel", len(parallel_tasks))
        coros = []
        for tc, tool in parallel_tasks:
            coros.append(_run_single_tool(
                tool, tc.get("args", {}), tc["name"], tc.get("id", ""),
                config, hook_manager,
            ))
        results = await asyncio.gather(*coros, return_exceptions=True)

        for (tc, tool), result in zip(parallel_tasks, results):
            tool_call_id = tc.get("id", "")
            tool_name = tc["name"]
            if isinstance(result, Exception):
                result = (
                    f"工具调用失败: {type(result).__name__} - {result}\n"
                    f"请尝试其他方式完成任务。"
                )
            else:
                result = str(result)
            new_messages.append(
                ToolMessage(content=result, tool_call_id=tool_call_id, name=tool_name)
            )

    # Persist
    if persist_fn:
        for msg in new_messages:
            await persist_fn(msg)

    return {
        "messages": new_messages,
        "tool_call_history": history,
        "terminated": terminated,
    }
