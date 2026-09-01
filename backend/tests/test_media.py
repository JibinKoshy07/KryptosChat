"""Media upload/download (encrypted, streamed) tests."""
from app.schemas.user import UserCreate
from app.services import users


async def _conv(client, db, token, other):
    resp = await client.post(
        "/api/v1/conversations", headers={"Authorization": f"Bearer {token}"}, json={"user_ids": [other.id]}
    )
    return resp.json()["id"]


async def test_upload_and_download_roundtrip(client, db, admin_user, normal_user, tokens):
    other = await users.create_user(db, UserCreate(username="mia", display_name="Mia", password="pass12345", role="user"))
    conv_id = await _conv(client, db, tokens["user1"], other)
    files = {"file": ("photo.png", b"\x89PNG\r\n\x1a\nfake-png-content", "image/png")}
    resp = await client.post(
        f"/api/v1/media/{conv_id}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        files=files,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["message_type"] == "image"
    assert body["attachment"] is not None
    att_id = body["attachment"]["id"]

    # Download it back (decrypted).
    dl = await client.get(
        f"/api/v1/media/{att_id}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
    )
    assert dl.status_code == 200
    assert dl.content == b"\x89PNG\r\n\x1a\nfake-png-content"


async def test_upload_type_validation(client, db, admin_user, normal_user, tokens):
    other = await users.create_user(db, UserCreate(username="nina", display_name="Nina", password="pass12345", role="user"))
    conv_id = await _conv(client, db, tokens["user1"], other)
    files = {"file": ("evil.exe", b"MZ-binary", "application/x-msdos-program")}
    resp = await client.post(
        f"/api/v1/media/{conv_id}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        files=files,
    )
    assert resp.status_code == 400


async def test_upload_requires_membership(client, db, admin_user, normal_user, tokens):
    other = await users.create_user(db, UserCreate(username="oscar", display_name="Oscar", password="pass12345", role="user"))
    conv_id = await _conv(client, db, tokens["admin"], other)
    files = {"file": ("a.txt", b"hello", "text/plain")}
    resp = await client.post(
        f"/api/v1/media/{conv_id}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
        files=files,
    )
    assert resp.status_code == 403


async def test_download_requires_membership(client, db, admin_user, normal_user, tokens):
    other = await users.create_user(db, UserCreate(username="paul", display_name="Paul", password="pass12345", role="user"))
    conv_id = await _conv(client, db, tokens["admin"], other)
    files = {"file": ("b.txt", b"world", "text/plain")}
    up = await client.post(
        f"/api/v1/media/{conv_id}",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
        files=files,
    )
    att_id = up.json()["attachment"]["id"]
    dl = await client.get(
        f"/api/v1/media/{att_id}",
        headers={"Authorization": f"Bearer {tokens['user1']}"},
    )
    assert dl.status_code == 403