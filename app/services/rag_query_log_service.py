import logging
from typing import Optional

from sqlalchemy import select, func, and_, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag_query_log import RagQueryLog
from app.schemas.rag_query_log import RagQueryLogVO, RagStatsVO

logger = logging.getLogger(__name__)


class RagQueryLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _to_vo(self, log: RagQueryLog) -> RagQueryLogVO:
        return RagQueryLogVO(
            id=str(log.id),
            sessionId=str(log.session_id),
            agentId=str(log.agent_id),
            knowledgeBaseId=str(log.knowledge_base_id),
            query=log.query,
            kbName=log.kb_name,
            chunkCount=log.chunk_count,
            vectorCount=log.vector_count,
            keywordCount=log.keyword_count,
            topScores=log.top_scores,
            embedMs=log.embed_ms,
            retrievalMs=log.retrieval_ms,
            fusionMs=log.fusion_ms,
            totalMs=log.total_ms,
            feedback=log.feedback,
            createdAt=str(log.created_at) if log.created_at else None,
        )

    async def submit_feedback(self, log_id: str, feedback: str) -> bool:
        from sqlalchemy import text
        result = await self.db.execute(
            select(RagQueryLog).where(RagQueryLog.id == log_id)
        )
        log = result.scalar_one_or_none()
        if not log:
            return False
        log.feedback = feedback
        await self.db.flush()
        return True

    async def list_logs(
        self,
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RagQueryLogVO], int]:
        conditions = []
        if session_id:
            conditions.append(RagQueryLog.session_id == session_id)

        count_q = select(func.count()).select_from(RagQueryLog)
        if conditions:
            count_q = count_q.where(and_(*conditions))
        total = (await self.db.execute(count_q)).scalar() or 0

        q = select(RagQueryLog).order_by(RagQueryLog.created_at.desc())
        if conditions:
            q = q.where(and_(*conditions))
        q = q.limit(limit).offset(offset)

        result = await self.db.execute(q)
        logs = result.scalars().all()
        return [self._to_vo(l) for l in logs], total

    async def get_stats(self, session_id: Optional[str] = None) -> RagStatsVO:
        conditions = []
        if session_id:
            conditions.append(RagQueryLog.session_id == session_id)

        base = select(
            func.count().label("total"),
            func.avg(RagQueryLog.chunk_count).label("avg_chunks"),
            func.avg(RagQueryLog.total_ms).label("avg_ms"),
            func.sum(
                func.cast(RagQueryLog.feedback == "positive", Integer)
            ).label("pos"),
            func.sum(
                func.cast(RagQueryLog.feedback == "negative", Integer)
            ).label("neg"),
        )
        if conditions:
            base = base.where(and_(*conditions))

        result = await self.db.execute(base)
        row = result.one()
        total = row.total or 0
        return RagStatsVO(
            totalQueries=total,
            avgChunkCount=round(float(row.avg_chunks or 0), 1),
            avgTotalMs=round(float(row.avg_ms or 0), 1) if row.avg_ms else None,
            positiveFeedback=int(row.pos or 0),
            negativeFeedback=int(row.neg or 0),
        )
