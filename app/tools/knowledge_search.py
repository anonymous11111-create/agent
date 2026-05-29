import logging
import time
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
        conf = config.get("configurable", config)

        results, debug_info = await rag_service.similarity_search(db_session, kbs_id, query)

        # Write RAG query log + emit SSE (best-effort, don't block on failure)
        try:
            await _log_rag_query(kbs_id, query, results, debug_info, conf)
        except Exception as log_err:
            logger.warning("RAG query log failed: %s", log_err)

        if not results:
            return "未找到与查询相关的知识片段。"

        parts = []
        for i, r in enumerate(results, 1):
            header = f"【片段 {i}】"
            if r.get("title"):
                header += f"来源章节: {r['title']}"
            if r.get("doc_filename"):
                header += f" | 文档: {r['doc_filename']}"
            parts.append(f"{header}\n{r['content']}")

        return "\n\n".join(parts)
    except Exception as e:
        logger.error("knowledge_query failed: %s", e)
        return f"错误：知识库检索失败 - {e}\n请尝试其他方式获取信息。"


async def _log_rag_query(
    kbs_id: str, query: str, results: list[dict], debug_info: dict, conf: dict
):
    """Persist RAG query log to DB and emit SSE event."""
    from app.db.engine import async_session_factory
    from app.models.rag_query_log import RagQueryLog
    from app.models.knowledge_base import KnowledgeBase
    from app.schemas.sse_event import (
        SseMessage, SsePayload, SseMetadata, SseRagQueryUpdate,
    )

    session_id = conf.get("parent_session_id")
    agent_id = conf.get("agent_id")
    sse_fn = conf.get("sse_fn")

    # Build top_scores summary
    top_scores = []
    for r in results[:5]:
        top_scores.append({
            "chunk_id": r.get("id"),
            "score": r.get("score"),
            "content_preview": (r.get("content") or "")[:100],
            "doc_filename": r.get("doc_filename"),
        })

    log_id = None
    kb_name = None

    async with async_session_factory() as db:
        # Get KB name
        from sqlalchemy import select
        kb_result = await db.execute(
            select(KnowledgeBase.name).where(KnowledgeBase.id == kbs_id)
        )
        kb_row = kb_result.scalar_one_or_none()
        if kb_row:
            kb_name = kb_row

        log = RagQueryLog(
            session_id=session_id,
            agent_id=agent_id,
            knowledge_base_id=kbs_id,
            query=query,
            kb_name=kb_name,
            chunk_count=len(results),
            vector_count=debug_info.get("vector_count", 0),
            keyword_count=debug_info.get("keyword_count", 0),
            top_scores=top_scores,
            embed_ms=debug_info.get("embed_ms"),
            retrieval_ms=debug_info.get("retrieval_ms"),
            fusion_ms=debug_info.get("fusion_ms"),
            total_ms=debug_info.get("total_ms"),
        )
        db.add(log)
        await db.commit()
        log_id = str(log.id)

    # Emit SSE
    if sse_fn and session_id:
        scores_list = [round(s.get("score", 0), 4) for s in top_scores]
        sse_fn(
            session_id,
            SseMessage(
                type="RAG_QUERY_UPDATE",
                payload=SsePayload(
                    ragQueryUpdate=SseRagQueryUpdate(
                        logId=log_id,
                        query=query,
                        kbName=kb_name,
                        chunks=top_scores,
                        chunkCount=len(results),
                        vectorCount=debug_info.get("vector_count", 0),
                        keywordCount=debug_info.get("keyword_count", 0),
                        totalMs=debug_info.get("total_ms"),
                        scores=scores_list,
                    ),
                ),
                metadata=SseMetadata(),
            ),
        )
