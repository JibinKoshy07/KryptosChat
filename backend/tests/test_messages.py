"""Message creation, listing, and receipts."""
from app.schemas.user import UserCreate
from app.services import users


async def _conv(client, db, token, other):
    resp = await client.post(
        "/api/v1/conversations", headers={"Authorization": f"Bearer {token}"}, json={"user_ids": [other.id]}
    )
    return resp.json()["id"]


async def test_send_text_message(client, db, admin_user, normal_user, tokens):
    other = await users.create_user(db, UserCreate(username="frank", display_name="Frank", password="pass12345", role="user"))
    conv_id = await _conv(client, db, tokens["user1"], other)
    resp = await client.post(
        f"/api/v1/messages/{conv_id}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        json={"content": "hello", "message_type": "text"},
    )
    assert resp.status_code == 201
    # Content must come back decrypted.
    assert resp.json()["content"] == "hello"


async def test_list_messages_paginated(client, db, admin_user, normal_user, tokens):
    other = await users.create_user(db, UserCreate(username="grace", display_name="Grace", password="pass12345", role="user"))
    conv_id = await _conv(client, db, tokens["user1"], other)
    for i in range(5):
        await client.post(
            f"/api/v1/messages/{conv_id}",
            headers={"Authorization": f"Bearer {tokens['user1']}"},
            json={"content": f"msg {i}", "message_type": "text"},
        )
    resp = await client.get(
        f"/api/v1/messages/{conv_id}?limit=3",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    assert body["has_more"] is True
    assert body["next_cursor"] is not None


async def test_cannot_send_message_outside_conversation(client, db, admin_user, normal_user, tokens):
    other = await users.create_user(db, UserCreate(username="heidi", display_name="Heidi", password="pass12345", role="user"))
    conv_id = await _conv(client, db, tokens["admin"], other)
    resp = await client.post(
        f"/api/v1/messages/{conv_id}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        json={"content": "intrusion", "message_type": "text"},
    )
    assert resp.status_code == 403


async def test_empty_text_message_rejected(client, db, admin_user, normal_user, tokens):
    other = await users.create_user(db, UserCreate(username="ivan", display_name="Ivan", password="pass12345", role="user"))
    conv_id = await _conv(client, db, tokens["user1"], other)
    resp = await client.post(
        f"/api/v1/messages/{conv_id}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        json={"content": "", "message_type": "text"},
    )
    assert resp.status_code == 400


async def test_soft_delete_own_message(client, db, admin_user, normal_user, tokens):
    other = await users.create_user(db, UserCreate(username="judy", display_name="Judy", password="pass12345", role="user"))
    conv_id = await _conv(client, db, tokens["user1"], other)
    msg = await client.post(
        f"/api/v1/messages/{conv_id}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        json={"content": "delete me", "message_type": "text"},
    )
    resp = await client.delete(
        f"/api/v1/messages/{conv_id}/{msg.json()['id']}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
    )
    assert resp.status_code == 204