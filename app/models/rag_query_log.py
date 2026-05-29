import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Float, Integer, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RagQueryLog(Base):
    __tablename__ = "rag_query_log"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_session.id", ondelete="CASCADE"))
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent.id", ondelete="CASCADE"))
    knowledge_base_id: Mapped[str] = mapped_column(String(36))
    query: Mapped[str] = mapped_column(Text)
    kb_name: Mapped[str | None] = mapped_column(String(255))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    vector_count: Mapped[int] = mapped_column(Integer, default=0)
    keyword_count: Mapped[int] = mapped_column(Integer, default=0)
    top_scores: Mapped[str | None] = mapped_column(JSON)
    embed_ms: Mapped[float | None] = mapped_column(Float)
    retrieval_ms: Mapped[float | None] = mapped_column(Float)
    fusion_ms: Mapped[float | None] = mapped_column(Float)
    total_ms: Mapped[float | None] = mapped_column(Float)
    feedback: Mapped[str | None] = mapped_column(String(20))  # "positive" / "negative"
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
