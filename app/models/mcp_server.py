import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MCPServerConfig(Base):
    __tablename__ = "mcp_server_config"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    command: Mapped[str] = mapped_column(String(500), nullable=False)
    args: Mapped[list | None] = mapped_column(JSON, default=list)
    env: Mapped[dict | None] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
