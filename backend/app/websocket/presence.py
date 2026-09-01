"""Presence WebSocket handler.

Keeps a lightweight connection open for online-detection and real-time
presence updates. The presence registry/Redis is the source of truth, so the
main chat connection and the presence connection work together.
"""
import logging

from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.core.security import decode_token
from app.services import conversations, presence
from app.websocket.connection import manager

logger = logging.getLogger(__name__)


async def handle_presence(ws: WebSocket, rc: Redis, db_factory) -> None:
    user_id = None
    try:
        token = ws.query_params.get("token") or _bearer(ws)
        payload = decode_token(token, "access")
        if payload is None:
            await ws.close(code=4001)
            return
        user_id = int(payload["sub"])
        contacts = await _contacts(db_factory, user_id)
        was_offline = await presence.set_online(rc, user_id, id(ws))
        await manager.connect(user_id, ws)
        if was_offline:
            await presence.publish_presence(rc, user_id, True, contacts)
        await ws.send_json({"type": "presence", "user_id": user_id, "online": True})
        while True:
            raw = await ws.receive_text()
            if "ping" in raw:
                await presence.refresh_presence(rc, user_id)
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        if user_id is not None:
            await manager.disconnect(user_id, ws)
            was_offline = await presence.set_offline(rc, user_id, id(ws))
            if was_offline:
                await presence.publish_presence(rc, user_id, False, await _contacts(db_factory, user_id))


async def _contacts(db_factory, user_id: int) -> list[int]:
    """Return the ids of users the user has a conversation with."""
    try:
        async with db_factory() as db:
            member_ids: set[int] = set()
            for conv in await conversations.list_for_user(db, user_id):
                member_ids.update(m.user.id for m in conv.members)
            return [uid for uid in member_ids if uid != user_id]
    except Exception:
        return []


def _bearer(ws: WebSocket) -> str | None:
    auth = ws.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return None