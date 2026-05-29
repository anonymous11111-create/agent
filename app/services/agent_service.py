import uuid
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.schemas.agent import (
    CreateAgentRequest,
    UpdateAgentRequest,
    AgentVO,
    ChatOptions,
)

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_agents(self) -> list[AgentVO]:
        result = await self.db.execute(select(Agent))
        agents = result.scalars().all()
        return [self._to_vo(a) for a in agents]

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        result = await self.db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
        return result.scalar_one_or_none()

    async def create_agent(self, request: CreateAgentRequest) -> str:
        agent = Agent(
            name=request.name,
            description=request.description,
            system_prompt=request.systemPrompt,
            model=request.model or "deepseek-chat",
            allowed_tools=request.allowedTools if request.allowedTools else None,
            allowed_kbs=request.allowedKbs if request.allowedKbs else None,
            chat_options=request.chatOptions.model_dump() if request.chatOptions else None,
        )
        self.db.add(agent)
        await self.db.flush()
        return str(agent.id)

    async def update_agent(self, agent_id: str, request: UpdateAgentRequest):
        agent = await self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        if request.name is not None:
            agent.name = request.name
        if request.description is not None:
            agent.description = request.description
        if request.systemPrompt is not None:
            agent.system_prompt = request.systemPrompt
        if request.model is not None:
            agent.model = request.model
        if request.allowedTools is not None:
            agent.allowed_tools = request.allowedTools
        if request.allowedKbs is not None:
            agent.allowed_kbs = request.allowedKbs
        if request.chatOptions is not None:
            agent.chat_options = request.chatOptions.model_dump()
        agent.updated_at = datetime.now()
        await self.db.flush()

    async def delete_agent(self, agent_id: str):
        await self.db.execute(delete(Agent).where(Agent.id == uuid.UUID(agent_id)))
        await self.db.flush()

    def _to_vo(self, agent: Agent) -> AgentVO:
        # JSON columns are auto-deserialized by SQLAlchemy, no need for json.loads
        allowed_tools = agent.allowed_tools if agent.allowed_tools else None
        allowed_kbs = agent.allowed_kbs if agent.allowed_kbs else None
        chat_options = None
        if agent.chat_options:
            co = agent.chat_options if isinstance(agent.chat_options, dict) else json.loads(agent.chat_options)
            chat_options = ChatOptions(**co)

        return AgentVO(
            id=str(agent.id),
            name=agent.name,
            description=agent.description,
            systemPrompt=agent.system_prompt,
            model=agent.model,
            allowedTools=allowed_tools,
            allowedKbs=allowed_kbs,
            chatOptions=chat_options,
            createdAt=agent.created_at,
            updatedAt=agent.updated_at,
        )
