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
import socket
import sys
import time
from typing import Optional

# Hidden start (pythonw.exe from install_autostart.bat, 2026-11-03): there is no console, so the log goes to
# %TEMP%\smartlab_relay.log instead (pythonw has no stdout and the relay carried no traffic without this).
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(os.path.join(os.environ.get("TEMP", "."), "smartlab_relay.log"), "a",
                                   encoding="utf-8", buffering=1)

DEFAULT_MAPS = ["8000=192.168.1.200:8000", "443=192.168.1.200:443", "80=192.168.1.200:80"]
stats = {"open": 0, "total": 0, "failed": 0, "refused": 0, "idle": 0}
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


# Gemini audit 24 Nov 2026 (RELAY-1..3). Agents, the portal's live channel (pings every ~20 s) and screen frames (several a
# second) are never quiet this long; 16 lab PCs hold a handful of connections each.
IDLE_S = 600.0
MAX_OPEN, MAX_PER_CLIENT = 400, 60
BIND_TRIES, BIND_WAIT_S = 20, 15.0             # ~5 min for the network adapter at start-up, then exit
per_client: dict = {}


def local_addresses() -> set:
    """Addresses of this PC (for the self-relay check)."""
    out = set()
    try:
        out |= {a[4][0].split("%")[0] for a in socket.getaddrinfo(socket.gethostname(), None)}
    except OSError:
        pass
    return out


def is_self(ip: str, local: set) -> bool:
    a = ipaddress.ip_address(ip.split("%")[0])
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_loopback or a.is_unspecified or str(a) in local


async def resolve_remote(host: str, port: int, allow_local: bool = False) -> Optional[str]:
    """The one address to connect to (checked and used, so a name cannot change in between), or None = this PC itself."""
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    local = local_addresses()
    for info in infos:
        ip = info[4][0]
        if allow_local or not is_self(ip, local):
            return ip
    return None


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, seen: list) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            seen[0] = time.monotonic()
            writer.write(data)
            await writer.drain()
            seen[0] = time.monotonic()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


def handler(host: str, port: int, timeout: float = 5.0, allow: list | None = None, *, allow_local: bool = False,
            idle_s: float | None = None, max_open: int | None = None, max_per_client: int | None = None):
    nets = [ipaddress.ip_network(n) for n in (allow or DEFAULT_ALLOW)]
    idle, cap, cap1 = idle_s or IDLE_S, max_open or MAX_OPEN, max_per_client or MAX_PER_CLIENT

    async def handle(cr: asyncio.StreamReader, cw: asyncio.StreamWriter) -> None:
        peer = cw.get_extra_info("peername")
        ip = peer[0] if peer else "?"
        if not (peer and allowed(ip, nets)):
            stats["refused"] += 1
            log(f"{ip} refused (not in --allow)")
            cw.close()
            return
        if stats["open"] >= cap or per_client.get(ip, 0) >= cap1:
            stats["refused"] += 1
            if stats["refused"] % 50 == 1:
                log(f"{ip} refused: too many connections ({stats['open']} open, {per_client.get(ip, 0)} from this PC)")
            cw.close()
            return
        stats["open"] += 1                                 # counted from here: a slow connect is an open connection too
        per_client[ip] = per_client.get(ip, 0) + 1
        uw = None
        try:
            try:
                target = await asyncio.wait_for(resolve_remote(host, port, allow_local), timeout)
                if target is None:
                    raise ConnectionRefusedError("the target is this PC")
                ur, uw = await asyncio.wait_for(asyncio.open_connection(target, port), timeout)
            except (OSError, asyncio.TimeoutError) as e:
                stats["failed"] += 1
                log(f"{ip} -> {host}:{port} FAILED ({e.__class__.__name__}) - is the portal laptop "
                    f"on the Smart Lab network and this PC's second adapter on 192.168.1.x?")
                return
            stats["total"] += 1
            seen = [time.monotonic()]
            jobs = [asyncio.ensure_future(_pipe(cr, uw, seen)), asyncio.ensure_future(_pipe(ur, cw, seen))]
            try:
                while True:
                    done, _ = await asyncio.wait(jobs, timeout=max(0.05, min(5.0, idle - (time.monotonic() - seen[0]))))
                    if len(done) == 2:
                        break
                    if time.monotonic() - seen[0] >= idle:
                        stats["idle"] += 1
                        break
            finally:
                for jb in jobs:
                    jb.cancel()
                await asyncio.gather(*jobs, return_exceptions=True)
        finally:
            stats["open"] -= 1
            per_client[ip] -= 1
            if per_client[ip] <= 0:
                per_client.pop(ip, None)
            for x in (cw, uw):
                try:
                    if x is not None:
                        x.close()
                except Exception:
                    pass
    return handle


async def serve(listen: str, maps: list[tuple[int, str, int]], allow: list | None = None, *, allow_local: bool = False,
                tries: int = 1, wait_s: float = BIND_WAIT_S) -> list:
    """Listens on exactly the address asked for. RELAY-1: it fell back to every interface when that failed (the university
    networks included); now it waits for the adapter and tries the SAME address again, then gives that port up."""
    servers = []
    for lport, host, rport in maps:
        for k in range(tries):
            try:
                servers.append(await asyncio.start_server(handler(host, rport, allow=allow, allow_local=allow_local), listen, lport))
                log(f"relay {listen}:{lport} -> {host}:{rport}")
                break
            except OSError as e:
                last = k == tries - 1
                log(f"cannot listen on {listen}:{lport} ({e.__class__.__name__} {getattr(e, 'winerror', None) or e.errno}) - "
                    + ("port in use or address not on this PC; NOT opened on any other address. Correct --listen." if last
                       else f"trying the same address again in {wait_s:.0f} s"))
                if not last:
                    await asyncio.sleep(wait_s)
    return servers


async def main_async(args) -> None:
    maps = [parse_map(m) for m in (args.map or DEFAULT_MAPS)]
    for _, host, rport in maps:                            # RELAY-2: never to itself
        try:
            if await resolve_remote(host, rport) is None:
                sys.exit(f"refused: {host} is this PC - the relay would connect to itself. Run it on the engineer PC, not on the portal laptop.")
        except OSError:
            pass                                           # name not resolvable now: checked again for every connection
    servers = await serve(args.listen, maps, args.allow or DEFAULT_ALLOW, tries=BIND_TRIES)
    log("clients allowed from: " + ", ".join(args.allow or DEFAULT_ALLOW))
    if not servers:
        sys.exit("nothing to relay")
    for _, host, rport in maps[:1]:
        try:
            target = await resolve_remote(host, rport)
            _, w = await asyncio.wait_for(asyncio.open_connection(target, rport), 3)
            w.close(); log(f"portal {host}:{rport} reachable from this PC - OK")
        except (OSError, asyncio.TimeoutError):
            log(f"WARNING: portal {host}:{rport} NOT reachable from this PC - check the USB-Ethernet adapter "
                f"(192.168.1.210 / 255.255.255.0, no gateway) and the cable to the Smart Lab router")
    while True:
        await asyncio.sleep(60)
        log(f"connections: {stats['open']} open, {stats['total']} total, {stats['failed']} failed, {stats['refused']} refused, "
            f"{stats['idle']} closed idle")


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
