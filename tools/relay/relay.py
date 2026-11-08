"""Smart Lab relay for the lab engineer PC (2026-11-03).

The lab PCs (PC-01..16) are on the GIU network only (10.40.20.x); the portal laptop is on the isolated Smart Lab
network (192.168.1.200). The lab engineer PC is on both. This relay runs THERE and forwards plain TCP from its GIU
address to the portal, so a GIU PC's agent and browser can reach the portal without any routing, gateway or
GIU network change. Pure standard-library Python 3.8+ (runs on the lab PCs' Python), no admin rights, stops with
Ctrl+C or by closing its window.

  py relay.py                                   # 8000 / 443 / 80 -> 192.168.1.200 on every local address
  py relay.py --listen 10.40.20.17              # only on the GIU address (recommended once known)
  py relay.py --map 8000=192.168.1.200:8000 --map 443=192.168.1.200:443

Then on a GIU lab PC:  start_pc_agent.bat with PORTAL=http://<engineer PC GIU IP>:8000/api
                       and the browser at https://<engineer PC GIU IP>/  (certificate warning: the portal's
                       certificate names smartlab.local / 192.168.1.200 - accept it for the test)
Windows Firewall on the engineer PC must allow inbound TCP to these ports (or to python.exe): that needs the
lab engineer / GIU IT - this script never changes the firewall.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import ipaddress
import os
import sys

# Hidden start (pythonw.exe from install_autostart.bat, 2026-11-03): there is no console, so the log goes to
# %TEMP%\smartlab_relay.log instead (pythonw has no stdout and the relay carried no traffic without this).
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(os.path.join(os.environ.get("TEMP", "."), "smartlab_relay.log"), "a",
                                   encoding="utf-8", buffering=1)

DEFAULT_MAPS = ["8000=192.168.1.200:8000", "443=192.168.1.200:443", "80=192.168.1.200:80"]
stats = {"open": 0, "total": 0, "failed": 0, "refused": 0}
# who may use the relay: the GIU lab LANs, the Smart Lab LAN and this PC (2026-11-03 audit: it was open to anyone).
# 10.30.11.0/24 added 2026-11-04: the engineer PC's relay listens on 10.30.11.136 and the lab PCs reach it on that
# subnet, so they were refused ("not in --allow") with only 10.40.20.0/24 listed.
DEFAULT_ALLOW = ["10.30.11.0/24", "10.40.20.0/24", "192.168.1.0/24", "127.0.0.0/8"]


def allowed(ip: str, nets: list) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return any(a in n for n in nets)


def parse_map(text: str) -> tuple[int, str, int]:
    """"8000=192.168.1.200:8000" -> (8000, "192.168.1.200", 8000)."""
    local, _, remote = text.partition("=")
    host, _, port = remote.rpartition(":")
    if not (local.isdigit() and host and port.isdigit()):
        raise ValueError(f"bad --map {text!r}, want LOCALPORT=HOST:PORT")
    return int(local), host, int(port)


def log(msg: str) -> None:
    print(f"{dt.datetime.now():%H:%M:%S}  {msg}", flush=True)


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


def handler(host: str, port: int, timeout: float = 5.0, allow: list | None = None):
    nets = [ipaddress.ip_network(n) for n in (allow or DEFAULT_ALLOW)]

    async def handle(cr: asyncio.StreamReader, cw: asyncio.StreamWriter) -> None:
        peer = cw.get_extra_info("peername")
        if not (peer and allowed(peer[0], nets)):
            stats["refused"] += 1
            log(f"{peer[0] if peer else '?'} refused (not in --allow)")
            cw.close()
            return
        try:
            ur, uw = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        except (OSError, asyncio.TimeoutError) as e:
            stats["failed"] += 1
            log(f"{peer[0] if peer else '?'} -> {host}:{port} FAILED ({e.__class__.__name__}) - is the portal laptop "
                f"on the Smart Lab network and this PC's second adapter on 192.168.1.x?")
            cw.close()
            return
        stats["open"] += 1; stats["total"] += 1
        try:
            await asyncio.gather(_pipe(cr, uw), _pipe(ur, cw))
        finally:
            stats["open"] -= 1
    return handle


async def serve(listen: str, maps: list[tuple[int, str, int]], allow: list | None = None) -> list:
    servers = []
    for lport, host, rport in maps:
        try:
            servers.append(await asyncio.start_server(handler(host, rport, allow=allow), listen, lport))
            log(f"relay {listen}:{lport} -> {host}:{rport}")
        except OSError as e:
            log(f"cannot listen on {listen}:{lport} ({e}) - port in use or not allowed; skipped")
    return servers


async def main_async(args) -> None:
    maps = [parse_map(m) for m in (args.map or DEFAULT_MAPS)]
    servers = await serve(args.listen, maps, args.allow or DEFAULT_ALLOW)
    log("clients allowed from: " + ", ".join(args.allow or DEFAULT_ALLOW))
    if not servers:
        sys.exit("nothing to relay")
    for _, host, rport in maps[:1]:
        try:
            _, w = await asyncio.wait_for(asyncio.open_connection(host, rport), 3)
            w.close(); log(f"portal {host}:{rport} reachable from this PC - OK")
        except (OSError, asyncio.TimeoutError):
            log(f"WARNING: portal {host}:{rport} NOT reachable from this PC - check the USB-Ethernet adapter "
                f"(192.168.1.210 / 255.255.255.0, no gateway) and the cable to the Smart Lab router")
    while True:
        await asyncio.sleep(60)
        log(f"connections: {stats['open']} open, {stats['total']} total, {stats['failed']} failed, {stats['refused']} refused")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listen", default="0.0.0.0", help="local address to listen on (the GIU address is best)")
    ap.add_argument("--map", action="append", help="LOCALPORT=HOST:PORT (repeatable); default 8000, 443, 80")
    ap.add_argument("--allow", action="append", help="client network allowed in, e.g. 10.40.20.0/24 (repeatable); "
                    "default " + " ".join(DEFAULT_ALLOW))
    try:
        asyncio.run(main_async(ap.parse_args()))
    except KeyboardInterrupt:
        log("relay stopped")


if __name__ == "__main__":
    main()
