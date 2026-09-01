"""Message business logic."""
import logging
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.attachment import Attachment
from app.models.message import Message, MessageReceipt, MessageType
from app.schemas.message import MessageCreate, MessageOut
from app.services import conversations
from app.services.crypto import decrypt_message, encrypt_message

logger = logging.getLogger(__name__)


async def create_message(
    db: AsyncSession,
    conversation_id: int,
    sender_id: int,
    data: MessageCreate,
    attachment_id: int | None = None,
) -> Message:
    """Create and persist a message. For media messages, ``content`` may be
    empty and an attachment is supplied separately (created after upload, e.g.
    through the WebSocket handshake end-to-end)."""
    await conversations.ensure_member(db, conversation_id, sender_id)
    if data.message_type in (MessageType.TEXT,) and not data.content:
        raise BadRequestError("Message content must not be empty")

    encrypted = encrypt_message(data.content) if data.content else None
    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        message_type=data.message_type,
        encrypted_content=encrypted,
        attachment_id=attachment_id,
    )
    db.add(message)
    # Mark the conversation as recently updated.
    conv = await conversations.get_conversation(db, conversation_id)
    if conv is not None:
        conv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(message)
    return message


async def get_message(db: AsyncSession, message_id: int) -> Message | None:
    return await db.get(Message, message_id)


async def list_messages(
    db: AsyncSession,
    conversation_id: int,
    viewer_id: int,
    cursor_before: int | None = None,
    limit: int = 40,
) -> tuple[list[Message], bool]:
    """Return (messages, has_more) with cursor-based pagination (newest first
    internal, returned oldest-first to the client)."""
    limit = max(1, min(limit, 100))
    await conversations.ensure_member(db, conversation_id, viewer_id)
    stmt = select(Message).where(
        Message.conversation_id == conversation_id,
        Message.deleted_at.is_(None),
    )
    if cursor_before is not None:
        stmt = stmt.where(Message.id < cursor_before)
    stmt = stmt.order_by(Message.id.desc()).limit(limit + 1)
    rows = list(await db.scalars(stmt))
    has_more = len(rows) > limit
    rows = rows[:limit]
    # Return oldest-first.
    rows.reverse()
    return rows, has_more


async def to_out(
    db: AsyncSession,
    message: Message,
    viewer_id: int,
) -> MessageOut:
    content = ""
    if message.message_type == MessageType.TEXT and message.encrypted_content:
        try:
            content = decrypt_message(message.encrypted_content)
        except Exception:
            content = "🔒 [unable to decrypt]"
    attachment = None
    if message.attachment_id is not None:
        att = await db.get(Attachment, message.attachment_id)
        if att is not None:
            from app.schemas.media import AttachmentOut

            attachment = AttachmentOut(
                id=att.id,
                message_id=att.message_id,
                original_filename=att.original_filename,
                mime_type=att.mime_type,
                size=att.size,
                created_at=att.created_at,
            ).model_dump(mode="json")
    receipt = await _receipt_for(db, message.id, viewer_id)
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        message_type=message.message_type,
        content=content,
        attachment=attachment,
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        delivered=bool(receipt and receipt.delivered_at),
        read=bool(receipt and receipt.read_at),
    )


async def _receipt_for(db: AsyncSession, message_id: int, user_id: int) -> MessageReceipt | None:
    stmt = select(MessageReceipt).where(
        MessageReceipt.message_id == message_id,
        MessageReceipt.user_id == user_id,
    )
    return await db.scalar(stmt)


async def mark_delivered(db: AsyncSession, conversation_id: int, user_id: int, message_ids: list[int]) -> list[int]:
    """Mark messages as delivered for the user; returns ids just marked."""
    await conversations.ensure_member(db, conversation_id, user_id)
    stmt = select(Message.id).where(
        Message.conversation_id == conversation_id,
        Message.id.in_(message_ids),
        Message.sender_id != user_id,
    )
    eligible = set(await db.scalars(stmt))
    newly: list[int] = []
    for mid in eligible:
        receipt = await _receipt_for(db, mid, user_id)
        if receipt is None:
            db.add(MessageReceipt(message_id=mid, user_id=user_id, delivered_at=datetime.now(timezone.utc)))
            newly.append(mid)
        elif receipt.delivered_at is None:
            receipt.delivered_at = datetime.now(timezone.utc)
            newly.append(mid)
    await db.commit()
    return newly


async def soft_delete(db: AsyncSession, message_id: int, user_id: int) -> None:
    message = await get_message(db, message_id)
    if not message:
        raise NotFoundError("Message not found")
    if message.sender_id != user_id:
        raise ForbiddenError("You can only delete your own messages")
    message.deleted_at = datetime.now(timezone.utc)
    await db.commit()