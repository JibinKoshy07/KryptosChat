"""WebSocket chat handler.

Protocol (JSON messages)::

    client -> server::
        {"type": "message", "temp_id": "...", "content": "...", "message_type": "text"}
        {"type": "read", "message_ids": [1, 2]}
        {"type": "typing", "conversation_id": 3}
        {"type": "ping"}

    server -> client::
        {"type": "message_new", "message": {...}}
        {"type": "message_delivered", "message_ids": [...]}
        {"type": "message_read", "message_ids": [...]}
        {"type": "typing", "user_id": ..., "conversation_id": ...}
        {"type": "presence", "user_id": ..., "online": true}
        {"type": "pong"}
        {"type": "error", "error": "..."}
"""
import json

from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.core.security import decode_token
from app.models.message import MessageType
from app.schemas.message import MessageCreate
from app.services import conversations, messages, presence
from app.websocket.connection import CHAT_CHANNEL, manager


async def handle_chat(ws: WebSocket, conversation_id: int, db_factory, rc: Redis) -> None:
    """Entry point for the ``/ws/chat/{conversation_id}`` endpoint."""
    user_id = None
    try:
        token = _extract_token(ws)
        payload = decode_token(token, "access")
        if payload is None:
            await ws.send_json({"type": "error", "error": "authentication_failed"})
            await ws.close(code=4001)
            return
        user_id = int(payload["sub"])

        async with db_factory() as db:
            await conversations.ensure_member(db, conversation_id, user_id)

        await manager.connect(user_id, ws)
        # Register presence (online).
        was_offline = await presence.set_online(rc, user_id, id(ws))
        if was_offline:
            await presence.publish_online(rc, user_id)

        await _send_conversation_snapshot(ws, db_factory, conversation_id, user_id)

        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "error": "invalid_json"})
                continue
            await _handle_client_message(ws, data, db_factory, rc, conversation_id, user_id)
    except WebSocketDisconnect:
        pass
    finally:
        if user_id is not None:
            await manager.disconnect(user_id, ws)
            was_offline = await presence.set_offline(rc, user_id, id(ws))
            if was_offline:
                await presence.publish_offline(rc, user_id)


def _extract_token(ws: WebSocket) -> str | None:
    # Support token via query param (browser WS) or Authorization header.
    token = ws.query_params.get("token")
    if token:
        return token
    auth = ws.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return None


async def _handle_client_message(
    ws: WebSocket,
    data: dict,
    db_factory,
    rc: Redis,
    conversation_id: int,
    user_id: int,
) -> None:
    msg_type = data.get("type")
    if msg_type == "ping":
        await ws.send_json({"type": "pong"})
        await presence.refresh_presence(rc, user_id)
        return
    if msg_type == "message":
        content = data.get("content", "")
        message_type = MessageType(data.get("message_type", "text"))
        temp_id = data.get("temp_id")
        if message_type == MessageType.TEXT and not content:
            await ws.send_json({"type": "error", "error": "empty_message"})
            return
        async with db_factory() as db:
            message = await messages.create_message(
                db, conversation_id, user_id,
                MessageCreate(content=content, message_type=message_type, temp_id=temp_id),
            )
            out = await messages.to_out(db, message, user_id)
            member_ids = await conversations.get_member_ids(db, conversation_id)
        # Fan out to the whole conversation (including sender for ack).
        payload = {"type": "message_new", "message": out.model_dump(mode="json"), "temp_id": temp_id}
        await _publish(rc, conversation_id, member_ids, payload)
        # Deliver receipts to the other member(s).
        await _mark_delivered_for_others(db_factory, conversation_id, message.id, user_id, rc)
        return
    if msg_type == "read":
        message_ids = data.get("message_ids", [])
        await _mark_read(db_factory, conversation_id, user_id, message_ids, rc)
        return
    if msg_type == "typing":
        conv_id = data.get("conversation_id", conversation_id)
        if conv_id != conversation_id:
            return
        async with db_factory() as db:
            member_ids = await conversations.get_member_ids(db, conversation_id)
        await _publish(rc, conversation_id, member_ids, {"type": "typing", "user_id": user_id, "conversation_id": conversation_id})
        return
    await ws.send_json({"type": "error", "error": "unknown_message_type"})


async def _publish(rc: Redis, conversation_id: int, user_ids: list[int], payload: dict) -> None:
    await rc.publish(
        CHAT_CHANNEL,
        json.dumps({**payload, "user_ids": user_ids, "conversation_id": conversation_id}),
    )


async def _send_conversation_snapshot(ws: WebSocket, db_factory, conversation_id: int, user_id: int) -> None:
    async with db_factory() as db:
        conn = await conversations.get_for_user(db, conversation_id, user_id)
        await ws.send_json({"type": "conversation", "conversation": conn.model_dump(mode="json")})


async def _mark_delivered_for_others(db_factory, conversation_id: int, message_id: int, sender_id: int, rc: Redis) -> None:
    async with db_factory() as db:
        member_ids = [m for m in await conversations.get_member_ids(db, conversation_id) if m != sender_id]
        newly = await messages.mark_delivered(db, conversation_id, sender_id, [message_id])
    await _publish(rc, conversation_id, member_ids, {"type": "message_delivered", "message_ids": newly})


async def _mark_read(db_factory, conversation_id: int, user_id: int, message_ids: list[int], rc: Redis) -> None:
    async with db_factory() as db:
        member_ids = [m for m in await conversations.get_member_ids(db, conversation_id) if m != user_id]
        newly = await conversations.mark_messages_read(db, conversation_id, user_id, message_ids)
    await _publish(rc, conversation_id, member_ids, {"type": "message_read", "message_ids": newly, "user_id": user_id})