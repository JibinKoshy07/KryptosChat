"""Presence (Redis) tests."""
from app.services import presence


async def test_online_offline_transitions(fakeredis):
    rc = fakeredis
    assert not await presence.is_online(rc, 1)

    newly = await presence.set_online(rc, 1, "conn-a")
    assert newly is True
    assert await presence.is_online(rc, 1)

    # A second connection keeps the user online.
    newly2 = await presence.set_online(rc, 1, "conn-b")
    assert newly2 is False
    assert await presence.is_online(rc, 1)

    # Dropping one connection still leaves the user online.
    offline = await presence.set_offline(rc, 1, "conn-a")
    assert offline is False
    assert await presence.is_online(rc, 1)

    # Dropping the last connection marks the user offline.
    offline2 = await presence.set_offline(rc, 1, "conn-b")
    assert offline2 is True
    assert not await presence.is_online(rc, 1)


async def test_refresh_presence_extends_ttl(fakeredis):
    rc = fakeredis
    await presence.set_online(rc, 2, "conn-c", ttl=5)
    await presence.refresh_presence(rc, 2, ttl=30)
    ttl = await rc.ttl("presence:user:2")
    assert 0 < ttl <= 30


async def test_online_count(fakeredis):
    rc = fakeredis
    await presence.set_online(rc, 3, "c1")
    await presence.set_online(rc, 4, "c2")
    assert await presence.online_count(rc) == 2