"""Conversation schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ConversationUser(BaseModel):
    """A member of a conversation, with presence information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    is_active: bool
    last_seen_at: Optional[datetime] = None
    online: bool = False


class ConversationCreate(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=1)  # 1:1 chat for now


class ConversationOut(BaseModel):
    """A conversation summary for the sidebar."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    members: list[ConversationUser]
    last_message: Optional[dict] = None
    unread_count: int = 0


class ConversationDetail(BaseModel):
    """A conversation with its message list (paginated)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    members: list[ConversationUser]
    messages: list[dict] = []