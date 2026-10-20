"""
Who is driving the UR5e right now - READ-ONLY, from what the controller itself reports.

Signals (none of them can move the robot):
  * RTDE robot_status_bits (receive): bit 0 power on, bit 1 program running, bit 2 teach button
    (freedrive / hand-guiding) pressed, bit 3 power button pressed.
  * Dashboard Server (port 29999) QUERIES only: "is in remote control", "get loaded program",
    "programState". DashboardReader below refuses every other command - it cannot load, play or stop.

What can be known:
  HAND_GUIDING    teach (freedrive) button pressed - someone is moving the arm by hand
  PENDANT         Local control mode: only the teach pendant can start programs
  REMOTE_PROGRAM  Remote control mode and a program is playing (started over the network,
                  e.g. the portal's Home or a ROS / Dashboard client)
  REMOTE_DIRECT   Remote mode, no program playing, but the joints move: direct commands over the
                  network (e.g. ROS 2 driver / URScript / RTDE control)
  IDLE / UNKNOWN
What can NOT be known: WHICH laptop or person sent a network command - the controller does not say.
"""
from __future__ import annotations

import socket
import threading
import time
from typing import Optional

TEACH_BUTTON_BIT = 1 << 2
PROGRAM_RUNNING_BIT = 1 << 1


def classify(extra: dict, moving: bool) -> tuple[str, str]:
    bits = extra.get("robot_status_bits")
    remote = extra.get("remote_control")             # True / False / None (dashboard not readable)
    prog = extra.get("loaded_program") or ""
    pstate = str(extra.get("program_state") or "").upper()
    running = ("PLAYING" in pstate) or (isinstance(bits, int) and bool(bits & PROGRAM_RUNNING_BIT))
    if isinstance(bits, int) and bits & TEACH_BUTTON_BIT:
        return "HAND_GUIDING", "Freedrive: the arm is being moved by hand (teach button pressed)"
    if remote is False:
        return "PENDANT", ("Teach pendant (Local mode)" + (f" - program {prog} running" if running and prog else
                           " - program running" if running else " - jogging or idle" if moving else " - idle"))
    if remote is True:
        if running:
            return "REMOTE_PROGRAM", f"Remote mode - program {prog or '(unnamed)'} started over the network"
        if moving:
            return "REMOTE_DIRECT", "Remote mode - moved by direct network commands (e.g. ROS 2 driver / URScript)"
        return "IDLE", "Remote mode - idle"
    if running:
        return "UNKNOWN", "A program is running - control mode not readable"
    return ("UNKNOWN", "Moving - control mode not readable") if moving else ("IDLE", "Idle")


class DashboardReader:
    """Polls the three read-only Dashboard queries in the background. Never sends anything else."""
    QUERIES = ("is in remote control", "get loaded program", "programState")

    def __init__(self, host: str, period_s: float = 2.0, timeout: float = 1.5):
        self.host, self.period_s, self.timeout = host, period_s, timeout
        self.state: dict = {}
        self.ok_at = 0.0
        self._stop = False

    def ask(self, cmd: str) -> str:
        if cmd not in self.QUERIES:
            raise ValueError(f"refused: {cmd!r} is not a read-only query")
        with socket.create_connection((self.host, 29999), timeout=self.timeout) as s:
            s.settimeout(self.timeout)
            s.recv(1024)                                     # welcome banner
            s.sendall((cmd + "\n").encode())
            return s.recv(1024).decode(errors="replace").strip()

    def poll_once(self) -> None:
        r = self.ask("is in remote control").lower()
        prog = self.ask("get loaded program")
        st = self.ask("programState")
        self.state = {"remote_control": r == "true" if r in ("true", "false") else None,
                      "loaded_program": prog.split(":", 1)[-1].strip().split("/")[-1][:60] if "loaded program" in prog.lower() else None,
                      "program_state": st.split()[0][:20] if st else None}
        self.ok_at = time.time()

    def start(self) -> None:
        def loop():
            while not self._stop:
                try:
                    self.poll_once()
                except Exception:
                    if time.time() - self.ok_at > 3 * self.period_s:
                        self.state = {}                       # unknown, never a stale guess
                time.sleep(self.period_s)
        threading.Thread(target=loop, daemon=True, name="dashboard-read").start()

    def current(self) -> dict:
        return dict(self.state) if time.time() - self.ok_at <= 3 * self.period_s else {}
