"""User management business logic."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password, verify_password
from app.models.user import ROLE_ADMIN, ROLE_USER, User
from app.schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return await db.scalar(stmt)


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    if await get_user_by_username(db, data.username):
        raise ConflictError(f"Username '{data.username}' is already taken")
    user = User(
        username=data.username,
        display_name=data.display_name,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("user_created", extra={"extra_fields": {"user_id": user.id, "role": user.role}})
    return user


async def update_user(db: AsyncSession, user_id: int, data: UserUpdate) -> User:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.role is not None:
        user.role = data.role
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> None:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")
    await db.delete(user)
    await db.commit()
    logger.info("user_deleted", extra={"extra_fields": {"user_id": user_id}})


async def authenticate(db: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def list_users(db: AsyncSession, include_disabled: bool = True) -> list[User]:
    stmt = select(User).order_by(User.created_at)
    if not include_disabled:
        stmt = stmt.where(User.is_active.is_(True))
    return list(await db.scalars(stmt))