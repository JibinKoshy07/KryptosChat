"""Shared FastAPI dependencies: authentication, authorization, rate limiting."""
import logging

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, RateLimitError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import ROLE_ADMIN, User
from app.services import users

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 120


def get_redis() -> Redis:
    from app.services.presence import get_redis

    return get_redis()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Not authenticated")
    token = credentials.credentials
    payload = decode_token(token, "access")
    if payload is None:
        raise UnauthorizedError("Invalid or expired access token")
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise UnauthorizedError("Invalid token subject")
    user = await users.get_user_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise ForbiddenError("Account disabled")
    return user


async def get_optional_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User | None:
    """Resolve the user from the Authorization header, or return ``None``.

    Used where a request is reachable both via an ``Authorization`` header and
    a ``?token=`` query param (e.g. in-browser media download). The caller is
    responsible for rejecting unauthenticated access.
    """
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials, "access")
    if payload is None:
        return None
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        return None
    return await users.get_user_by_id(db, user_id)


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != ROLE_ADMIN:
        raise ForbiddenError("Admin privileges required")
    return current_user


async def rate_limit_requests(request: Request, rc: Redis = Depends(get_redis)) -> None:
    """Simple fixed-window rate limiter keyed by client IP + path."""
    key = f"rl:{request.client.host if request.client else 'unknown'}:{request.url.path}"
    try:
        count = await rc.incr(key)
        if count == 1:
            await rc.expire(key, RATE_LIMIT_WINDOW)
        if count > RATE_LIMIT_MAX:
            raise RateLimitError("Too many requests")
    except RateLimitError:
        raise
    except Exception:
        # Redis unavailable: fail open rather than disrupting the app.
        logger.warning("rate_limit_redis_unavailable", extra={"extra_fields": {}})