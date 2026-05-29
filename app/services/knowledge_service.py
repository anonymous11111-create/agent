import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.models.document import Document
from app.models.chunk import ChunkBgeM3
from app.schemas.knowledge_base import (
    CreateKnowledgeBaseRequest,
    KnowledgeBaseVO,
    UpdateKnowledgeBaseRequest,
)
from app.schemas.document import DocumentVO, CreateDocumentResponse
from app.rag.embedder import embed_text
from app.rag.service import rag_service
from app.utils.chinese_tokenizer import tokenize
from app.config import settings

logger = logging.getLogger(__name__)

# Simple markdown section parser
import re

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class _MarkdownSection:
    def __init__(self, title: str, content: str):
        self.title = title
        self.content = content


def _parse_markdown(md_text: str) -> list[_MarkdownSection]:
    """Split markdown by headings, return list of (title, content) sections."""
    sections = []
    parts = _HEADING_RE.split(md_text)

    # parts: [before_first_heading, hashes, title, content, hashes, title, ...]
    if len(parts) < 4:
        # No headings found, treat whole as one section
        if md_text.strip():
            sections.append(_MarkdownSection("Document", md_text.strip()))
        return sections

    # Skip text before first heading
    i = 1
    while i + 2 < len(parts):
        level = parts[i]
        title = parts[i + 1].strip()
        body = parts[i + 2]
        # Extract content until next heading
        next_heading = _HEADING_RE.search(body)
        if next_heading:
            content = body[: next_heading.start()].strip()
            # Put the rest back
            parts[i + 2] = body[next_heading.start():]
        else:
            content = body.strip()
            i += 3

        if title:
            sections.append(_MarkdownSection(title, content))
        else:
            i += 3

    return sections


def _chunk_section(title: str, content: str, max_size: int = 500, overlap: int = 100):
    """Split a section into chunks, each prefixed with title."""
    full_text = title + "\n" + content
    if len(full_text) <= max_size:
        return [(full_text, content)]

    available = max_size - len(title) - 1
    if available <= 0:
        return [(title, content)]

    chunks = []
    start = 0
    while start < len(content):
        end = min(start + available, len(content))
        segment = content[start:end]
        chunks.append((title + "\n" + segment, segment))
        start = end - overlap
        if start >= end:
            break
    return chunks


class KnowledgeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- Knowledge Base CRUD ----

    async def list_knowledge_bases(self) -> list[KnowledgeBaseVO]:
        result = await self.db.execute(select(KnowledgeBase))
        kbs = result.scalars().all()
        return [self._kb_to_vo(kb) for kb in kbs]

    async def create_knowledge_base(self, request: CreateKnowledgeBaseRequest) -> str:
        kb = KnowledgeBase(name=request.name, description=request.description)
        self.db.add(kb)
        await self.db.flush()
        return str(kb.id)

    async def delete_knowledge_base(self, kb_id: str):
        await self.db.execute(
            delete(KnowledgeBase).where(KnowledgeBase.id == uuid.UUID(kb_id))
        )
        await self.db.flush()

    async def update_knowledge_base(self, kb_id: str, request: UpdateKnowledgeBaseRequest):
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == uuid.UUID(kb_id))
        )
        kb = result.scalar_one_or_none()
        if not kb:
            raise ValueError(f"KB not found: {kb_id}")
        if request.name is not None:
            kb.name = request.name
        if request.description is not None:
            kb.description = request.description
        kb.updated_at = datetime.now()
        await self.db.flush()

    # ---- Document CRUD ----

    async def list_documents(self) -> list[DocumentVO]:
        result = await self.db.execute(select(Document))
        docs = result.scalars().all()
        return [self._doc_to_vo(d) for d in docs]

    async def list_documents_by_kb(self, kb_id: str) -> list[DocumentVO]:
        result = await self.db.execute(
            select(Document).where(Document.kb_id == uuid.UUID(kb_id))
        )
        return [self._doc_to_vo(d) for d in result.scalars().all()]

    async def upload_document(
        self, kb_id: str, filename: str, file_content: bytes
    ) -> str:
        """Upload a document: save file, create DB record, process chunks."""
        filetype = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"
        file_size = len(file_content)

        # Create document record
        doc = Document(
            kb_id=uuid.UUID(kb_id),
            filename=filename,
            filetype=filetype,
            size=file_size,
        )
        self.db.add(doc)
        await self.db.flush()
        doc_id = str(doc.id)

        # Save file to disk
        storage_path = Path(settings.DOCUMENT_STORAGE_PATH) / kb_id / doc_id
        storage_path.mkdir(parents=True, exist_ok=True)
        file_path = storage_path / filename
        file_path.write_bytes(file_content)

        # Update metadata
        doc.metadata_ = {"filePath": str(file_path)}
        doc.updated_at = datetime.now()
        await self.db.flush()

        # Process markdown
        if filetype in ("md", "markdown"):
            await self._process_markdown(kb_id, doc_id, file_content.decode("utf-8"))

        return doc_id

    async def delete_document(self, document_id: str):
        doc_result = await self.db.execute(
            select(Document).where(Document.id == uuid.UUID(document_id))
        )
        doc = doc_result.scalar_one_or_none()
        if doc and doc.metadata_:
            meta = doc.metadata_ if isinstance(doc.metadata_, dict) else json.loads(doc.metadata_)
            file_path = meta.get("filePath")
            if file_path:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning("Failed to delete file: %s", e)

        # Delete chunks
        await self.db.execute(
            delete(ChunkBgeM3).where(ChunkBgeM3.doc_id == uuid.UUID(document_id))
        )
        await self.db.execute(
            delete(Document).where(Document.id == uuid.UUID(document_id))
        )
        await self.db.flush()

    async def _process_markdown(self, kb_id: str, doc_id: str, md_text: str):
        """Parse markdown, chunk, embed, and store."""
        try:
            sections = _parse_markdown(md_text)
            chunk_count = 0
            now = datetime.now()

            for section in sections:
                if not section.title.strip():
                    continue

                content = section.content or ""
                chunks = _chunk_section(
                    section.title,
                    content,
                    max_size=settings.RAG_CHUNK_MAX_SIZE,
                    overlap=settings.RAG_CHUNK_OVERLAP,
                )

                for i, (embed_text_str, display_content) in enumerate(chunks):
                    embedding = await embed_text(embed_text_str)
                    metadata = {
                        "title": section.title,
                        "chunkIndex": i,
                        "chunkTotal": len(chunks),
                    }
                    content_search = tokenize(display_content)

                    chunk = ChunkBgeM3(
                        kb_id=uuid.UUID(kb_id),
                        doc_id=uuid.UUID(doc_id),
                        content=display_content,
                        content_search=content_search,
                        metadata_=metadata,
                        embedding=embedding,
                        created_at=now,
                        updated_at=now,
                    )
                    self.db.add(chunk)
                    chunk_count += 1

            await self.db.flush()
            logger.info("Processed document %s: %d chunks", doc_id, chunk_count)

        except Exception as e:
            logger.error("Failed to process markdown: %s", e)

    # ---- Helpers ----

    def _kb_to_vo(self, kb: KnowledgeBase) -> KnowledgeBaseVO:
        meta = kb.metadata_
        return KnowledgeBaseVO(
            id=str(kb.id),
            name=kb.name,
            description=kb.description,
            metadata=meta,
            createdAt=kb.created_at,
            updatedAt=kb.updated_at,
        )

    def _doc_to_vo(self, doc: Document) -> DocumentVO:
        meta = doc.metadata_
        return DocumentVO(
            id=str(doc.id),
            kbId=str(doc.kb_id),
            filename=doc.filename,
            filetype=doc.filetype,
            size=doc.size,
            metadata=meta,
            createdAt=doc.created_at,
            updatedAt=doc.updated_at,
        )
