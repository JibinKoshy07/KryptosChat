"""Conversation endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.conversation import ConversationCreate, ConversationOut
from app.services import conversations

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await conversations.list_for_user(db, current_user.id)


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not data.user_ids or len(data.user_ids) != 1:
        raise BadRequestError("Provide exactly one other user id")
    other_id = data.user_ids[0]
    if other_id == current_user.id:
        raise BadRequestError("Cannot start a conversation with yourself")
    from app.services import users

    other = await users.get_user_by_id(db, other_id)
    if other is None:
        raise NotFoundError("User not found")
    if not other.is_active:
        raise BadRequestError("That user is disabled")
    conv = await conversations.create_direct_conversation(db, current_user.id, other_id)
    return await conversations.get_for_user(db, conv.id, current_user.id)


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await conversations.get_for_user(db, conversation_id, current_user.id)