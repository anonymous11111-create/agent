from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class CreateDocumentRequest(BaseModel):
    kbId: str
    filename: Optional[str] = None
    filetype: Optional[str] = None
    size: Optional[int] = None


class UpdateDocumentRequest(BaseModel):
    filename: Optional[str] = None


class DocumentVO(BaseModel):
    id: str
    kbId: str
    filename: Optional[str] = None
    filetype: Optional[str] = None
    size: Optional[int] = None
    metadata: Optional[dict] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class CreateDocumentResponse(BaseModel):
    documentId: str


class GetDocumentsResponse(BaseModel):
    documents: List[DocumentVO]
