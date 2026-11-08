---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/lan_presence.py"
source_hash: "d6d4b470d79888a85fb14d84fa1f300c2309e2f4ed7e4a66b4bbddbcd7237642"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/lan_presence.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_equipment.py]] - imports
- [[backend_app_api_routes_security.py]] - imports

```py
"""
Lab PCs seen on the lab LAN, with nothing installed on the PC (2026-10-21).

The robots are read over the LAN by a collector that asks them; a plain Windows PC has no such server,
but it must answer ARP (and ping, if its firewall allows). tools/lan_presence runs on the lab laptop
(Docker cannot see the LAN's ARP), checks each configured PC by its MAC address every ~2 s and posts
the result here. So a PC shows ON within seconds of its cable going in and it booting, and OFF when the
cable comes out or it shuts down - with or without the PC agent.

Kept in memory, like the screen frames: the collector reposts every cycle, so a restart loses nothing
that matters. A report older than STALE_S means the collector stopped: the state is then unknown
(None), never a guess. Each change (connected / disconnected) is written to the audit log.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional

STALE_S = 15.0

_lock = threading.Lock()
_state: dict[str, dict] = {}            # device_uid -> {present, ip, mac, via, seen_at, since}


def update(device_uid: str, present: bool, ip: Optional[str], mac: Optional[str], via: str,
           now: Optional[datetime] = None) -> Optional[bool]:
    """Store one report. Returns the new value when it changed (True = connected, False =
    disconnected), else None. The first report after a restart is a change only if it says present
    - "absent" after a restart is not news."""
    now = now or datetime.now(timezone.utc)
    with _lock:
        old = _state.get(device_uid)
        changed = (old is None and present) or (old is not None and old["present"] != present)
        since = now if (old is None or changed) else old["since"]
        _state[device_uid] = {"present": present, "ip": ip, "mac": mac, "via": via,
                              "seen_at": now, "since": since}
    return present if changed else None


def get(device_uid: str, now: Optional[datetime] = None) -> Optional[dict]:
    """The PC's LAN state for the API, or None (never reported / collector stopped)."""
    now = now or datetime.now(timezone.utc)
    with _lock:
        s = _state.get(device_uid)
    if s is None or (now - s["seen_at"]).total_seconds() > STALE_S:
        return None
    return {"present": s["present"], "ip": s["ip"], "mac": s["mac"], "via": s["via"],
            "since": s["since"], "checked_at": s["seen_at"]}


def clear() -> None:
    with _lock:
        _state.clear()

```
