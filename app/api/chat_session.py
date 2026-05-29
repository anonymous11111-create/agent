from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import ApiResponse
from app.schemas.chat_session import (
    CreateChatSessionRequest,
    UpdateChatSessionRequest,
    GetChatSessionsResponse,
    GetChatSessionResponse,
    CreateChatSessionResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api", tags=["chat-sessions"])


@router.get("/chat-sessions")
async def get_chat_sessions(db: AsyncSession = Depends(get_db)):
    svc = ChatService(db)
    sessions = await svc.list_sessions()
    return ApiResponse.success(GetChatSessionsResponse(chatSessions=sessions))


@router.get("/chat-sessions/{chat_session_id}")
async def get_chat_session(chat_session_id: str, db: AsyncSession = Depends(get_db)):
    svc = ChatService(db)
    session = await svc.get_session(chat_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ApiResponse.success(GetChatSessionResponse(chatSession=session))


@router.get("/chat-sessions/agent/{agent_id}")
async def get_sessions_by_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    svc = ChatService(db)
    sessions = await svc.list_sessions_by_agent(agent_id)
    return ApiResponse.success(GetChatSessionsResponse(chatSessions=sessions))


@router.post("/chat-sessions")
async def create_chat_session(
    request: CreateChatSessionRequest, db: AsyncSession = Depends(get_db)
):
    svc = ChatService(db)
    session = await svc.create_session(
        agent_id=request.agentId,
        title=request.title,
        session_type=request.type or "NORMAL",
    )
    await db.commit()
    return ApiResponse.success(CreateChatSessionResponse(chatSessionId=str(session.id)))


@router.delete("/chat-sessions/{chat_session_id}")
async def delete_chat_session(chat_session_id: str, db: AsyncSession = Depends(get_db)):
    svc = ChatService(db)
    await svc.delete_session(chat_session_id)
    await db.commit()
    return ApiResponse.success()


@router.patch("/chat-sessions/{chat_session_id}")
async def update_chat_session(
    chat_session_id: str,
    request: UpdateChatSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = ChatService(db)
    await svc.update_session(chat_session_id, request)
    await db.commit()
    return ApiResponse.success()
