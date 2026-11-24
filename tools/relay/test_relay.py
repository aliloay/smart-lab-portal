import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import relay  # noqa: E402


def test_parse_map():
    assert relay.parse_map("8000=192.168.1.200:8000") == (8000, "192.168.1.200", 8000)
    with pytest.raises(ValueError):
        relay.parse_map("8000")


def test_bytes_go_both_ways_through_the_relay():
    async def run():
        async def echo(r, w):
            w.write(b"portal:" + await r.read(100)); await w.drain(); w.close()
        target = await asyncio.start_server(echo, "127.0.0.1", 0)
        tport = target.sockets[0].getsockname()[1]
        srv = await asyncio.start_server(relay.handler("127.0.0.1", tport, allow_local=True), "127.0.0.1", 0)
        rport = srv.sockets[0].getsockname()[1]
        r, w = await asyncio.open_connection("127.0.0.1", rport)
        w.write(b"GET /api/health"); await w.drain()
        got = await asyncio.wait_for(r.read(100), 3)
        w.close(); srv.close(); target.close()
        return got
    assert asyncio.run(run()) == b"portal:GET /api/health"


def test_unreachable_portal_closes_the_client_cleanly():
    async def run():
        srv = await asyncio.start_server(relay.handler("127.0.0.1", 1, timeout=1), "127.0.0.1", 0)
        r, w = await asyncio.open_connection("127.0.0.1", srv.sockets[0].getsockname()[1])
        got = await asyncio.wait_for(r.read(10), 3)
        srv.close()
        return got
    before = relay.stats["failed"]
    assert asyncio.run(run()) == b"" and relay.stats["failed"] == before + 1


def test_only_allowed_networks_get_through():
    nets = [relay.ipaddress.ip_network(n) for n in relay.DEFAULT_ALLOW]
    assert relay.allowed("10.40.20.18", nets) and relay.allowed("192.168.1.210", nets) and relay.allowed("127.0.0.1", nets)
    assert relay.allowed("::ffff:10.40.20.17", nets)                    # IPv4 seen through a dual-stack socket
    assert relay.allowed("10.30.11.57", nets)                           # a lab PC on the engineer PC's subnet (2026-11-04)
    assert not relay.allowed("172.20.10.4", nets)                       # a phone hotspot peer
    assert not relay.allowed("10.40.21.5", nets) and not relay.allowed("junk", nets)


def test_a_refused_client_is_closed_without_touching_the_portal():
    async def go():
        echo = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        port = echo.sockets[0].getsockname()[1]
        srv = await asyncio.start_server(relay.handler("127.0.0.1", port, allow=["10.40.20.0/24"]), "127.0.0.1", 0)
        before = relay.stats["refused"]
        r, w = await asyncio.open_connection("127.0.0.1", srv.sockets[0].getsockname()[1])
        assert await asyncio.wait_for(r.read(10), 3) == b""            # closed straight away: 127.0.0.1 not allowed here
        w.close(); srv.close(); echo.close()
        return relay.stats["refused"] - before
    assert asyncio.run(go()) == 1


def test_a_failed_bind_never_opens_another_address():
    """RELAY-1: it used to fall back to 0.0.0.0."""
    async def go():
        return await relay.serve("198.51.100.254", [(0, "192.0.2.1", 8000)], tries=2, wait_s=0.01)
    assert asyncio.run(go()) == []


def test_the_relay_never_connects_to_this_pc():
    async def go():
        me = sorted(relay.local_addresses())
        hosts = ["127.0.0.1", "localhost", "::1", "0.0.0.0", *[a for a in me if ":" not in a][:2]]
        got = [await relay.resolve_remote(h, 8000) for h in hosts]
        return got, await relay.resolve_remote("192.0.2.1", 8000)
    got, remote = asyncio.run(go())
    assert set(got) == {None} and remote == "192.0.2.1"


async def _chain(**kw):
    held = []

    async def portal(r, w):
        held.append(w)
        try:
            while (d := await r.read(100)):
                w.write(d)
                await w.drain()
        except ConnectionError:
            pass
    t = await asyncio.start_server(portal, "127.0.0.1", 0)
    srv = await asyncio.start_server(relay.handler("127.0.0.1", t.sockets[0].getsockname()[1], allow_local=True, **kw), "127.0.0.1", 0)
    return t, srv, srv.sockets[0].getsockname()[1]


def test_idle_is_closed_and_busy_is_not():
    async def go():
        t, srv, port = await _chain(idle_s=0.6)
        quiet = await asyncio.open_connection("127.0.0.1", port)
        busy = await asyncio.open_connection("127.0.0.1", port)
        for _ in range(8):                                   # 1.2 s of traffic every 0.15 s: longer than the idle limit
            busy[1].write(b"x")
            assert await asyncio.wait_for(busy[0].read(1), 2) == b"x"
            await asyncio.sleep(0.15)
        closed = await asyncio.wait_for(quiet[0].read(1), 2)
        busy[1].close()
        await asyncio.sleep(0.3)
        srv.close(); t.close()
        return closed, relay.stats["open"], dict(relay.per_client)
    assert asyncio.run(go()) == (b"", 0, {})


def test_connection_limits_and_no_leak():
    async def go():
        t, srv, port = await _chain(max_per_client=3)
        conns = [await asyncio.open_connection("127.0.0.1", port) for _ in range(6)]
        await asyncio.sleep(0.3)
        open_now = relay.stats["open"]
        refused = 0
        for r, _ in conns:
            try:
                refused += await asyncio.wait_for(r.read(1), 0.2) == b""
            except asyncio.TimeoutError:
                pass
        for _, w in conns:
            w.close()
        await asyncio.sleep(0.4)
        srv.close(); t.close()
        return open_now, refused, relay.stats["open"], dict(relay.per_client), len(asyncio.all_tasks())
    open_now, refused, left, clients, tasks = asyncio.run(go())
    assert (open_now, refused, left, clients) == (3, 3, 0, {}) and tasks <= 4
