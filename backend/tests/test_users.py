"""User management and authorization tests."""
import pytest


async def test_admin_creates_user(client, tokens):
    resp = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
        json={"username": "bob", "display_name": "Bob", "password": "bobpass123", "role": "user"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["username"] == "bob"


async def test_non_admin_cannot_create_user(client, tokens):
    resp = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        json={"username": "mallory", "display_name": "M", "password": "pass12345", "role": "user"},
    )
    assert resp.status_code == 403


async def test_create_duplicate_user_conflicts(client, admin_user, tokens):
    await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
        json={"username": "dup", "display_name": "D", "password": "pass12345", "role": "user"},
    )
    resp = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
        json={"username": "dup", "display_name": "D", "password": "pass12345", "role": "user"},
    )
    assert resp.status_code == 409


async def test_admin_disables_user(client, admin_user, normal_user, tokens):
    resp = await client.post(
        f"/api/v1/users/{normal_user.id}/disable",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_user_reads_own_profile(client, normal_user, tokens):
    resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == normal_user.id


async def test_admin_deletes_user(client, admin_user, normal_user, tokens):
    resp = await client.delete(
        f"/api/v1/users/{normal_user.id}",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    assert resp.status_code == 204