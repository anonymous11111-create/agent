import logging

from langchain_core.tools import tool
from langgraph.config import get_config

logger = logging.getLogger(__name__)


@tool
async def save_memory(name: str, description: str, type: str, content: str) -> str:
    """保存一条跨会话持久化的记忆。用于记录用户偏好、反馈、项目约定或外部资源指针等信息，在后续对话中自动注入系统提示。

    参数说明：
    - name: 记忆的短标识符（如 prefer_tabs, db_schema）
    - description: 一句话摘要
    - type: 记忆类型，可选 user（用户偏好）、feedback（用户纠正）、project（项目约定）、reference（外部资源）
    - content: 记忆的完整内容（支持多行）
    """
    if type not in ("user", "feedback", "project", "reference"):
        return f"错误：type 必须是 user、feedback、project 或 reference 之一"

    try:
        config = get_config()
        memory_manager = config["configurable"].get("memory_manager")
        if not memory_manager:
            return "错误：MemoryManager 未初始化"

        result = memory_manager.save_memory(name, description, type, content)
        logger.info("save_memory: %s", result)
        return result
    except Exception as e:
        logger.error("save_memory failed: %s", e)
        return f"保存记忆失败: {e}"
