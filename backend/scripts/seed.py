"""Create the initial administrator account from environment variables.

Run::
    cd backend
    python -m scripts.seed
"""
import asyncio
import logging
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.db.session import async_session_factory, engine
from app.models.user import ROLE_ADMIN, User
from app.services import users

setup_logging("INFO")
logger = logging.getLogger(__name__)


async def seed() -> int:
    async with async_session_factory() as db:
        username = settings.admin_username or "admin"
        password = settings.admin_password
        display_name = settings.admin_display_name or "Administrator"
        if not password:
            logger.error("ADMIN_PASSWORD must be set to seed an admin")
            return 1

        existing = await users.get_user_by_username(db, username)
        if existing:
            logger.info("admin_already_exists", extra={"extra_fields": {"username": username}})
            return 0

        user = User(
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            role=ROLE_ADMIN,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        logger.info("admin_created", extra={"extra_fields": {"username": username}})
        return 0


def main() -> None:
    code = asyncio.run(seed())
    asyncio.run(engine.dispose())
    sys.exit(code)


if __name__ == "__main__":
    main()