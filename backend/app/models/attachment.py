"""Attachment (media/file) model.

``encrypted_storage_key`` is the logical key/path used to locate the
encrypted blob on the storage backend. ``storage_backend`` records which
backend wrote the blob so it can be read back correctly.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.message import Message


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), index=True)
    encrypted_storage_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    storage_backend: Mapped[str] = mapped_column(String(32), default="local")
    original_filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(BigInteger)
    # Encryption metadata (e.g. storage format version, key derivation salt).
    encryption_metadata: Mapped[str] = mapped_column(String(2048), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped["Message"] = relationship(back_populates="attachment")