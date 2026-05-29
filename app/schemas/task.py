from typing import Optional, List
from pydantic import BaseModel


class CreateTaskRequest(BaseModel):
    subject: str
    description: Optional[str] = ""
    priority: Optional[str] = "medium"
    tags: Optional[List[str]] = []
    sessionId: Optional[str] = None


class UpdateTaskRequest(BaseModel):
    subject: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None
    progress: Optional[int] = None
    addBlockedBy: Optional[List[int]] = None
    addBlocks: Optional[List[int]] = None


class TaskVO(BaseModel):
    id: int
    subject: str
    description: Optional[str] = ""
    status: str
    priority: Optional[str] = "medium"
    blockedBy: List[int] = []
    blocks: List[int] = []
    owner: Optional[str] = ""
    tags: List[str] = []
    progress: Optional[int] = 0
    sessionId: Optional[str] = None
    agentId: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class GetTasksResponse(BaseModel):
    tasks: List[TaskVO]
