"""Conversation tests."""
from app.schemas.user import UserCreate
from app.services import users


async def _add_user(db, username, display):
    return await users.create_user(
        db, UserCreate(username=username, display_name=display, password="pass12345", role="user")
    )


async def test_create_conversation(client, db, admin_user, normal_user, tokens):
    other = await _add_user(db, "alice", "Alice")
    resp = await client.post(
        "/api/v1/conversations",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        json={"user_ids": [other.id]},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] > 0


async def test_cannot_chat_with_disabled_user(client, db, admin_user, normal_user, tokens):
    other = await _add_user(db, "carol", "Carol")
    await client.post(
        f"/api/v1/users/{other.id}/disable",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    resp = await client.post(
        "/api/v1/conversations",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        json={"user_ids": [other.id]},
    )
    assert resp.status_code == 400


async def test_reuse_existing_conversation(client, db, admin_user, normal_user, tokens):
    other = await _add_user(db, "dave", "Dave")
    await client.post(
        "/api/v1/conversations",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        json={"user_ids": [other.id]},
    )
    resp = await client.post(
        "/api/v1/conversations",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        json={"user_ids": [other.id]},
    )
    assert resp.status_code == 201


async def test_cannot_access_foreign_conversation(client, db, admin_user, normal_user, tokens):
    other = await _add_user(db, "erin", "Erin")
    # admin chats with erin
    conv = await client.post(
        "/api/v1/conversations",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
        json={"user_ids": [other.id]},
    )
    conv_id = conv.json()["id"]
    # user1 (not a member) attempts to read it
    resp = await client.get(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
    )
    assert resp.status_code == 403