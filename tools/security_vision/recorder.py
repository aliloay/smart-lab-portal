"""
Video recording of the security camera, on THIS laptop (no cloud).

An administrator presses Record in the portal; the portal asks this service
(device key) to start / stop. FFmpeg copies the camera's own H.264 video
untouched (no re-encoding, little CPU) and converts only the camera's
G.711 audio to AAC so browsers can play it. Files are fragmented MP4: a
recording cut by a crash or power loss is still playable up to that point.

    recordings/<DEVICE>_<YYYY-MM-DD_HH-MM-SS>.mp4     the video
    recordings/<same name>.json                         who, when, how long, why it stopped

Nothing is ever deleted here. A recording stops on Stop, after
max_minutes, or if the camera stream ends. Start is refused while free disk
space is below min_free_gb.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.mp4$")


def find_ffmpeg() -> Optional[str]:
    """FFMPEG env var, then PATH, then winget's install folder."""
    env = os.environ.get("FFMPEG")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    pattern = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages",
                           "Gyan.FFmpeg*", "ffmpeg-*", "bin", "ffmpeg.exe")
    hits = sorted(glob.glob(pattern))
    return hits[-1] if hits else None


def ffmpeg_command(ffmpeg: str, source: str, out: str, max_s: int) -> list[str]:
    rtsp = source.lower().startswith("rtsp://")
    # No -nostdin: stdin stays open, "q" on it ends the file cleanly.
    return ([ffmpeg, "-hide_banner", "-loglevel", "error"]
            + (["-rtsp_transport", "tcp"] if rtsp else [])
            + ["-i", source, "-map", "0:v:0", "-map", "0:a:0?",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "32k",
               "-t", str(max_s),
               "-movflags", "+frag_keyframe+empty_moov+default_base_moof",
               "-f", "mp4", "-y", out])


class Recorder:
    def __init__(self, device: str, source: str, folder: str, *, ffmpeg: Optional[str] = None,
                 max_minutes: int = 60, min_free_gb: float = 2.0, command=None):
        self.device = device
        self.source = source
        self.folder = folder
        self.ffmpeg = ffmpeg if ffmpeg is not None else find_ffmpeg()
        self.max_s = int(max_minutes * 60)
        self.min_free_gb = min_free_gb
        self._command = command or ffmpeg_command        # tests replace it
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._file: Optional[str] = None
        self._meta: dict = {}
        os.makedirs(folder, exist_ok=True)

    # ------------------------------------------------------------ status --
    def free_gb(self) -> float:
        return shutil.disk_usage(self.folder).free / 1e9

    def status(self) -> dict:
        with self._lock:
            self._reap()
            rec = self._proc is not None
            return {"recording": rec, "file": os.path.basename(self._file) if rec else None,
                    "started_at": self._meta.get("started_at") if rec else None,
                    "started_by": self._meta.get("started_by") if rec else None,
                    "elapsed_s": round(time.time() - self._meta["t0"], 1) if rec else None,
                    "max_s": self.max_s, "ffmpeg": bool(self.ffmpeg),
                    "free_gb": round(self.free_gb(), 1), "min_free_gb": self.min_free_gb}

    # ------------------------------------------------------- start / stop --
    def start(self, by: str = "") -> dict:
        with self._lock:
            self._reap()
            if self._proc is not None:
                return {"ok": False, "error": "already recording", "file": os.path.basename(self._file)}
            if not self.ffmpeg:
                return {"ok": False, "error": "FFmpeg is not installed on the laptop (winget install Gyan.FFmpeg)"}
            free = self.free_gb()
            if free < self.min_free_gb:
                return {"ok": False, "error": f"only {free:.1f} GB free on the laptop (needs {self.min_free_gb} GB)"}
            now = datetime.now()
            name = f"{self.device}_{now:%Y-%m-%d_%H-%M-%S}.mp4"
            path = os.path.join(self.folder, name)
            cmd = self._command(self.ffmpeg, self.source, path, self.max_s)
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.PIPE, creationflags=flags)
            self._file = path
            self._meta = {"device": self.device, "file": name, "started_at": now.isoformat(timespec="seconds"),
                          "started_by": by, "t0": time.time()}
            self._write_meta()
            return {"ok": True, "file": name}

    def stop(self, by: str = "", reason: str = "stopped") -> dict:
        with self._lock:
            self._reap()
            if self._proc is None:
                return {"ok": False, "error": "not recording"}
            proc, name = self._proc, os.path.basename(self._file)
            try:                                   # "q" = finish the file cleanly
                proc.stdin.write(b"q")
                proc.stdin.flush()
                proc.stdin.close()
            except OSError:
                pass
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            self._finish(reason, by)
            return {"ok": True, "file": name, "duration_s": self._meta.get("duration_s"),
                    "size_bytes": self._meta.get("size_bytes")}

    def _reap(self) -> None:
        """A recording that ended by itself (max length, stream lost)."""
        if self._proc is not None and self._proc.poll() is not None:
            err = (self._proc.stderr.read() or b"").decode(errors="replace").strip() if self._proc.stderr else ""
            reached = time.time() - self._meta.get("t0", time.time()) >= self.max_s - 2
            self._finish("max_length" if reached else "stream_ended", "", err[-300:])

    def _finish(self, reason: str, by: str, error: str = "") -> None:
        self._meta.update({"stopped_at": datetime.now().isoformat(timespec="seconds"),
                           "stopped_by": by, "stop_reason": reason,
                           "duration_s": round(time.time() - self._meta["t0"], 1),
                           "size_bytes": os.path.getsize(self._file) if os.path.isfile(self._file) else 0})
        if error:
            self._meta["ffmpeg_error"] = error
        self._write_meta()
        self._proc, self._file = None, None

    def _write_meta(self) -> None:
        meta = {k: v for k, v in self._meta.items() if k != "t0"}
        with open(os.path.join(self.folder, meta["file"][:-4] + ".json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)

    # ------------------------------------------------------------- files --
    def list(self) -> list[dict]:
        self.status()                               # finish a recording that ended by itself
        out = []
        for path in sorted(glob.glob(os.path.join(self.folder, "*.mp4")), reverse=True):
            name = os.path.basename(path)
            if not NAME_RE.match(name):
                continue
            meta = {}
            try:
                with open(path[:-4] + ".json", encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                pass
            out.append({"file": name, "size_bytes": os.path.getsize(path),
                        "recording": self._file is not None and os.path.basename(self._file) == name,
                        **{k: meta.get(k) for k in ("started_at", "stopped_at", "duration_s",
                                                    "started_by", "stopped_by", "stop_reason")}})
        return out

    def path_of(self, name: str) -> Optional[str]:
        if not NAME_RE.match(name or ""):
            return None
        path = os.path.join(self.folder, name)
        return path if os.path.isfile(path) else None
