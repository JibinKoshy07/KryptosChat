"""Admin dashboard endpoints (admin-only)."""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.attachment import Attachment
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.admin import DashboardStats

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    total_users = await db.scalar(select(func.count(User.id))) or 0
    active_users = await db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    total_conversations = await db.scalar(select(func.count(Conversation.id))) or 0
    total_messages = await db.scalar(select(func.count(Message.id))) or 0
    storage_usage = await db.scalar(select(func.sum(Attachment.size))) or 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent_signups = [
        {"id": u.id, "username": u.username, "created_at": u.created_at.isoformat() if u.created_at else None}
        for u in await db.scalars(select(User).where(User.created_at >= cutoff).order_by(User.created_at.desc()).limit(5))
    ]
    recent_activity = [
        {"id": m.id, "conversation_id": m.conversation_id, "type": m.message_type.value, "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in await db.scalars(select(Message).where(Message.created_at >= cutoff).order_by(Message.created_at.desc()).limit(10))
    ]

    online = await _online_count()
    logger.info("admin_dashboard", extra={"extra_fields": {"admin_id": admin.id}})
    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        online_users=online,
        total_conversations=total_conversations,
        total_messages=total_messages,
        storage_usage_bytes=int(storage_usage or 0),
        recent_signups=list(recent_signups),
        recent_activity=list(recent_activity),
    )


async def _online_count() -> int:
    try:
        from app.services.presence import get_redis, online_count

        return await online_count(get_redis())
    except Exception:
        return 0