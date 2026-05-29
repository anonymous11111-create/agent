import uuid
from datetime import datetime

from sqlalchemy import String, BigInteger, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_base.id"))
    filename: Mapped[str | None] = mapped_column(String(500))
    filetype: Mapped[str | None] = mapped_column(String(50))
    size: Mapped[int | None] = mapped_column(BigInteger)
    metadata_: Mapped[str | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
