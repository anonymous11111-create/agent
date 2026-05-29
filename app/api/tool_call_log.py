from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import ApiResponse
from app.schemas.tool_call_log import (
    GetToolCallLogsResponse,
    GetToolCallStatsResponse,
)
from app.services.tool_call_log_service import ToolCallLogService

router = APIRouter(prefix="/api", tags=["tool-call-logs"])


@router.get("/tool-call-logs")
async def get_tool_call_logs(
    sessionId: Optional[str] = Query(None),
    agentId: Optional[str] = Query(None),
    toolName: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    svc = ToolCallLogService(db)
    logs, total = await svc.list_logs(
        session_id=sessionId,
        agent_id=agentId,
        tool_name=toolName,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ApiResponse.success(GetToolCallLogsResponse(logs=logs, total=total))


@router.get("/tool-call-logs/stats")
async def get_tool_call_stats(
    sessionId: Optional[str] = Query(None),
    agentId: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    svc = ToolCallLogService(db)
    stats = await svc.get_stats(session_id=sessionId, agent_id=agentId)
    return ApiResponse.success(GetToolCallStatsResponse(stats=stats))
