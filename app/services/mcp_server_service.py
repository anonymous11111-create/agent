import logging
import uuid
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_server import MCPServerConfig
from app.schemas.mcp_server import (
    CreateMCPServerRequest,
    UpdateMCPServerRequest,
    MCPServerVO,
)

logger = logging.getLogger(__name__)


class MCPServerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_servers(self) -> list[MCPServerVO]:
        result = await self.db.execute(select(MCPServerConfig))
        servers = result.scalars().all()
        return [self._to_vo(s) for s in servers]

    async def create_server(self, request: CreateMCPServerRequest) -> str:
        server = MCPServerConfig(
            name=request.name,
            command=request.command,
            args=request.args or [],
            env=request.env or {},
            enabled=request.enabled if request.enabled is not None else True,
            description=request.description,
        )
        self.db.add(server)
        await self.db.flush()
        return str(server.id)

    async def update_server(
        self, server_id: str, request: UpdateMCPServerRequest
    ) -> bool:
        server = await self._get_by_id(server_id)
        if not server:
            return False

        if request.name is not None:
            server.name = request.name
        if request.command is not None:
            server.command = request.command
        if request.args is not None:
            server.args = request.args
        if request.env is not None:
            server.env = request.env
        if request.enabled is not None:
            server.enabled = request.enabled
        if request.description is not None:
            server.description = request.description

        await self.db.flush()
        return True

    async def delete_server(self, server_id: str) -> bool:
        result = await self.db.execute(
            delete(MCPServerConfig).where(MCPServerConfig.id == uuid.UUID(server_id))
        )
        await self.db.flush()
        return result.rowcount > 0

    async def get_server(self, server_id: str) -> Optional[MCPServerVO]:
        server = await self._get_by_id(server_id)
        return self._to_vo(server) if server else None

    async def _get_by_id(self, server_id: str) -> Optional[MCPServerConfig]:
        result = await self.db.execute(
            select(MCPServerConfig).where(MCPServerConfig.id == uuid.UUID(server_id))
        )
        return result.scalar_one_or_none()

    def _to_vo(self, server: MCPServerConfig) -> MCPServerVO:
        return MCPServerVO(
            id=str(server.id),
            name=server.name,
            command=server.command,
            args=server.args,
            env=server.env,
            enabled=server.enabled,
            description=server.description,
            createdAt=server.created_at,
            updatedAt=server.updated_at,
        )
