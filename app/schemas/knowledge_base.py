from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    description: Optional[str] = None


class UpdateKnowledgeBaseRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class KnowledgeBaseVO(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    metadata: Optional[dict] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class CreateKnowledgeBaseResponse(BaseModel):
    knowledgeBaseId: str


class GetKnowledgeBasesResponse(BaseModel):
    knowledgeBases: List[KnowledgeBaseVO]
