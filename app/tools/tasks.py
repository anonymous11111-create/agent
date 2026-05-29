import logging

from langchain_core.tools import tool
from langgraph.config import get_config

logger = logging.getLogger(__name__)


@tool
async def task_create(subject: str, description: str = "") -> str:
    """创建一个新任务，将其加入持久化任务图中。返回任务的完整 JSON 信息。"""
    try:
        config = get_config()
        task_manager = config["configurable"].get("task_manager")
        if not task_manager:
            return "错误：TaskManager 未初始化"
        result = task_manager.create(subject, description)
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
    addBlockedBy: list = None,
    addBlocks: list = None,
) -> str:
    """更新任务的状态、负责人或依赖关系。status 可选值：pending、in_progress、completed、deleted。
    当任务标记为 completed 时，会自动将其从其他任务的 blockedBy 列表中移除。"""
    try:
        config = get_config()
        task_manager = config["configurable"].get("task_manager")
        if not task_manager:
            return "错误：TaskManager 未初始化"
        result = task_manager.update(
            task_id, status, owner,
            add_blocked_by=addBlockedBy,
            add_blocks=addBlocks,
        )
        logger.info("task_update: %s", result[:200])
        return result
    except Exception as e:
        logger.error("task_update failed: %s", e)
        return f"更新任务失败: {e}"


@tool
async def task_list() -> str:
    """列出所有任务及其状态摘要，包括阻塞关系。"""
    try:
        config = get_config()
        task_manager = config["configurable"].get("task_manager")
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
        config = get_config()
        task_manager = config["configurable"].get("task_manager")
        if not task_manager:
            return "错误：TaskManager 未初始化"
        result = task_manager.get(task_id)
        logger.info("task_get: %s", result[:200])
        return result
    except Exception as e:
        logger.error("task_get failed: %s", e)
        return f"获取任务失败: {e}"
