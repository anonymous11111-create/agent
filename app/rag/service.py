import asyncio
import logging
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.rag.embedder import embed_text
from app.rag.vector_search import vector_search
from app.rag.keyword_search import keyword_search
from app.rag.fusion import rrf_fusion

logger = logging.getLogger(__name__)


class RagService:
    """Top-level RAG service: embed + multi-path retrieval + RRF fusion."""

    async def embed(self, text: str) -> list[float]:
        return await embed_text(text)

    async def similarity_search(
        self,
        session: AsyncSession,
        kb_id: str,
        query: str,
    ) -> tuple[list[dict], dict]:
        """Hybrid search: vector + keyword + RRF fusion.

        Returns (fused_results, debug_info) where debug_info contains
        timing and retrieval counts for monitoring.
        """
        t_start = time.monotonic()

        t0 = time.monotonic()
        query_embedding = await embed_text(query)
        embed_ms = round((time.monotonic() - t0) * 1000, 1)

        t1 = time.monotonic()
        vector_results, keyword_results = await asyncio.gather(
            vector_search(
                session,
                kb_id,
                query_embedding,
                top_k=settings.RAG_TOP_K,
                similarity_threshold=settings.RAG_SIMILARITY_THRESHOLD,
            ),
            keyword_search(
                session,
                kb_id,
                query,
                top_k=settings.RAG_KEYWORD_TOP_K,
                threshold=settings.RAG_KEYWORD_THRESHOLD,
            ),
        )
        retrieval_ms = round((time.monotonic() - t1) * 1000, 1)

        logger.info(
            "RAG: vector=%d, keyword=%d",
            len(vector_results),
            len(keyword_results),
        )

        t2 = time.monotonic()
        fused = rrf_fusion(vector_results, keyword_results, k=settings.RAG_RRF_K)
        fusion_ms = round((time.monotonic() - t2) * 1000, 1)

        total_ms = round((time.monotonic() - t_start) * 1000, 1)

        debug_info = {
            "vector_count": len(vector_results),
            "keyword_count": len(keyword_results),
            "embed_ms": embed_ms,
            "retrieval_ms": retrieval_ms,
            "fusion_ms": fusion_ms,
            "total_ms": total_ms,
        }

        return fused[: settings.RAG_FINAL_TOP_N], debug_info


rag_service = RagService()
