import logging
from langchain_core.tools import tool
from langgraph.config import get_config

from app.rag.service import rag_service

logger = logging.getLogger(__name__)


@tool
async def knowledge_query(kbs_id: str, query: str) -> str:
    """从指定知识库中执行相似性检索（RAG）。参数为知识库 ID（kbsId）和查询文本（query），返回与查询最相关的知识片段。"""
    try:
        config = get_config()
        db_session = config["configurable"]["db_session"]

        results = await rag_service.similarity_search(db_session, kbs_id, query)
        if not results:
            return "未找到与查询相关的知识片段。"

        parts = []
        for i, r in enumerate(results, 1):
            header = f"【片段 {i}】"
            if r.get("title"):
                header += f"来源章节: {r['title']}"
            parts.append(f"{header}\n{r['content']}")

        return "\n\n".join(parts)
    except Exception as e:
        logger.error("knowledge_query failed: %s", e)
        return f"错误：知识库检索失败 - {e}\n请尝试其他方式获取信息。"
