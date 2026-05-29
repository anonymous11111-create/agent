import json
import logging

from langchain_core.tools import tool
from langgraph.config import get_config

logger = logging.getLogger(__name__)


def _get_tm_and_config():
    """Retrieve TaskManager and config dict from LangGraph context."""
    config = get_config()
    task_manager = config["configurable"].get("task_manager")
    if not task_manager:
        return None, config
    return task_manager, config


@tool
async def task_create(
    subject: str,
    description: str = "",
    priority: str = "medium",
    tags: list = None,
) -> str:
    """创建一个新任务，将其加入持久化任务图中。返回任务的完整 JSON 信息。

    Args:
        subject: 任务标题
        description: 任务描述（可选）
        priority: 优先级，可选值：low、medium、high、critical（默认 medium）
        tags: 标签列表（可选）
    """
    try:
        task_manager, config = _get_tm_and_config()
        if not task_manager:
            return "错误：TaskManager 未初始化"

        # Auto-inject session/agent context from LangGraph config
        session_id = config["configurable"].get("parent_session_id")
        agent_id = config["configurable"].get("agent_id")

        result = task_manager.create(
            subject=subject,
            description=description,
            priority=priority,
            tags=tags,
            session_id=session_id,
            agent_id=agent_id,
            config=config["configurable"],
        )
        logger.info("task_create: %s", result[:200])
        return result
    except Exception as e:
        logger.error("task_create failed: %s", e)
        return f"创建任务失败: {e}"


@tool
async def task_update(
    task_id: int,
    status: str = None,
    owner: str = None,
    subject: str = None,
    description: str = None,
    priority: str = None,
    tags: list = None,
    progress: int = None,
    addBlockedBy: list = None,
    addBlocks: list = None,
) -> str:
    """更新任务的状态、负责人或依赖关系。

    status 可选值：pending、in_progress、completed、deleted。
    priority 可选值：low、medium、high、critical。
    当任务标记为 completed 时，会自动将其从其他任务的 blockedBy 列表中移除。

    Args:
        task_id: 任务 ID
        status: 新状态
        owner: 负责人
        subject: 新标题
        description: 新描述
        priority: 优先级
        tags: 标签列表
        progress: 进度百分比 (0-100)
        addBlockedBy: 添加阻塞依赖的任务 ID 列表
        addBlocks: 添加被阻塞的任务 ID 列表
    """
    try:
        task_manager, config = _get_tm_and_config()
        if not task_manager:
            return "错误：TaskManager 未初始化"
        result = task_manager.update(
            task_id,
            status=status,
            owner=owner,
            subject=subject,
            description=description,
            priority=priority,
            tags=tags,
            progress=progress,
            add_blocked_by=addBlockedBy,
            add_blocks=addBlocks,
            config=config["configurable"],
        )
        logger.info("task_update: %s", result[:200])
        return result
    except Exception as e:
        logger.error("task_update failed: %s", e)
        return f"更新任务失败: {e}"


@tool
async def task_list() -> str:
    """列出所有任务及其状态摘要，包括阻塞关系、优先级和进度。"""
    try:
        task_manager, _ = _get_tm_and_config()
        if not task_manager:
            return "错误：TaskManager 未初始化"
        result = task_manager.list_all()
        logger.info("task_list: %d chars", len(result))
        return result
    except Exception as e:
        logger.error("task_list failed: %s", e)
        return f"列出任务失败: {e}"


@tool
async def task_get(task_id: int) -> str:
    """根据 ID 获取任务的完整详细信息。"""
    try:
        task_manager, _ = _get_tm_and_config()
        if not task_manager:
            return "错误：TaskManager 未初始化"
        result = task_manager.get(task_id)
        logger.info("task_get: %s", result[:200])
        return result
    except Exception as e:
        logger.error("task_get failed: %s", e)
        return f"获取任务失败: {e}"


@tool
async def task_delete(task_id: int) -> str:
    """永久删除一个任务，同时清理所有依赖引用。"""
    try:
        task_manager, config = _get_tm_and_config()
        if not task_manager:
            return "错误：TaskManager 未初始化"
        result = task_manager.delete(task_id, config=config["configurable"])
        logger.info("task_delete: %s", result[:200])
        return result
    except Exception as e:
        logger.error("task_delete failed: %s", e)
        return f"删除任务失败: {e}"
