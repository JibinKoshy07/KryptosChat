"""Message schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.message import MessageType


class MessageCreate(BaseModel):
    content: str = Field(default="", max_length=10000)
    message_type: MessageType = MessageType.TEXT
    temp_id: str | None = Field(default=None, description="Client-generated id for deduplication")


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    message_type: MessageType
    content: str = ""
    attachment: Optional[dict] = None
    created_at: datetime
    edited_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    # Delivery/read state relative to the requesting user.
    delivered: bool = False
    read: bool = False


class MessagePage(BaseModel):
    items: list[MessageOut]
    next_cursor: Optional[int] = None
    has_more: bool = False


class ReadReceiptRequest(BaseModel):
    message_ids: list[int] = Field(min_length=1)