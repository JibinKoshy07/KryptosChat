"""Health check endpoint."""
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", status_code=status.HTTP_200_OK)
async def health(db: AsyncSession = Depends(get_db)):
    # Verify DB connectivity.
    await db.execute(text("SELECT 1"))
    try:
        from app.services.presence import get_redis

        redis = get_redis()
        await redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok", "database": "ok", "redis": "ok" if redis_ok else "unavailable"}