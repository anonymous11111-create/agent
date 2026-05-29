from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ChatOptions(BaseModel):
    temperature: float = 0.7
    topP: float = 1.0
    messageLength: int = 10


class CreateAgentRequest(BaseModel):
    name: str
    description: Optional[str] = None
    systemPrompt: Optional[str] = None
    model: Optional[str] = "deepseek-chat"
    allowedTools: Optional[List[str]] = None
    allowedKbs: Optional[List[str]] = None
    chatOptions: Optional[ChatOptions] = None


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    systemPrompt: Optional[str] = None
    model: Optional[str] = None
    allowedTools: Optional[List[str]] = None
    allowedKbs: Optional[List[str]] = None
    chatOptions: Optional[ChatOptions] = None


class AgentVO(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    systemPrompt: Optional[str] = None
    model: Optional[str] = None
    allowedTools: Optional[List[str]] = None
    allowedKbs: Optional[List[str]] = None
    chatOptions: Optional[ChatOptions] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class CreateAgentResponse(BaseModel):
    agentId: str


class GetAgentsResponse(BaseModel):
    agents: List[AgentVO]
