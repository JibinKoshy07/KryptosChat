"""Authentication tests."""
import pytest

from app.services.auth import check_login_throttle, record_failed_login


async def test_login_success(client, admin_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "adminpass123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["role"] == "admin"
    assert "krypte_refresh" in resp.cookies


async def test_login_wrong_password(client, admin_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrongpass"},
    )
    assert resp.status_code == 401


async def test_login_unknown_user(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "whatever"},
    )
    assert resp.status_code == 401


async def test_me(client, tokens):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "user1"


async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_login_throttle(fakeredis):
    fake = fakeredis  # the fixture yields the shared Redis
    for i in range(5):
        await record_failed_login(fake, "attack")
    from app.core.exceptions import RateLimitError

    with pytest.raises(RateLimitError):
        await check_login_throttle(fake, "attack")