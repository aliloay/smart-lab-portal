"""Local services, cameras, laptop resources and network - probes only, nothing is started or stopped."""
from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..utils.api_client import Client
from ..utils.freshness import NOT_ACCESSIBLE, OFFLINE, ONLINE, UNKNOWN


def services(c: Client) -> list[dict]:
    """Probe every configured local health URL in parallel."""
    items = list(c.cfg.services.items())
    with ThreadPoolExecutor(max_workers=len(items) or 1) as ex:
        res = list(ex.map(lambda kv: c.probe(kv[1][0]), items))
    out = []
    for (name, (url, desc)), r in zip(items, res):
        out.append({"service": name, "status": ONLINE if r["state"] == "UP" else OFFLINE if r["state"] == "DOWN" else UNKNOWN,
                    "http": r["http"], "ms": r["ms"], "url": url, "what": desc,
                    **({"detail": r["detail"]} if r.get("detail") else {})})
    return out


def camera_metrics(c: Client) -> list[dict]:
    """The camera services' own metrics: is a picture arriving, how fast is analysis, which engine."""
    rows = []
    for i, port in enumerate(c.cfg.camera_ports, 1):
        row: dict[str, Any] = {"camera": i, "port": port}
        try:
            st, m, _ = c.camera(port, "/metrics")
        except Exception as e:  # noqa: BLE001
            rows.append({**row, "service": OFFLINE, "picture": UNKNOWN, "detail": getattr(e, "message", str(e))})
            continue
        if st == 401:
            rows.append({**row, "service": ONLINE, "picture": NOT_ACCESSIBLE,
                         "detail": "metrics need the device key (set SMARTLAB_REPO or SMARTLAB_DEVICE_KEY)"})
            continue
        cap, ana, eng, gpu = (m.get("capture", {}), m.get("analysis", {}), m.get("engines", {}), m.get("gpu", {})) \
            if isinstance(m, dict) else ({}, {}, {}, {})
        fps = cap.get("fps") or 0
        rows.append({**row, "service": ONLINE,
                     "picture": ONLINE if fps and fps > 0 else OFFLINE,
                     "capture_fps": fps, "analysis_fps": ana.get("fps"), "detect_ms": ana.get("detect_ms"),
                     "open_failures": cap.get("open_failures"), "reconnects": cap.get("reconnects"),
                     "detector": eng.get("detector"), "reid": eng.get("reid"),
                     "gpu_mem_used_mb": gpu.get("mem_used_mb"), "gpu_mem_total_mb": gpu.get("mem_total_mb")})
    return rows


class _MemStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def resources(c: Client) -> dict:
    out: dict[str, Any] = {"host": socket.gethostname(), "os": f"{platform.system()} {platform.release()}",
                           "cpu_count": os.cpu_count()}
    if os.name == "nt":
        ms = _MemStatus()
        ms.dwLength = ctypes.sizeof(_MemStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
            out["ram_total_gb"] = round(ms.ullTotalPhys / 2**30, 1)
            out["ram_free_gb"] = round(ms.ullAvailPhys / 2**30, 1)
            out["ram_used_pct"] = ms.dwMemoryLoad
    disks = []
    for root in ([f"{d}:\\" for d in "CD"] if os.name == "nt" else ["/"]):
        if os.path.exists(root):
            u = shutil.disk_usage(root)
            disks.append({"disk": root, "total_gb": round(u.total / 2**30), "free_gb": round(u.free / 2**30),
                          "used_pct": round(100 * u.used / u.total)})
    out["disks"] = disks
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            r = subprocess.run([smi, "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                                "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=6)
            n, used, total, util = [x.strip() for x in r.stdout.strip().split(",")[:4]]
            out["gpu"] = {"name": n, "mem_used_mb": int(used), "mem_total_mb": int(total), "util_pct": int(util)}
        except (OSError, ValueError, subprocess.SubprocessError):
            out["gpu"] = UNKNOWN
    return out


def docker_containers() -> dict:
    """`docker ps` (read-only). Returns containers with their health, or why it could not be read."""
    exe = shutil.which("docker")
    if not exe:
        return {"status": "NOT_CONFIGURED", "containers": []}
    try:
        r = subprocess.run([exe, "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        return {"status": NOT_ACCESSIBLE, "detail": str(e), "containers": []}
    if r.returncode != 0:
        return {"status": NOT_ACCESSIBLE, "detail": r.stderr.strip()[:200], "containers": []}
    rows = []
    for line in r.stdout.strip().splitlines():
        name, status, image = (line.split("\t") + ["", "", ""])[:3]
        health = "healthy" if "(healthy)" in status else "unhealthy" if "unhealthy" in status else \
                 "starting" if "starting" in status else "running" if status.startswith("Up") else "stopped"
        rows.append({"name": name, "health": health, "status": status, "image": image})
    return {"status": ONLINE if rows else OFFLINE, "containers": rows}


def interfaces() -> list[dict]:
    """IPv4 addresses per adapter from `ipconfig` (Windows) - read-only."""
    if os.name != "nt":
        return [{"address": a[4][0]} for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    r = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=10)
    rows, cur = [], None
    for line in r.stdout.splitlines():
        if line and not line.startswith(" ") and line.rstrip().endswith(":"):
            cur = line.rstrip(": ").strip()
        m = re.search(r"IPv4 Address[ .]*: ([\d.]+)", line)
        if m and cur:
            rows.append({"adapter": cur, "ipv4": m.group(1)})
        g = re.search(r"Default Gateway[ .]*: ([\d.]+)", line)
        if g and rows and rows[-1]["adapter"] == cur:
            rows[-1]["gateway"] = g.group(1)
    return rows


def ping(host: str, timeout_ms: int = 800) -> dict:
    """One ICMP echo via the system ping. The host is validated to be an IP or hostname (no shell)."""
    if not re.fullmatch(r"[A-Za-z0-9.\-]{1,253}", host or ""):
        return {"host": host, "reachable": False, "detail": "invalid host"}
    args = ["ping", "-n", "1", "-w", str(timeout_ms), host] if os.name == "nt" else ["ping", "-c", "1", "-W", "1", host]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return {"host": host, "reachable": False, "detail": "ping failed to run"}
    m = re.search(r"time[=<](\d+)\s*ms", r.stdout)
    ok = r.returncode == 0 and ("TTL=" in r.stdout or "ttl=" in r.stdout)
    return {"host": host, "reachable": ok, "ms": int(m.group(1)) if (ok and m) else None}
