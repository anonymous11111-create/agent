from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import ApiResponse
from app.schemas.rag_query_log import (
    FeedbackRequest,
    GetRagQueryLogsResponse,
)
from app.services.rag_query_log_service import RagQueryLogService

router = APIRouter(prefix="/api", tags=["rag-query-logs"])


@router.get("/rag-query-logs")
async def get_rag_query_logs(
    sessionId: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    svc = RagQueryLogService(db)
    logs, total = await svc.list_logs(session_id=sessionId, limit=limit, offset=offset)
    return ApiResponse.success(GetRagQueryLogsResponse(logs=logs, total=total))


@router.get("/rag-query-logs/stats")
async def get_rag_stats(
    sessionId: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    svc = RagQueryLogService(db)
    stats = await svc.get_stats(session_id=sessionId)
    return ApiResponse.success(stats)


@router.post("/rag-query-logs/{log_id}/feedback")
async def submit_rag_feedback(
    log_id: str,
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = RagQueryLogService(db)
    found = await svc.submit_feedback(log_id, request.feedback)
    if not found:
        return ApiResponse.success(data={"status": "not_found"})
    await db.commit()
    return ApiResponse.success(data={"status": "ok"})
