"""
Lab PC presence on the lab LAN - nothing installed on the PCs (2026-10-21).

The robots are read by asking them over the LAN; a plain Windows PC has no server to ask, but every
device on the LAN must answer ARP, and answers ping when its firewall allows it. Every CYCLE_S this
script (on the lab laptop - Docker cannot see the LAN's ARP) checks each PC listed in
lan_presence.json by its MAC address and posts the result to the portal:

  * ping from the lab cable's address (SOURCE_IP; this laptop is also on Wi-Fi in the same
    192.168.1.x range, so the source must be fixed) - a reply = present ("ping");
  * a PC that has ever answered ping and then misses MISSES_OFF in a row = absent (~6 s);
  * a PC whose firewall drops ping: the Windows neighbour table decides ("arp") - Reachable =
    present, Unreachable / no entry = absent; each ping still makes Windows re-check the entry,
    so a stale one is resolved within seconds (absent within ~15-50 s, Windows' ARP timing);
  * the PC's address is found from its MAC (a new DHCP address is followed): every SWEEP_S a UDP
    datagram to every address of the /24 refreshes the table.

Read-only towards the PCs: echo requests, UDP to the discard port, ARP. Python 3.12 stdlib only.
    py tools/lan_presence/lan_presence.py               (portal http://127.0.0.1:8000/api)
"""
from __future__ import annotations

import ctypes
import json
import os
import socket
import struct
import sys
import time
import urllib.error
import urllib.request
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CYCLE_S = 2.0
PING_TIMEOUT_MS = 500
MISSES_OFF = 3
SWEEP_S = 30.0

REACHABLE_STATES = {5, 6}          # NlnsReachable, NlnsPermanent
GONE_STATES = {0, 1}               # NlnsUnreachable, NlnsIncomplete
# 2 Probe, 3 Delay, 4 Stale: Windows is re-checking - keep the last decision


def norm_mac(m: str) -> str:
    return m.strip().lower().replace(":", "-")


# ------------------------------------------------------------------ Windows ---
class _Win:
    def __init__(self):
        self.ip = ctypes.WinDLL("iphlpapi")
        self.ip.IcmpCreateFile.restype = wintypes.HANDLE
        self.ip.IcmpSendEcho2Ex.restype = wintypes.DWORD
        self.ip.IcmpSendEcho2Ex.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                            wintypes.ULONG, wintypes.ULONG, ctypes.c_void_p, wintypes.WORD,
                                            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
        self.ip.GetIpNetTable2.argtypes = [ctypes.c_ushort, ctypes.POINTER(ctypes.c_void_p)]
        self.ip.FreeMibTable.argtypes = [ctypes.c_void_p]
        self.icmp = self.ip.IcmpCreateFile()

    @staticmethod
    def _addr(ip: str) -> int:
        return struct.unpack("<I", socket.inet_aton(ip))[0]     # IPAddr: network byte order in a ULONG

    def ping(self, src: str, dst: str, timeout_ms: int) -> bool:
        data = b"smartlab"
        reply = ctypes.create_string_buffer(256)
        n = self.ip.IcmpSendEcho2Ex(self.icmp, None, None, None, self._addr(src), self._addr(dst),
                                    data, len(data), None, reply, len(reply), timeout_ms)
        if not n:
            return False
        addr, status = struct.unpack_from("<II", reply.raw, 0)    # ICMP_ECHO_REPLY: Address, Status
        return status == 0 and addr == self._addr(dst)

    def neighbours(self) -> list[tuple[str, str, int]]:
        """(ip, mac, state) for every IPv4 neighbour entry (all interfaces)."""
        p = ctypes.c_void_p()
        if self.ip.GetIpNetTable2(socket.AF_INET, ctypes.byref(p)) != 0 or not p.value:
            return []
        try:
            n = ctypes.c_ulong.from_address(p.value).value
            out, base, size = [], p.value + 8, 88                     # MIB_IPNET_ROW2, 8-byte aligned
            for i in range(n):
                row = ctypes.string_at(base + i * size, size)
                ip = socket.inet_ntoa(row[4:8])
                ln = struct.unpack_from("<I", row, 72)[0]
                mac = "-".join(f"{b:02x}" for b in row[40:40 + min(ln, 8)])
                state = struct.unpack_from("<i", row, 76)[0]
                out.append((ip, mac, state))
            return out
        finally:
            self.ip.FreeMibTable(p)


# ------------------------------------------------------------------- logic ---
class Pc:
    def __init__(self, cfg: dict):
        self.uid, self.tag = cfg["device_uid"], cfg.get("asset_tag")
        self.mac = norm_mac(cfg["mac"])
        self.ip: str | None = cfg.get("ip")
        self.present = False
        self.via = "none"
        self.icmp_ok = False          # has this PC ever answered ping? (firewall allows it)
        self.misses = 0

    def decide(self, pinged: bool, state: int | None) -> None:
        """One cycle's evidence -> present / absent (state None = no neighbour entry for its MAC)."""
        if pinged:
            self.icmp_ok, self.misses, self.present, self.via = True, 0, True, "ping"
            return
        if self.icmp_ok:
            self.misses += 1
            if self.misses >= MISSES_OFF:
                self.present, self.via = False, "ping"
            return
        if state in REACHABLE_STATES:
            self.present, self.via = True, "arp"
        elif state is None or state in GONE_STATES:
            self.present, self.via = False, "arp"
        # Probe / Delay / Stale: keep the last decision while Windows re-checks


def sweep(src: str) -> None:
    """A UDP datagram to the discard port of every address in the /24 makes Windows ARP for it."""
    net = src.rsplit(".", 1)[0]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind((src, 0))
        s.setblocking(False)
        for i in range(1, 255):
            ip = f"{net}.{i}"
            if ip != src:
                try:
                    s.sendto(b"", (ip, 9))
                except OSError:
                    pass
    finally:
        s.close()


def read_key() -> str:
    """DEVICE_API_KEY from the environment or the repo's .env (never printed)."""
    if os.environ.get("DEVICE_API_KEY"):
        return os.environ["DEVICE_API_KEY"]
    env = HERE.parents[1] / ".env"
    for line in env.read_text(encoding="utf-8").splitlines() if env.exists() else []:
        if line.startswith("DEVICE_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    sys.exit("DEVICE_API_KEY not found (environment or .env)")


def post(portal: str, key: str, lab: str, pcs: list[Pc]) -> str:
    body = json.dumps({"lab_id": lab, "pcs": [{"device_uid": p.uid, "asset_tag": p.tag, "present": p.present,
                                               "ip": p.ip, "mac": p.mac, "via": p.via} for p in pcs]}).encode()
    rq = urllib.request.Request(portal.rstrip("/") + "/equipment/pc/presence", data=body, method="POST",
                                headers={"Content-Type": "application/json", "X-Device-Key": key})
    try:
        with urllib.request.urlopen(rq, timeout=5) as r:
            return f"{r.status}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"
    except OSError as e:
        return f"portal unreachable ({e.__class__.__name__})"


def main() -> None:
    cfg = json.loads((HERE / "lan_presence.json").read_text(encoding="utf-8"))
    src, lab = cfg["source_ip"], cfg.get("lab", "LAB_01")
    portal = os.environ.get("PORTAL", cfg.get("portal", "http://127.0.0.1:8000/api"))
    pcs = [Pc(c) for c in cfg["pcs"]]
    key, win = read_key(), _Win()
    log = (HERE / "presence_log.jsonl").open("a", encoding="utf-8")
    print(f"LAN presence: {len(pcs)} PC(s), from {src}, every {CYCLE_S:g} s -> {portal}")
    last_sweep, last_post = 0.0, ""
    while True:
        t0 = time.monotonic()
        if t0 - last_sweep > SWEEP_S or any(p.ip is None for p in pcs) and t0 - last_sweep > 5:
            sweep(src)
            last_sweep = t0
            time.sleep(0.3)
        pinged = {p.uid: bool(p.ip) and win.ping(src, p.ip, PING_TIMEOUT_MS) for p in pcs}
        table = win.neighbours()
        for p in pcs:
            rows = [r for r in table if r[1] == p.mac]
            best = max(rows, key=lambda r: r[2] in REACHABLE_STATES) if rows else None
            if best and best[0] != p.ip:
                p.ip = best[0]                               # followed a new address (DHCP)
            was = p.present
            p.decide(pinged[p.uid], best[2] if best else None)
            if p.present != was:
                stamp = datetime.now().isoformat(timespec="milliseconds")
                print(f"{stamp}  {p.tag or p.uid}: {'CONNECTED' if p.present else 'DISCONNECTED'} ({p.via}, {p.ip})")
                log.write(json.dumps({"at": stamp, "pc": p.uid, "present": p.present, "via": p.via, "ip": p.ip}) + "\n")
                log.flush()
        res = post(portal, key, lab, pcs)
        if res != last_post:
            print(f"{datetime.now():%H:%M:%S}  portal: {res}")
            last_post = res
        time.sleep(max(0.0, CYCLE_S - (time.monotonic() - t0)))


if __name__ == "__main__":
    main()
