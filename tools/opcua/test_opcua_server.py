"""OPC UA server: tree built from a fake portal snapshot, values update, nothing writable, LAN mode needs a user.
    py -3.12 -m pytest -q tools/opcua"""
import asyncio
import socket

import pytest
from asyncua import Client, ua

import opcua_server as S

SNAP = {"server_time": "2026-10-26T20:00:00+00:00", "labs": [{
    "code": "LAB_01", "name": "Robotics Lab",
    "devices": [{"uid": "UR5E_01", "name": "UR5e", "type": "ROBOT", "online": True, "last_seen": "2026-10-26T19:59:59+00:00",
                 "values": {"robot_mode": "RUNNING", "J1_deg": -15.0, "speed_scaling": 1}},
                {"uid": "SECCAM_1", "name": "Camera 1", "type": "SECURITY_CAMERA", "online": False, "last_seen": None,
                 "values": {"people": 2}}],
    "environment": {"temperature": {"value": 24.5, "unit": "C", "quality": "VALID", "at": "2026-10-26T19:59:00+00:00"}}}]}


def port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


async def _serve(snaps, secure=False, users=None):
    p = port()
    ep = f"opc.tcp://127.0.0.1:{p}/smartlab/"
    it = iter(snaps)
    state = {"last": snaps[0]}

    def fetch():
        state["last"] = next(it, state["last"])
        return state["last"]
    ready, stop = asyncio.Event(), asyncio.Event()
    task = asyncio.create_task(S.run(fetch, ep, secure, users, period=0.2, ready=ready, stop=stop))
    await asyncio.wait_for(ready.wait(), 20)
    return ep, task, stop


def test_tree_values_and_read_only():
    async def go():
        snap2 = {**SNAP, "labs": [{**SNAP["labs"][0], "devices": [
            {**SNAP["labs"][0]["devices"][0], "values": {"robot_mode": "IDLE", "J1_deg": -20.5, "speed_scaling": 1}},
            SNAP["labs"][0]["devices"][1]]}]}
        ep, task, stop = await _serve([SNAP, snap2])
        try:
            async with Client(ep) as c:
                idx = await c.get_namespace_index(S.NS)
                j1 = c.get_node(ua.NodeId("SmartLab.LAB_01.Robots.UR5E_01.J1_deg", idx))
                await asyncio.sleep(0.6)
                assert await j1.read_value() == pytest.approx(-20.5)          # updated from the second snapshot
                assert await c.get_node(ua.NodeId("SmartLab.LAB_01.Robots.UR5E_01.robot_mode", idx)).read_value() == "IDLE"
                assert await c.get_node(ua.NodeId("SmartLab.LAB_01.Cameras.SECCAM_1.Online", idx)).read_value() is False
                t = c.get_node(ua.NodeId("SmartLab.LAB_01.Environment.temperature.Value", idx))
                assert await t.read_value() == pytest.approx(24.5)
                with pytest.raises(ua.UaStatusCodeError):
                    await j1.write_value(ua.DataValue(ua.Variant(0.0, ua.VariantType.Double)))   # read-only
        finally:
            stop.set(); await task
    asyncio.run(go())


def test_feed_loss_is_published_not_hidden():
    async def go():
        calls = {"n": 0}
        p = port(); ep = f"opc.tcp://127.0.0.1:{p}/smartlab/"

        def fetch():
            calls["n"] += 1
            if calls["n"] > 1:
                raise OSError("portal down")
            return SNAP
        ready, stop = asyncio.Event(), asyncio.Event()
        task = asyncio.create_task(S.run(fetch, ep, False, None, period=0.2, ready=ready, stop=stop))
        await asyncio.wait_for(ready.wait(), 20)
        try:
            async with Client(ep) as c:
                idx = await c.get_namespace_index(S.NS)
                await asyncio.sleep(0.6)
                assert await c.get_node(ua.NodeId("SmartLab.FeedOK", idx)).read_value() is False
        finally:
            stop.set(); await task
    asyncio.run(go())


def test_lan_mode_refuses_anonymous(tmp_path, monkeypatch):
    async def go():
        monkeypatch.setattr(S, "HERE", str(tmp_path))
        p = port(); ep = f"opc.tcp://127.0.0.1:{p}/smartlab/"
        ready, stop = asyncio.Event(), asyncio.Event()

        async def run_secure():
            server, mirror = await S.build(ep, True, {"viewer": "a-long-password-1"}, cert_dir=str(tmp_path))
            async with server:
                await mirror.apply(SNAP); ready.set()
                while not stop.is_set():
                    await asyncio.sleep(0.1)
        task = asyncio.create_task(run_secure())
        await asyncio.wait_for(ready.wait(), 30)
        try:
            with pytest.raises(Exception):
                async with Client(ep) as c:                     # no security, no user -> refused
                    await c.get_namespace_index(S.NS)
        finally:
            stop.set(); await task
    asyncio.run(go())
