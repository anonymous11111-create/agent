from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import ApiResponse
from app.schemas.knowledge_base import (
    CreateKnowledgeBaseRequest,
    UpdateKnowledgeBaseRequest,
    GetKnowledgeBasesResponse,
    CreateKnowledgeBaseResponse,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api", tags=["knowledge-bases"])


@router.get("/knowledge-bases")
async def get_knowledge_bases(db: AsyncSession = Depends(get_db)):
    svc = KnowledgeService(db)
    kbs = await svc.list_knowledge_bases()
    return ApiResponse.success(GetKnowledgeBasesResponse(knowledgeBases=kbs))


@router.post("/knowledge-bases")
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest, db: AsyncSession = Depends(get_db)
):
    svc = KnowledgeService(db)
    kb_id = await svc.create_knowledge_base(request)
    await db.commit()
    return ApiResponse.success(CreateKnowledgeBaseResponse(knowledgeBaseId=kb_id))


@router.delete("/knowledge-bases/{knowledge_base_id}")
async def delete_knowledge_base(
    knowledge_base_id: str, db: AsyncSession = Depends(get_db)
):
    svc = KnowledgeService(db)
    await svc.delete_knowledge_base(knowledge_base_id)
    await db.commit()
    return ApiResponse.success()


@router.patch("/knowledge-bases/{knowledge_base_id}")
async def update_knowledge_base(
    knowledge_base_id: str,
    request: UpdateKnowledgeBaseRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = KnowledgeService(db)
    await svc.update_knowledge_base(knowledge_base_id, request)
    await db.commit()
    return ApiResponse.success()
