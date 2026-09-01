"""User management endpoints.

Only authenticated users can read their own profile and list permitted
contacts. Admin-only actions (create/update/delete users) live here and are
protected by :func:`require_admin`.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("", response_model=list[UserOut])
async def list_users(
    current_user: User = Depends(get_current_user),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await users.list_users(db)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await users.create_user(db, data)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await users.update_user(db, user_id, data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    await users.delete_user(db, user_id)
    return None


@router.post("/{user_id}/disable", response_model=UserOut)
async def disable_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await users.update_user(db, user_id, UserUpdate(is_active=False))


@router.post("/{user_id}/enable", response_model=UserOut)
async def enable_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await users.update_user(db, user_id, UserUpdate(is_active=True))


@router.post("/{user_id}/reset-password", response_model=UserOut)
async def reset_password(
    user_id: int,
    new_password: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await users.update_user(db, user_id, UserUpdate(password=new_password))