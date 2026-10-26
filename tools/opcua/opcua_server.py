"""
Smart Lab OPC UA server - READ-ONLY (2026-10-26, priority J).

OPC UA is the industrial "common language" for live machine data: a client (UaExpert, Siemens/SCADA, Node-RED, a
MES) browses a tree of named variables (Labs > LAB_01 > Robots > UR5E_01 > J1_deg ...) and reads or subscribes to
them. This server mirrors the portal's equipment state into that tree every second. Nothing can be written: every
variable is read-only, there are no methods, and the source is the portal's read-only /api/opcua/snapshot.

    py -3.12 tools/opcua/opcua_server.py            # opc.tcp://127.0.0.1:4840/smartlab/ (settings: tools/opcua/opcua.env)

Security: on 127.0.0.1 (default) anonymous read is allowed - only this laptop can connect. With OPCUA_HOST set to a
LAN address the server requires Basic256Sha256 Sign&Encrypt (self-signed certificate made on first start) AND the
user name / password from opcua.env; anonymous is then refused.
No people's names, PC accounts or images are published (see backend/app/api/routes/opcua.py).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Callable, Optional

from asyncua import Server, ua

HERE = os.path.dirname(os.path.abspath(__file__))
NS = "urn:giu:smartlab:opcua"
GROUP = {"ROBOT": "Robots", "PC": "PCs", "SECURITY_CAMERA": "Cameras", "MASTER_CONTROLLER": "Door",
         "SENSOR_NODE": "SensorNodes"}
log = logging.getLogger("smartlab.opcua")


def _variant(v):
    if isinstance(v, bool):
        return ua.Variant(v, ua.VariantType.Boolean)
    if isinstance(v, int):
        return ua.Variant(float(v), ua.VariantType.Double)        # one numeric type: no type change later
    if isinstance(v, float):
        return ua.Variant(v, ua.VariantType.Double)
    return ua.Variant("" if v is None else str(v), ua.VariantType.String)


class Mirror:
    """Keeps an OPC UA tree equal to the latest snapshot. New devices / values appear as they are reported."""

    def __init__(self, server: Server, idx: int):
        self.server, self.idx = server, idx
        self.nodes: dict[str, object] = {}
        self.root = None

    async def _obj(self, key: str, parent, name: str):
        if key not in self.nodes:
            self.nodes[key] = await parent.add_object(ua.NodeId(key, self.idx), name)
        return self.nodes[key]

    async def _var(self, key: str, parent, name: str, value):
        var = _variant(value)
        node = self.nodes.get(key)
        if node is None:
            node = await parent.add_variable(ua.NodeId(key, self.idx), name, var)
            await node.set_read_only()                              # never writable by a client
            self.nodes[key] = node
            self.nodes[key + "#type"] = var.VariantType
            return
        want = self.nodes[key + "#type"]
        if want != var.VariantType:                                 # a value changed type: keep the declared type
            if want == ua.VariantType.String:
                var = ua.Variant("" if value is None else str(value), want)
            elif want == ua.VariantType.Double:
                var = ua.Variant(float(value) if isinstance(value, (int, float)) else float("nan"), want)
            else:
                var = ua.Variant(bool(value), want)
        await self.server.write_attribute_value(node.nodeid, ua.DataValue(var))

    async def apply(self, snap: dict) -> int:
        if self.root is None:
            self.root = await self.server.nodes.objects.add_object(ua.NodeId("SmartLab", self.idx), "SmartLab")
        await self._var("SmartLab.ServerTime", self.root, "SourceTime", snap.get("server_time"))
        await self._var("SmartLab.FeedOK", self.root, "FeedOK", True)
        n = 0
        for lab in snap.get("labs", []):
            lk = f"SmartLab.{lab['code']}"
            lnode = await self._obj(lk, self.root, lab["code"])
            await self._var(lk + ".Name", lnode, "Name", lab.get("name"))
            for d in lab.get("devices", []):
                g = GROUP.get(d["type"], "Other")
                gnode = await self._obj(f"{lk}.{g}", lnode, g)
                dk = f"{lk}.{g}.{d['uid']}"
                dnode = await self._obj(dk, gnode, d["uid"])
                await self._var(dk + ".Name", dnode, "Name", d.get("name"))
                await self._var(dk + ".Online", dnode, "Online", bool(d.get("online")))
                await self._var(dk + ".LastSeen", dnode, "LastSeen", d.get("last_seen"))
                for k, v in (d.get("values") or {}).items():
                    await self._var(f"{dk}.{k}", dnode, k, v)
                    n += 1
            env = lab.get("environment") or {}
            if env:
                enode = await self._obj(f"{lk}.Environment", lnode, "Environment")
                for m, v in env.items():
                    mk = f"{lk}.Environment.{m}"
                    mnode = await self._obj(mk, enode, m)
                    await self._var(mk + ".Value", mnode, "Value", v.get("value"))
                    await self._var(mk + ".Unit", mnode, "Unit", v.get("unit"))
                    await self._var(mk + ".Quality", mnode, "Quality", v.get("quality"))
                    await self._var(mk + ".At", mnode, "At", v.get("at"))
                    n += 1
        return n

    async def feed_lost(self):
        if self.root is not None:
            await self._var("SmartLab.FeedOK", self.root, "FeedOK", False)


async def build(endpoint: str, secure: bool, users: Optional[dict] = None, cert_dir: str = HERE) -> tuple[Server, Mirror]:
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("Smart Lab OPC UA (read-only)")
    if secure:
        from asyncua.crypto.cert_gen import setup_self_signed_certificate
        from asyncua.server.user_managers import UserManager
        from cryptography.x509.oid import ExtendedKeyUsageOID
        from pathlib import Path
        cert, key = Path(cert_dir) / "server_cert.der", Path(cert_dir) / "server_key.pem"
        await setup_self_signed_certificate(key, cert, NS, os.environ.get("COMPUTERNAME", "smartlab"),
                                            [ExtendedKeyUsageOID.SERVER_AUTH], {"commonName": "Smart Lab OPC UA"})
        await server.load_certificate(cert)
        await server.load_private_key(key)
        server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])

        class Users(UserManager):
            def get_user(self, iserver, username=None, password=None, certificate=None):
                import hmac
                from asyncua.server.users import User, UserRole
                if username and users and username in users and hmac.compare_digest(password or "", users[username]):
                    return User(role=UserRole.User)
                return None
        server.iserver.user_manager = Users()
        server.set_security_IDs(["Username"])
    else:
        server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        server.set_security_IDs(["Anonymous"])
    idx = await server.register_namespace(NS)
    return server, Mirror(server, idx)


async def run(fetch: Callable[[], dict], endpoint: str, secure: bool, users: Optional[dict], period: float = 1.0,
              ready: Optional[asyncio.Event] = None, stop: Optional[asyncio.Event] = None):
    server, mirror = await build(endpoint, secure, users)
    async with server:
        first = True
        while not (stop and stop.is_set()):
            try:
                snap = await asyncio.get_running_loop().run_in_executor(None, fetch)
                n = await mirror.apply(snap)
                if first:
                    log.info("serving %d values at %s", n, endpoint)
                    first = False
            except Exception as e:                                   # portal down: keep serving, say so
                log.warning("feed error: %s", e.__class__.__name__)
                await mirror.feed_lost()
            if ready is not None and not ready.is_set():
                ready.set()
            await asyncio.sleep(period)


def main():
    import requests
    envf = os.path.join(HERE, "opcua.env")
    if os.path.isfile(envf):
        for line in open(envf, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    key = os.environ.get("OPCUA_KEY", "")
    if not key:
        raise SystemExit("OPCUA_KEY missing (tools/opcua/opcua.env) - the same value as the backend's OPCUA_KEY")
    host = os.environ.get("OPCUA_HOST", "127.0.0.1")
    port = int(os.environ.get("OPCUA_PORT", "4840"))
    api = os.environ.get("OPCUA_PORTAL", "http://127.0.0.1:8000/api").rstrip("/")
    secure = host not in ("127.0.0.1", "localhost")
    users = None
    if secure:
        u, p = os.environ.get("OPCUA_USER", ""), os.environ.get("OPCUA_PASSWORD", "")
        if not u or len(p) < 12:
            raise SystemExit("LAN mode needs OPCUA_USER and an OPCUA_PASSWORD of 12+ characters in opcua.env")
        users = {u: p}
    s = requests.Session()
    s.headers["X-OPCUA-Key"] = key

    def fetch():
        r = s.get(api + "/opcua/snapshot", timeout=5)
        r.raise_for_status()
        return r.json()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    endpoint = f"opc.tcp://{host}:{port}/smartlab/"
    print(f"Smart Lab OPC UA (read-only): {endpoint} | {'Basic256Sha256 + user/password' if secure else 'localhost, anonymous'} "
          f"| source {api}/opcua/snapshot")
    asyncio.run(run(fetch, endpoint, secure, users))


if __name__ == "__main__":
    main()
