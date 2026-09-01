"""Message and message-read-receipt models."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.conversation import Conversation
    from app.models.user import User


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    FILE = "file"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message_type: Mapped[MessageType] = mapped_column(
        SAEnum(MessageType, native_enum=False), default=MessageType.TEXT
    )
    # Authenticated AES-256-GCM encrypted payload, stored as urlsafe base64.
    encrypted_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # For media messages, an attachment is linked.
    attachment_id: Mapped[int | None] = mapped_column(ForeignKey("attachments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(back_populates="messages")
    attachment: Mapped["Attachment | None"] = relationship(back_populates="message")
    receipts: Mapped[list["MessageReceipt"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class MessageReceipt(Base):
    __tablename__ = "message_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    message: Mapped["Message"] = relationship(back_populates="receipts")