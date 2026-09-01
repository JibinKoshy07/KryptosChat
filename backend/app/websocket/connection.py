"""WebSocket connection registry and Redis pub/sub fanout.

The registry tracks live connections per user (multi-tab support). For
multi-instance deployments, message events are published to a Redis channel;
every backend instance subscribes and fans out to its own local connections,
so a message sent on one instance reaches recipients on any instance.
"""
import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

CHAT_CHANNEL = "events:chat"
PRESENCE_CHANNEL = "events:presence"


class WebSocketManager:
    def __init__(self) -> None:
        # user_id -> set[connection objects]
        self._connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._pubsub: Redis | None = None

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(ws)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(user_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        """Send a JSON payload to every live connection for a user."""
        async with self._lock:
            conns = list(self._connections.get(user_id, set()))
        for ws in conns:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                logger.warning("ws_send_failed", extra={"extra_fields": {"user_id": user_id}})

    async def send_to_connection(self, ws: WebSocket, payload: dict[str, Any]) -> bool:
        try:
            await ws.send_text(json.dumps(payload))
            return True
        except Exception:
            return False

    def has_connection(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))

    async def subscribe_redis(self, rc: Redis) -> None:
        """Subscribe to chat/presence channels so all instances fan out."""
        self._pubsub = rc.pubsub()
        await self._pubsub.subscribe(CHAT_CHANNEL, PRESENCE_CHANNEL)

    async def listen(self) -> None:
        """Background task: relay pub/sub events to local connections.

        Each published payload carries the ``user_ids`` that should receive it.
        Every backend instance relays to its own local connections for those
        ids, so a user's connections receive each event exactly once regardless
        of which instance they are attached to.
        """
        if self._pubsub is None:
            return
        while True:
            try:
                msg = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if msg is None:
                continue
            data = msg.get("data")
            if not isinstance(data, str):
                continue
            try:
                payload = json.loads(data)
            except ValueError:
                # Presence channel may carry a bare user id.
                try:
                    await self.send_to_user(int(data), {"type": "presence"})
                except ValueError:
                    pass
                continue
            user_ids = payload.get("user_ids") or ([payload["user_id"]] if "user_id" in payload else [])
            for uid in user_ids:
                await self.send_to_user(int(uid), payload)

    async def start(self, rc: Redis) -> None:
        await self.subscribe_redis(rc)
        asyncio.create_task(self.listen())

    async def stop(self) -> None:
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(CHAT_CHANNEL, PRESENCE_CHANNEL)


manager = WebSocketManager()