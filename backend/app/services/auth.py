"""Authentication business logic: login, refresh, logout."""
import logging
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import RateLimitError, UnauthorizedError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.services import users

logger = logging.getLogger(__name__)

LOCKOUT_PREFIX = "auth:lockout"
FAIL_PREFIX = "auth:fail"


async def check_login_throttle(rc: Redis, username: str) -> None:
    """Enforce a per-username lockout after repeated failures."""
    lockout_key = f"{LOCKOUT_PREFIX}:{username}"
    if await rc.exists(lockout_key):
        ttl = await rc.ttl(lockout_key)
        raise RateLimitError(f"Too many failed attempts. Try again in {max(ttl, 1)}s.")


async def record_failed_login(rc: Redis, username: str) -> None:
    fail_key = f"{FAIL_PREFIX}:{username}"
    count = await rc.incr(fail_key)
    await rc.expire(fail_key, settings.login_lockout_minutes * 60)
    if count >= settings.login_max_attempts:
        lockout_key = f"{LOCKOUT_PREFIX}:{username}"
        await rc.set(lockout_key, 1, ex=settings.login_lockout_minutes * 60)
        await rc.delete(fail_key)
        logger.warning("login_lockout", extra={"extra_fields": {"username": username}})


async def clear_failures(rc: Redis, username: str) -> None:
    await rc.delete(f"{FAIL_PREFIX}:{username}")
    await rc.delete(f"{LOCKOUT_PREFIX}:{username}")


async def login(db: AsyncSession, rc: Redis, username: str, password: str) -> User:
    """Authenticate a user and return it, or raise ``UnauthorizedError``."""
    await check_login_throttle(rc, username)
    user = await users.authenticate(db, username, password)
    if user is None:
        await record_failed_login(rc, username)
        raise UnauthorizedError("Invalid username or password")
    await clear_failures(rc, username)
    user.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("login_success", extra={"extra_fields": {"user_id": user.id, "role": user.role}})
    return user


def issue_token_pair(user_id: int, now: datetime | None = None) -> tuple[str, str]:
    """Return (access_token, refresh_token)."""
    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)
    return access, refresh


def set_refresh_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        settings.cookie_name,
        refresh_token,
        max_age=settings.cookie_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure or settings.use_https,
        samesite="lax",
        path="/api/v1",
    )


def clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        settings.cookie_name,
        path="/api/v1",
    )