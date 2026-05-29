import logging
from langchain_core.tools import tool
from langgraph.config import get_config

from app.services.skill_service import skill_registry

logger = logging.getLogger(__name__)


@tool
def load_skill(name: str) -> str:
    """按名称加载一个技能的完整指导内容。技能包含特定任务的最佳实践、检查清单或操作指南。参数：name（技能名称，必填）。"""
    logger.info("Loading skill: %s", name)
    return skill_registry.load_full_text(name)
