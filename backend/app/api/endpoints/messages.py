"""Message endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.message import MessageCreate, MessageOut, MessagePage
from app.services import conversations, messages

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/{conversation_id}", response_model=MessagePage)
async def list_messages(
    conversation_id: int,
    before: int | None = Query(default=None),
    limit: int = Query(default=40, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows, has_more = await messages.list_messages(db, conversation_id, current_user.id, before, limit)
    items = [await messages.to_out(db, m, current_user.id) for m in rows]
    next_cursor = items[-1].id if rows and has_more else None
    return MessagePage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.post("/{conversation_id}", response_model=MessageOut, status_code=201)
async def send_message(
    conversation_id: int,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message = await messages.create_message(db, conversation_id, current_user.id, data)
    return await messages.to_out(db, message, current_user.id)


@router.delete("/{conversation_id}/{message_id}", status_code=204)
async def delete_message(
    conversation_id: int,
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await conversations.ensure_member(db, conversation_id, current_user.id)
    await messages.soft_delete(db, message_id, current_user.id)