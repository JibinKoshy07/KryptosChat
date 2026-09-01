"""WebSocket real-time message and presence tests."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def ws_client():
    with TestClient(app) as client:
        yield client


def _conv_id(ws_client, token, other_id):
    resp = ws_client.post(
        "/api/v1/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_ids": [other_id]},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_ws_message_relay(ws_client, db, admin_user, normal_user, tokens):
    # user1 and admin are both seeded; create a 1:1 chat between them.
    conv_id = _conv_id(ws_client, tokens["user1"], admin_user.id)

    with ws_client.websocket_connect(f"/ws/chat/{conv_id}?token={tokens['user1']}") as ws1, \
         ws_client.websocket_connect(f"/ws/chat/{conv_id}?token={tokens['admin']}") as ws2:
        # Drain the conversation snapshot on both.
        ws1.receive_json()
        ws2.receive_json()

        ws1.send_json({"type": "message", "content": "ping", "message_type": "text", "temp_id": "t1"})

        # Both sender and recipient receive message_new.
        seen = [ws1.receive_json(), ws2.receive_json()]
        got = [m for m in seen if m.get("type") == "message_new"]
        assert len(got) >= 1
        assert got[0]["message"]["content"] == "ping"
        assert got[0]["temp_id"] == "t1"


@pytest.mark.asyncio
async def test_ws_read_receipt(ws_client, db, admin_user, normal_user, tokens):
    conv_id = _conv_id(ws_client, tokens["user1"], admin_user.id)

    with ws_client.websocket_connect(f"/ws/chat/{conv_id}?token={tokens['user1']}") as ws1, \
         ws_client.websocket_connect(f"/ws/chat/{conv_id}?token={tokens['admin']}") as ws2:
        ws1.receive_json()
        ws2.receive_json()
        ws1.send_json({"type": "message", "content": "read me", "message_type": "text", "temp_id": "t2"})
        # Recipient marks it read.
        messages = [ws2.receive_json(), ws1.receive_json()]
        new_msg = next(m for m in messages if m.get("type") == "message_new")
        msg_id = new_msg["message"]["id"]
        ws2.send_json({"type": "read", "message_ids": [msg_id]})

        read_events = [m for m in (ws1.receive_json(), ws2.receive_json()) if m.get("type") == "message_read"]
        assert read_events and msg_id in read_events[0]["message_ids"]


@pytest.mark.asyncio
async def test_ws_auth_required(ws_client, db, admin_user, normal_user):
    with pytest.raises(Exception):
        with ws_client.websocket_connect("/ws/chat/1?token=invalidtoken") as ws:
            ws.receive_json()