from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import ApiResponse
from app.schemas.mcp_server import (
    CreateMCPServerRequest,
    UpdateMCPServerRequest,
    GetMCPServersResponse,
    CreateMCPServerResponse,
    MCPServerVO,
)
from app.services.mcp_server_service import MCPServerService

router = APIRouter(prefix="/api", tags=["mcp-servers"])


@router.get("/mcp-servers")
async def get_mcp_servers(db: AsyncSession = Depends(get_db)):
    svc = MCPServerService(db)
    servers = await svc.list_servers()
    return ApiResponse.success(GetMCPServersResponse(servers=servers))


@router.post("/mcp-servers")
async def create_mcp_server(
    request: CreateMCPServerRequest, db: AsyncSession = Depends(get_db)
):
    svc = MCPServerService(db)
    server_id = await svc.create_server(request)
    await db.commit()
    return ApiResponse.success(CreateMCPServerResponse(serverId=server_id))


@router.get("/mcp-servers/{server_id}")
async def get_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    svc = MCPServerService(db)
    server = await svc.get_server(server_id)
    if not server:
        return ApiResponse(code=404, message="MCP server not found", data=None)
    return ApiResponse.success(server)


@router.patch("/mcp-servers/{server_id}")
async def update_mcp_server(
    server_id: str, request: UpdateMCPServerRequest, db: AsyncSession = Depends(get_db)
):
    svc = MCPServerService(db)
    ok = await svc.update_server(server_id, request)
    await db.commit()
    if not ok:
        return ApiResponse(code=404, message="MCP server not found", data=None)
    return ApiResponse.success()


@router.delete("/mcp-servers/{server_id}")
async def delete_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    svc = MCPServerService(db)
    ok = await svc.delete_server(server_id)
    await db.commit()
    if not ok:
        return ApiResponse(code=404, message="MCP server not found", data=None)
    return ApiResponse.success()
