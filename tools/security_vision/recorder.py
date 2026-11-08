"""
Video recording of the security camera, on THIS laptop (no cloud).

An administrator presses Record in the portal; the portal asks this service
(device key) to start / stop. FFmpeg copies the camera's own H.264 video
untouched (no re-encoding, little CPU) and converts only the camera's
G.711 audio to AAC so browsers can play it.

One recording runs until Stop and is SPLIT into parts of segment_minutes
(default 60): a new file starts at a key frame, so nothing is lost between
parts. Files are fragmented MP4: a part cut by a crash or power loss is
still playable up to that point.

    recordings/<DEVICE>_<YYYY-MM-DD_HH-MM-SS>.mp4   one part (named by its start time)
    recordings/<same name>.json                      its recording: who, when, part n of N, why it stopped

Nothing is ever deleted here. A recording stops on Stop, when the camera
stream ends, or when free disk space falls below min_free_gb (checked every
30 s); Start is refused below it.
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
TIME_FMT = "%Y-%m-%d_%H-%M-%S"


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


def ffmpeg_command(ffmpeg: str, source: str, pattern: str, segment_s: int) -> list[str]:
    """pattern: a path with strftime fields - each part is named by its start time."""
    rtsp = source.lower().startswith("rtsp://")
    # No -nostdin: stdin stays open, "q" on it ends the current part cleanly.
    return ([ffmpeg, "-hide_banner", "-loglevel", "error"]
            + (["-rtsp_transport", "tcp"] if rtsp else [])
            + ["-i", source, "-map", "0:v:0", "-map", "0:a:0?",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "32k",
               "-f", "segment", "-segment_time", str(segment_s), "-reset_timestamps", "1",
               "-strftime", "1", "-segment_format", "mp4",
               "-segment_format_options", "movflags=+frag_keyframe+empty_moov+default_base_moof",
               pattern])


def probe_duration(ffmpeg: Optional[str], path: str) -> Optional[float]:
    """The video's real length, read by ffprobe (next to ffmpeg); None if unavailable."""
    if not ffmpeg:
        return None
    probe = os.path.join(os.path.dirname(ffmpeg), "ffprobe" + (".exe" if ffmpeg.lower().endswith(".exe") else ""))
    if not os.path.isfile(probe):
        probe = shutil.which("ffprobe")
    if not probe:
        return None
    try:
        out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=15,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
        return round(float(out), 1)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _start_of(name: str) -> Optional[datetime]:
    try:
        return datetime.strptime(name[-23:-4], TIME_FMT)
    except ValueError:
        return None


class Recorder:
    def __init__(self, device: str, source: str, folder: str, *, ffmpeg: Optional[str] = None,
                 segment_minutes: int = 60, min_free_gb: float = 2.0, command=None):
        self.device = device
        self.source = source
        self.folder = folder
        self.ffmpeg = ffmpeg if ffmpeg is not None else find_ffmpeg()
        self.segment_s = int(segment_minutes * 60)
        self.min_free_gb = min_free_gb
        self._command = command or ffmpeg_command        # tests replace it
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._meta: dict = {}
        self._watch: Optional[threading.Thread] = None
        os.makedirs(folder, exist_ok=True)

    # ------------------------------------------------------------ status --
    def free_gb(self) -> float:
        return shutil.disk_usage(self.folder).free / 1e9

    def _parts(self) -> list[str]:
        """The current recording's files, oldest first."""
        t0 = self._meta.get("t0_name", "")
        return sorted(os.path.basename(p) for p in glob.glob(os.path.join(self.folder, f"{self.device}_*.mp4"))
                      if NAME_RE.match(os.path.basename(p)) and os.path.basename(p) >= t0)

    def status(self) -> dict:
        with self._lock:
            self._reap()
            rec = self._proc is not None
            parts = self._parts() if rec else []
            return {"recording": rec, "file": parts[-1] if parts else None, "parts": len(parts),
                    "started_at": self._meta.get("started_at") if rec else None,
                    "started_by": self._meta.get("started_by") if rec else None,
                    "elapsed_s": round(time.time() - self._meta["t0"], 1) if rec else None,
                    "segment_s": self.segment_s, "ffmpeg": bool(self.ffmpeg),
                    "free_gb": round(self.free_gb(), 1), "min_free_gb": self.min_free_gb}

    # ------------------------------------------------------- start / stop --
    def start(self, by: str = "") -> dict:
        with self._lock:
            self._reap()
            if self._proc is not None:
                return {"ok": False, "error": "already recording"}
            if not self.ffmpeg:
                return {"ok": False, "error": "FFmpeg is not installed on the laptop (winget install Gyan.FFmpeg)"}
            free = self.free_gb()
            if free < self.min_free_gb:
                return {"ok": False, "error": f"only {free:.1f} GB free on the laptop (needs {self.min_free_gb} GB)"}
            now = datetime.now()
            pattern = os.path.join(self.folder, f"{self.device}_%Y-%m-%d_%H-%M-%S.mp4")
            cmd = self._command(self.ffmpeg, self.source, pattern, self.segment_s)
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.PIPE, creationflags=flags)
            self._meta = {"device": self.device, "started_at": now.isoformat(timespec="seconds"),
                          "started_by": by, "t0": time.time(),
                          "t0_name": f"{self.device}_{now:{TIME_FMT}}.mp4"}
            self._watch = threading.Thread(target=self._disk_watch, args=(self._proc,), daemon=True)
            self._watch.start()
            return {"ok": True, "file": self._meta["t0_name"], "segment_s": self.segment_s}

    def stop(self, by: str = "", reason: str = "stopped") -> dict:
        with self._lock:
            self._reap()
            if self._proc is None:
                return {"ok": False, "error": "not recording"}
            proc = self._proc
            try:                                   # "q" = finish the current part cleanly
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
            return self._finish(reason, by)

    def _disk_watch(self, proc) -> None:
        while proc.poll() is None:
            time.sleep(30)
            if proc.poll() is None and self.free_gb() < self.min_free_gb:
                self.stop("", "disk_low")
                return

    def _reap(self) -> None:
        """A recording that ended by itself (camera stream lost)."""
        if self._proc is not None and self._proc.poll() is not None:
            err = (self._proc.stderr.read() or b"").decode(errors="replace").strip() if self._proc.stderr else ""
            self._finish("stream_ended", "", err[-300:])

    def _finish(self, reason: str, by: str, error: str = "") -> dict:
        stopped = datetime.now()
        parts = self._parts()
        total = 0
        for i, name in enumerate(parts):
            start = _start_of(name)
            end = _start_of(parts[i + 1]) if i + 1 < len(parts) else stopped
            size = os.path.getsize(os.path.join(self.folder, name))
            total += size
            meta = {"device": self.device, "file": name, "recording_started_at": self._meta["started_at"],
                    "started_by": self._meta.get("started_by", ""), "part": i + 1, "parts": len(parts),
                    "started_at": start.isoformat(timespec="seconds") if start else None,
                    "stopped_at": end.isoformat(timespec="seconds"),
                    # ffprobe's length (FFmpeg also writes the camera's buffered frames,
                    # so clock time understates it); clock time only as a fallback.
                    "duration_s": probe_duration(self.ffmpeg, os.path.join(self.folder, name))
                                  or (round((end - start).total_seconds(), 1) if start else None),
                    "size_bytes": size, "stopped_by": by, "stop_reason": reason}
            if error:
                meta["ffmpeg_error"] = error
            with open(os.path.join(self.folder, name[:-4] + ".json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=1)
        self._proc, self._meta = None, {}
        return {"ok": True, "file": parts[0] if parts else None, "parts": len(parts),
                "duration_s": round((stopped - _start_of(parts[0])).total_seconds(), 1) if parts and _start_of(parts[0]) else None,
                "size_bytes": total, "stop_reason": reason}

    # ------------------------------------------------------------- files --
    def list(self) -> list[dict]:
        st = self.status()                       # also closes a recording that ended by itself
        live = {st["file"]} if st["recording"] and st["file"] else set()   # only the part being written
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
            start = _start_of(name)
            out.append({"file": name, "size_bytes": os.path.getsize(path), "recording": name in live,
                        "started_at": meta.get("started_at") or (start.isoformat(timespec="seconds") if start else None),
                        **{k: meta.get(k) for k in ("stopped_at", "duration_s", "started_by", "stopped_by",
                                                    "stop_reason", "part", "parts", "recording_started_at")}})
        return out

    def remove(self, name: str, by: str = "") -> dict:
        """"Delete" from the list: the video and its notes move to deleted/
        next to the recordings - recoverable by hand, never erased here."""
        path = self.path_of(name)
        if path is None:
            return {"ok": False, "error": "No such recording"}
        st = self.status()
        if st["recording"] and st["file"] == name:
            return {"ok": False, "error": "This part is being recorded - press Stop first"}
        trash = os.path.join(self.folder, "deleted")
        os.makedirs(trash, exist_ok=True)
        for src in (path, path[:-4] + ".json"):
            if os.path.isfile(src):
                os.replace(src, os.path.join(trash, os.path.basename(src)))
        with open(os.path.join(trash, name[:-4] + ".deleted.json"), "w", encoding="utf-8") as f:
            json.dump({"deleted_by": by, "deleted_at": datetime.now().astimezone().isoformat(timespec="seconds")}, f)
        return {"ok": True, "file": name, "moved_to": trash}

    def path_of(self, name: str) -> Optional[str]:
        if not NAME_RE.match(name or ""):
            return None
        path = os.path.join(self.folder, name)
        return path if os.path.isfile(path) else None
