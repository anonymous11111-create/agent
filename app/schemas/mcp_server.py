from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class CreateMCPServerRequest(BaseModel):
    name: str
    command: str
    args: Optional[List[str]] = None
    env: Optional[dict] = None
    enabled: Optional[bool] = True
    description: Optional[str] = None


class UpdateMCPServerRequest(BaseModel):
    name: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[dict] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class MCPServerVO(BaseModel):
    id: str
    name: str
    command: str
    args: Optional[List[str]] = None
    env: Optional[dict] = None
    enabled: bool
    description: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class CreateMCPServerResponse(BaseModel):
    serverId: str


class GetMCPServersResponse(BaseModel):
    servers: List[MCPServerVO]
