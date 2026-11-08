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
        srv = await asyncio.start_server(relay.handler("127.0.0.1", tport), "127.0.0.1", 0)
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
