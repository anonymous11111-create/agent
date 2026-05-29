import asyncio
import logging
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
    ) -> list[dict]:
        """Hybrid search: vector + keyword + RRF fusion."""
        query_embedding = await embed_text(query)

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

        logger.info(
            "RAG: vector=%d, keyword=%d",
            len(vector_results),
            len(keyword_results),
        )

        fused = rrf_fusion(vector_results, keyword_results, k=settings.RAG_RRF_K)
        return fused[: settings.RAG_FINAL_TOP_N]


rag_service = RagService()
