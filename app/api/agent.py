from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import ApiResponse
from app.schemas.agent import (
    CreateAgentRequest,
    UpdateAgentRequest,
    GetAgentsResponse,
    CreateAgentResponse,
)
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/agents")
async def get_agents(db: AsyncSession = Depends(get_db)):
    svc = AgentService(db)
    agents = await svc.list_agents()
    return ApiResponse.success(GetAgentsResponse(agents=agents))


@router.post("/agents")
async def create_agent(request: CreateAgentRequest, db: AsyncSession = Depends(get_db)):
    svc = AgentService(db)
    agent_id = await svc.create_agent(request)
    await db.commit()
    return ApiResponse.success(CreateAgentResponse(agentId=agent_id))


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    svc = AgentService(db)
    await svc.delete_agent(agent_id)
    await db.commit()
    return ApiResponse.success()


@router.patch("/agents/{agent_id}")
async def update_agent(
    agent_id: str, request: UpdateAgentRequest, db: AsyncSession = Depends(get_db)
):
    svc = AgentService(db)
    await svc.update_agent(agent_id, request)
    await db.commit()
    return ApiResponse.success()
