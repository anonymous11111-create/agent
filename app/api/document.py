from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import ApiResponse
from app.schemas.document import GetDocumentsResponse, CreateDocumentResponse
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents")
async def get_documents(db: AsyncSession = Depends(get_db)):
    svc = KnowledgeService(db)
    docs = await svc.list_documents()
    return ApiResponse.success(GetDocumentsResponse(documents=docs))


@router.get("/documents/kb/{kb_id}")
async def get_documents_by_kb(kb_id: str, db: AsyncSession = Depends(get_db)):
    svc = KnowledgeService(db)
    docs = await svc.list_documents_by_kb(kb_id)
    return ApiResponse.success(GetDocumentsResponse(documents=docs))


@router.post("/documents/upload")
async def upload_document(
    kbId: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    svc = KnowledgeService(db)
    content = await file.read()
    doc_id = await svc.upload_document(kbId, file.filename or "unknown", content)
    await db.commit()
    return ApiResponse.success(CreateDocumentResponse(documentId=doc_id))


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    svc = KnowledgeService(db)
    await svc.delete_document(document_id)
    await db.commit()
    return ApiResponse.success()
