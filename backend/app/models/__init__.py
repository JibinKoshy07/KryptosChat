"""Import all models so they are registered with the declarative base."""
from app.models.attachment import Attachment
from app.models.conversation import Conversation, ConversationMember
from app.models.message import Message, MessageReceipt, MessageType
from app.models.user import ROLE_ADMIN, ROLE_USER, User

__all__ = [
    "Attachment",
    "Conversation",
    "ConversationMember",
    "Message",
    "MessageReceipt",
    "MessageType",
    "ROLE_ADMIN",
    "ROLE_USER",
    "User",
]