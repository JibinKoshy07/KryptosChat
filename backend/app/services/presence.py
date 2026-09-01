"""Presence tracking backed by Redis.

Each active WebSocket connection registers a key ``presence:{user_id}`` and
adds its connection id to a Redis set. A user is online while that set is
non-empty. The key carries a TTL that is refreshed by heartbeat pings, so
a lost connection (no heartbeat) automatically removes the user after the TTL
expires. Multiple tabs/devices all share one set, so presence stays online
until the last live connection disappears.
"""
import json
import logging

from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

PRESENCE_PREFIX = "presence:user"
ONLINE_CHANNEL = "events:presence"


def get_redis() -> Redis:
    """Create a Redis client with a unique connection name per process."""
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        connection_pool=None,
    )


async def set_online(rc: Redis, user_id: int, conn_id: str, ttl: int = 60) -> bool:
    """Register a connection for an online user. Returns True if newly online."""
    key = f"{PRESENCE_PREFIX}:{user_id}"
    was_offline = not await rc.exists(key)
    await rc.sadd(key, conn_id)
    await rc.expire(key, ttl)
    return was_offline


async def set_offline(rc: Redis, user_id: int, conn_id: str, ttl: int = 60) -> bool:
    """Remove a connection for a user. Returns True if user is now offline."""
    key = f"{PRESENCE_PREFIX}:{user_id}"
    await rc.srem(key, conn_id)
    remaining = await rc.scard(key)
    if remaining == 0:
        await rc.delete(key)
        return True
    await rc.expire(key, ttl)
    return False


async def refresh_presence(rc: Redis, user_id: int, ttl: int = 60) -> None:
    key = f"{PRESENCE_PREFIX}:{user_id}"
    if await rc.exists(key):
        await rc.expire(key, ttl)


async def is_online(rc: Redis, user_id: int) -> bool:
    return await rc.exists(f"{PRESENCE_PREFIX}:{user_id}")


async def online_count(rc: Redis) -> int:
    keys = await rc.keys(f"{PRESENCE_PREFIX}:*")
    return len(keys)


async def online_user_ids(rc: Redis) -> set[int]:
    keys = await rc.keys(f"{PRESENCE_PREFIX}:*")
    return {int(k.split(":")[-1]) for k in keys}


async def publish_presence(rc: Redis, user_id: int, online: bool, contacts: list[int]) -> None:
    """Notify the user's contacts of an online/offline change."""
    await rc.publish(
        ONLINE_CHANNEL,
        json.dumps({"type": "presence", "user_id": user_id, "online": online, "user_ids": contacts}),
    )