"""Authentication endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis, rate_limit_requests
from app.core.auth_cookie import read_refresh_cookie
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserSummary
from app.schemas.user import MeResponse
from app.services import auth as auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit_requests)])
async def login(
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    rc: Redis = Depends(get_redis),
):
    user = await auth_service.login(db, rc, data.username, data.password)
    access, refresh = auth_service.issue_token_pair(user.id)
    auth_service.set_refresh_cookie(response, refresh)
    logger.info("auth_login", extra={"extra_fields": {"user_id": user.id}})
    return TokenResponse(access_token=access, user=_user_summary(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    refresh_token = read_refresh_cookie(request)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")
    payload = decode_token(refresh_token, "refresh")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or missing")
    access, new_refresh = auth_service.issue_token_pair(user.id)
    auth_service.set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access, user=_user_summary(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    auth_service.clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user