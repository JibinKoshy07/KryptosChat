"""Conversation business logic."""
import logging
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.conversation import Conversation, ConversationMember
from app.models.message import Message
from app.models.message import MessageReceipt
from app.models.user import User
from app.schemas.conversation import ConversationOut, ConversationUser

logger = logging.getLogger(__name__)


async def get_conversation(db: AsyncSession, conversation_id: int) -> Conversation | None:
    return await db.get(Conversation, conversation_id)


async def get_conversation_with_members(db: AsyncSession, conversation_id: int) -> Conversation | None:
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
    )
    return await db.scalar(stmt)


async def get_member_ids(db: AsyncSession, conversation_id: int) -> list[int]:
    stmt = select(ConversationMember.user_id).where(ConversationMember.conversation_id == conversation_id)
    return list(await db.scalars(stmt))


async def is_member(db: AsyncSession, conversation_id: int, user_id: int) -> bool:
    stmt = select(ConversationMember).where(
        and_(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
    )
    return await db.scalar(stmt) is not None


async def ensure_member(db: AsyncSession, conversation_id: int, user_id: int) -> None:
    if not await is_member(db, conversation_id, user_id):
        raise ForbiddenError("You are not a member of this conversation")


async def direct_conversation(db: AsyncSession, user_a: int, user_b: int) -> Conversation | None:
    """Find an existing 1:1 conversation between two users."""
    from sqlalchemy.orm import aliased

    ma = aliased(ConversationMember)
    mb = aliased(ConversationMember)
    stmt = (
        select(Conversation.id)
        .join(ma, ma.conversation_id == Conversation.id)
        .where(ma.user_id == user_a)
        .join(mb, mb.conversation_id == Conversation.id)
        .where(mb.user_id == user_b)
    )
    conversation_id = await db.scalar(stmt)
    if conversation_id is None:
        return None
    return await get_conversation(db, conversation_id)


async def create_direct_conversation(db: AsyncSession, user_a: int, user_b: int) -> Conversation:
    existing = await direct_conversation(db, user_a, user_b)
    if existing:
        return existing
    conv = Conversation()
    db.add(conv)
    await db.flush()
    db.add_all(
        [
            ConversationMember(conversation_id=conv.id, user_id=user_a),
            ConversationMember(conversation_id=conv.id, user_id=user_b),
        ]
    )
    await db.commit()
    await db.refresh(conv)
    return conv


async def list_for_user(db: AsyncSession, user_id: int) -> list[ConversationOut]:
    """List the user's conversations, sorted by most recent activity."""
    stmt = (
        select(Conversation)
        .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
        .where(ConversationMember.user_id == user_id)
        .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
        .order_by(Conversation.updated_at.desc())
    )
    conversations = list(await db.scalars(stmt))
    results: list[ConversationOut] = []
    online_ids = await _online_user_ids(db)
    for conv in conversations:
        results.append(await _to_out(db, conv, user_id, online_ids))
    return results


async def get_for_user(db: AsyncSession, conversation_id: int, user_id: int) -> ConversationOut:
    conv = await get_conversation_with_members(db, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    await ensure_member(db, conversation_id, user_id)
    online_ids = await _online_user_ids(db)
    return await _to_out(db, conv, user_id, online_ids)


async def _online_user_ids(db: AsyncSession) -> set[int]:
    """Fetch online user ids from Redis; degrade to empty set if unavailable."""
    try:
        from app.services.presence import online_user_ids, get_redis

        rc = get_redis()
        return await online_user_ids(rc)
    except Exception:
        logger.warning("presence_redis_unavailable", extra={"extra_fields": {}})
        return set()


async def _to_out(db: AsyncSession, conv: Conversation, viewer_id: int, online_ids: set[int]) -> ConversationOut:
    members = [
        ConversationUser(
            id=m.user.id,
            username=m.user.username,
            display_name=m.user.display_name,
            is_active=m.user.is_active,
            last_seen_at=m.user.last_seen_at,
            online=m.user.id in online_ids,
        )
        for m in conv.members
        if m.user is not None and m.user.id != viewer_id
    ]
    # Last message + unread count for the viewer.
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv.id, Message.deleted_at.is_(None))
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    last_message = await db.scalar(stmt)
    unread = 0
    if last_message and last_message.sender_id != viewer_id:
        unread = await _unread_count(db, conv.id, viewer_id)
    last_message_out = None
    if last_message:
        last_message_out = {
            "id": last_message.id,
            "sender_id": last_message.sender_id,
            "message_type": last_message.message_type.value,
            "content": _preview_content(last_message),
            "created_at": last_message.created_at.isoformat() if last_message.created_at else None,
        }
    return ConversationOut(
        id=conv.id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        members=members,
        last_message=last_message_out,
        unread_count=unread,
    )


def _preview_content(message: Message) -> str:
    """Return a short plaintext-ish preview without decrypting (media only)."""
    if message.message_type.value == "text" and message.encrypted_content:
        try:
            from app.services.crypto import decrypt_message

            return decrypt_message(message.encrypted_content)[:120]
        except Exception:
            return ""
    labels = {"image": "📷 Photo", "video": "🎥 Video", "file": "📎 File"}
    return labels.get(message.message_type.value, "")


async def _unread_count(db: AsyncSession, conversation_id: int, user_id: int) -> int:
    """Count messages in a conversation the viewer has not read."""
    stmt = (
        select(func.count(Message.id))
        .where(
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
            Message.sender_id != user_id,
        )
    )
    total = await db.scalar(stmt) or 0
    read = await _read_count(db, conversation_id, user_id)
    return max(0, total - read)


async def _read_count(db: AsyncSession, conversation_id: int, user_id: int) -> int:
    stmt = (
        select(func.count(MessageReceipt.id))
        .join(Message, MessageReceipt.message_id == Message.id)
        .where(Message.conversation_id == conversation_id, MessageReceipt.user_id == user_id)
    )
    return await db.scalar(stmt) or 0


async def mark_messages_read(db: AsyncSession, conversation_id: int, user_id: int, message_ids: list[int]) -> list[int]:
    """Mark messages as read for the user; returns ids just marked read."""
    await ensure_member(db, conversation_id, user_id)
    stmt = (
        select(Message.id)
        .where(
            Message.conversation_id == conversation_id,
            Message.id.in_(message_ids),
            Message.sender_id != user_id,
        )
    )
    eligible = set(await db.scalars(stmt))
    newly_read: list[int] = []
    for mid in eligible:
        receipt = await db.scalar(
            select(MessageReceipt).where(
                MessageReceipt.message_id == mid,
                MessageReceipt.user_id == user_id,
            )
        )
        if receipt is None:
            db.add(MessageReceipt(message_id=mid, user_id=user_id, read_at=datetime.now(timezone.utc)))
            newly_read.append(mid)
        elif receipt.read_at is None:
            receipt.read_at = datetime.now(timezone.utc)
            newly_read.append(mid)
    await db.commit()
    return newly_read