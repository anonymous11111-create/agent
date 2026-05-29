import logging
from typing import Optional

from sqlalchemy import select, func, Float, Integer, and_, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_call_log import ToolCallLog
from app.schemas.tool_call_log import ToolCallLogVO, ToolCallStatsVO

logger = logging.getLogger(__name__)


class ToolCallLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_log(
        self,
        session_id: str,
        agent_id: str,
        tool_name: str,
        tool_call_id: str,
        arguments: dict = None,
        status: str = "success",
        duration_ms: float = None,
        error_message: str = None,
        result_preview: str = None,
    ) -> ToolCallLog:
        log = ToolCallLog(
            session_id=session_id,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            arguments=arguments,
            status=status,
            duration_ms=duration_ms,
            error_message=error_message,
            result_preview=result_preview[:500] if result_preview else None,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    def _to_vo(self, log: ToolCallLog) -> ToolCallLogVO:
        return ToolCallLogVO(
            id=str(log.id),
            sessionId=str(log.session_id),
            agentId=str(log.agent_id),
            toolName=log.tool_name,
            toolCallId=log.tool_call_id,
            arguments=log.arguments,
            status=log.status,
            durationMs=log.duration_ms,
            errorMessage=log.error_message,
            resultPreview=log.result_preview,
            createdAt=str(log.created_at) if log.created_at else None,
            updatedAt=str(log.updated_at) if log.updated_at else None,
        )

    async def list_logs(
        self,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ToolCallLogVO], int]:
        conditions = []
        if session_id:
            conditions.append(ToolCallLog.session_id == session_id)
        if agent_id:
            conditions.append(ToolCallLog.agent_id == agent_id)
        if tool_name:
            conditions.append(ToolCallLog.tool_name == tool_name)
        if status:
            conditions.append(ToolCallLog.status == status)

        # Count
        count_q = select(func.count()).select_from(ToolCallLog)
        if conditions:
            count_q = count_q.where(and_(*conditions))
        total = (await self.db.execute(count_q)).scalar() or 0

        # Query
        q = select(ToolCallLog).order_by(ToolCallLog.created_at.desc())
        if conditions:
            q = q.where(and_(*conditions))
        q = q.limit(limit).offset(offset)

        result = await self.db.execute(q)
        logs = result.scalars().all()
        return [self._to_vo(l) for l in logs], total

    async def get_stats(
        self,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> list[ToolCallStatsVO]:
        conditions = []
        if session_id:
            conditions.append(ToolCallLog.session_id == session_id)
        if agent_id:
            conditions.append(ToolCallLog.agent_id == agent_id)

        q = (
            select(
                ToolCallLog.tool_name,
                func.count().label("total_calls"),
                func.sum(func.cast(ToolCallLog.status == "success", Integer)).label("success_count"),
                func.sum(func.cast(ToolCallLog.status == "fail", Integer)).label("fail_count"),
                func.sum(func.cast(ToolCallLog.status == "timeout", Integer)).label("timeout_count"),
                func.sum(func.cast(ToolCallLog.status == "blocked", Integer)).label("blocked_count"),
                func.avg(cast(ToolCallLog.duration_ms, Float)).label("avg_duration"),
                func.max(cast(ToolCallLog.duration_ms, Float)).label("max_duration"),
                func.min(cast(ToolCallLog.duration_ms, Float)).label("min_duration"),
            )
            .group_by(ToolCallLog.tool_name)
        )

        if conditions:
            q = q.where(and_(*conditions))

        result = await self.db.execute(q)
        rows = result.all()

        stats = []
        for r in rows:
            total = r.total_calls or 0
            success = r.success_count or 0
            stats.append(ToolCallStatsVO(
                toolName=r.tool_name,
                totalCalls=total,
                successCount=success,
                failCount=r.fail_count or 0,
                timeoutCount=r.timeout_count or 0,
                blockedCount=r.blocked_count or 0,
                avgDurationMs=round(r.avg_duration, 1) if r.avg_duration else None,
                maxDurationMs=round(r.max_duration, 1) if r.max_duration else None,
                minDurationMs=round(r.min_duration, 1) if r.min_duration else None,
                successRate=round(success / total * 100, 1) if total > 0 else 0,
            ))
        return stats
