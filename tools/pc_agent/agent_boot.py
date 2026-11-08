"""
What Windows starts at sign-in on a lab PC (2026-11-04): a small supervisor for the agent, and on the engineer's
PC also for the relay.

  * the agent or the relay crashes -> started again, no sign-in needed (a dead relay cuts every lab PC off);
  * the relay cannot listen yet because the network is still coming up at sign-in -> it simply tries again;
  * the agent updated itself (exit code 75) -> started again with the new files;
  * the new files crash before their first good report to the portal -> rolled back, that bundle is never retried.

Settings come from smartlab.json next to the kit, written by INSTALL_SMARTLAB.ps1. Nothing here needs admin rights.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
TEMP = os.environ.get("TEMP", ".")
LOG_MAX = 5_000_000
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

if sys.stdout is None or sys.stderr is None:      # pythonw: no console
    sys.stdout = sys.stderr = open(os.path.join(TEMP, "smartlab_boot.log"), "a", encoding="utf-8", buffering=1)

import agent_update  # noqa: E402


def say(text: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), text, flush=True)


def rotate(path: str) -> None:
    """One old copy per log, so a PC left on for months cannot fill its disk."""
    try:
        if os.path.getsize(path) > LOG_MAX:
            os.replace(path, path + ".1")
    except OSError:
        pass


def first_copy() -> bool:
    """A second supervisor in this session leaves at once."""
    if sys.platform != "win32":
        return True
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    first_copy.handle = kernel32.CreateMutexW(None, False, "Local\\SmartLabAgentBoot")     # kept for the process's life
    return ctypes.get_last_error() != 183                                                 # ERROR_ALREADY_EXISTS


def relay_loop(base: str, relay_args: list, stop: threading.Event) -> None:
    """python.exe, not pythonw: Windows Firewall allows exactly this program on the engineer's PC."""
    exe = os.path.join(os.path.dirname(sys.executable), "python.exe")
    cmd = [exe, "-u", "-X", "utf8", "-E", "-s", os.path.join(base, "relay", "relay.py")] + relay_args
    log = os.path.join(TEMP, "smartlab_relay.log")
    child = None
    while not stop.is_set():
        rotate(log)
        with open(log, "a", encoding="utf-8") as out:
            child = subprocess.Popen(cmd, cwd=base, stdout=out, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
        while child.poll() is None and not stop.is_set():
            time.sleep(1)
        if child.poll() is None:
            child.terminate()
            return
        say(f"[relay] stopped with code {child.returncode}; starting it again in 5 s")
        stop.wait(5)


def agent_loop(base: str, agent_args: list, spawn=subprocess.Popen, sleep=time.sleep, wait_for_other: bool = False) -> None:
    # -u -X utf8 and an explicit log: a child of pythonw otherwise gets a dead pipe as its output, where its prints
    # vanish and, once the buffer fills, crash it (found by the kit simulation, 2026-11-04). UTF-8: an Arabic message
    # must not be able to stop the agent while it is written to the log.
    cmd = [sys.executable, "-u", "-X", "utf8", "-E", "-s", os.path.join(HERE, "pc_agent.py"), "--supervised"] + agent_args
    log = os.path.join(TEMP, "smartlab_agent.log")
    backoff = 2.0
    while True:
        rotate(log)
        t0 = time.monotonic()
        with open(log, "a", encoding="utf-8") as out:
            rc = spawn(cmd, cwd=base, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                       creationflags=NO_WINDOW).wait()
        ran = time.monotonic() - t0
        if rc == agent_update.EXIT_UPDATED:
            say("[agent] updated; starting the new version")
            backoff = 2.0
            continue
        if rc == 0:                                # another agent already serves this PC
            if not wait_for_other:
                say("[agent] another agent is running here; leaving")
                return
            # Another Windows account is signed in too: only one agent may speak for a PC. Take over when it signs out.
            say("[agent] another account's agent serves this PC; checking again in 60 s")
            sleep(60)
            continue
        if agent_update.read_state(HERE).get("pending_health"):
            say(f"[agent] the new version stopped with code {rc} before reporting; rolling back")
            agent_update.rollback(HERE)
            backoff = 2.0
            continue
        say(f"[agent] stopped with code {rc} after {ran:.0f} s; starting it again in {backoff:.0f} s")
        sleep(backoff)
        backoff = 2.0 if ran > 60 else min(60.0, backoff * 2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    if not first_copy():
        return
    with open(args.config, encoding="utf-8-sig") as f:         # written by PowerShell, which may add a BOM
        cfg = json.load(f)
    base = os.path.dirname(os.path.abspath(args.config))
    say(f"[boot] started for {cfg.get('agent_args')}")
    stop = threading.Event()
    relay = None
    if cfg.get("relay_args"):
        relay = threading.Thread(target=relay_loop, args=(base, cfg["relay_args"], stop), daemon=True)
        relay.start()
    import status_tray
    status_tray.write_state("starting")
    status_tray.start(str(cfg.get("device", "")), stop)
    agent_loop(base, cfg["agent_args"], wait_for_other=bool(cfg.get("wait_for_other_account")))
    stop.set()
    if relay:
        relay.join(3)


if __name__ == "__main__":
    main()
