---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/ur_dashboard.py"
source_hash: "6d776b8071acefce75b731d7f5c744fcb0c0cb7e75323ec0a826abb04c46e0fd"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/ur_dashboard.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_services_robot_control.py]] - imports
- [[docs_ROBOT_CONTROL.md]] - mentioned by docs

```py
"""
UR5e Dashboard Server client (TCP 29999) - used ONLY when ROBOT_CONTROL=live (never by default).

Reads: remote/local mode, robot mode, safety status, program state. Commands: load the ONE
configured HOME program, play, stop. Nothing else is ever sent: no motion scripts, no URScript,
no I/O. See docs/ROBOT_CONTROL.md - live mode is switched on only after commissioning at the lab.
"""
from __future__ import annotations

import socket

ALLOWED = ("is in remote control", "robotmode", "safetystatus", "programState", "get loaded program",
           "play", "stop")


class Dashboard:
    def __init__(self, host: str, timeout: float = 2.0):
        self.host, self.timeout = host, timeout

    def ask(self, cmd: str) -> str:
        if cmd not in ALLOWED and not cmd.startswith("load "):
            raise ValueError(f"not an allowed dashboard command: {cmd!r}")
        with socket.create_connection((self.host, 29999), timeout=self.timeout) as s:
            s.settimeout(self.timeout)
            s.recv(1024)                                   # welcome banner
            s.sendall((cmd + "\n").encode())
            return s.recv(1024).decode(errors="replace").strip()

    def mode(self) -> str:
        """REMOTE_READY only when every condition holds; anything else blocks commands."""
        try:
            if self.ask("is in remote control").lower() != "true":
                return "LOCAL_PENDANT"
            if "NORMAL" not in self.ask("safetystatus").upper():
                return "SAFETY_STOP"
            if "RUNNING" not in self.ask("robotmode").upper():
                return "NOT_POWERED"
            if "PLAYING" in self.ask("programState").upper():
                return "PROGRAM_RUNNING"
            return "REMOTE_READY"
        except (OSError, ValueError):
            return "UNREACHABLE"

```
