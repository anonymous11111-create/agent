import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Float, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ToolCallLog(Base):
    __tablename__ = "tool_call_log"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_session.id", ondelete="CASCADE"))
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent.id", ondelete="CASCADE"))
    tool_name: Mapped[str] = mapped_column(String(100))
    tool_call_id: Mapped[str] = mapped_column(String(100))
    arguments: Mapped[str | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))  # success/fail/timeout/blocked/rejected
    duration_ms: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    result_preview: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
