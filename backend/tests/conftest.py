"""Shared test fixtures.

The test suite runs against an ephemeral SQLite database (aiosqlite) and a
fake Redis (fakeredis), so no external services are required. Set
``KRIPTE_TEST_DATABASE_URL=sqlite+aiosqlite:///:memory:`` etc. to override.
"""
import asyncio
import base64
import os
import secrets
import tempfile
from collections.abc import AsyncGenerator

import fakeredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# --- Environment (must be set before app modules are imported) ---------------
_TMP_DB = tempfile.mktemp(suffix=".krypte_test.db")
os.environ.setdefault("JWT_SECRET", secrets.token_urlsafe(48))
os.environ.setdefault("SESSION_SECRET", secrets.token_urlsafe(48))
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "1")
os.environ.setdefault(
    "DATABASE_URL", f"sqlite+aiosqlite:///{_TMP_DB}"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("MEDIA_STORAGE_BACKEND", "local")
os.environ.setdefault("MEDIA_LOCAL_PATH", tempfile.mkdtemp(suffix=".krypte_media"))
os.environ.setdefault("CORS_ORIGINS", "http://testserver")
for name in ("MESSAGE_ENCRYPTION_KEY_BASE64", "MESSAGE_MASTER_KEY_BASE64",
             "MEDIA_KDF_MASTER_KEY_BASE64", "MEDIA_KDF_AUTH_KEY_BASE64"):
    os.environ.setdefault(name, base64.b64encode(secrets.token_bytes(32)).decode())


import app.main as main_module  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine, async_session_factory  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _fakeredis(monkeypatch):
    """Replace all ``get_redis`` entry points with a shared fake Redis."""
    rc = fakeredis.FakeAsyncRedis(decode_responses=True)

    def _fake_get_redis():
        return rc

    monkeypatch.setattr("app.services.presence.get_redis", _fake_get_redis)
    monkeypatch.setattr("app.api.deps.get_redis", _fake_get_redis)
    monkeypatch.setattr("app.main.presence_redis", _fake_get_redis)
    await rc.flushdb()
    yield rc
    await rc.aclose()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator:
    """A clean database session for direct service tests."""
    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _prepare_db():
    """Ensure tables exist and are empty per test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator:
    """An HTTPX async client backed by the FastAPI ASGI app."""
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def admin_user(db):
    """A single seeded admin user."""
    from app.schemas.user import UserCreate
    from app.services import users

    return await users.create_user(
        db, UserCreate(username="admin", display_name="Admin", password="adminpass123", role="admin")
    )


@pytest_asyncio.fixture
async def normal_user(db):
    """A single seeded normal user."""
    from app.schemas.user import UserCreate
    from app.services import users

    return await users.create_user(
        db, UserCreate(username="user1", display_name="User One", password="userpass123", role="user")
    )


@pytest_asyncio.fixture
async def tokens(client, admin_user, normal_user):
    """Return access tokens for both seeded users."""
    async def _login(username, password):
        resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return {
        "admin": await _login("admin", "adminpass123"),
        "user1": await _login("user1", "userpass123"),
    }