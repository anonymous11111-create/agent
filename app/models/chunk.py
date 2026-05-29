import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.models.base import Base


class ChunkBgeM3(Base):
    __tablename__ = "chunk_bge_m3"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_base.id"))
    doc_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document.id"))
    content: Mapped[str | None] = mapped_column(Text)
    content_search: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[str | None] = mapped_column("metadata", JSON)
    embedding = mapped_column(Vector(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
