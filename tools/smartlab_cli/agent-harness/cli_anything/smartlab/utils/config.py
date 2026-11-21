"""Configuration for the read-only Smart Lab CLI.

Nothing machine-specific is hard-coded. Every value comes from an environment variable, the optional
user config file (~/.smartlab/config.json) or a safe default. Secrets (KB service key, device key, login
token) are only ever read from where the Smart Lab itself keeps them and are never printed.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

USER_DIR = Path(os.environ.get("SMARTLAB_HOME", str(Path.home() / ".smartlab")))
USER_CONFIG = USER_DIR / "config.json"
TOKEN_FILE = USER_DIR / "token.json"

# Local helper services started by launch.bat (all 127.0.0.1). Same list as tools/ops/watchdog.py,
# plus the face server and Ollama.
DEFAULT_SERVICES = {
    "portal": ("http://localhost:8000/api/health", "Portal API (FastAPI in Docker)"),
    "n8n": ("http://127.0.0.1:5678/healthz", "n8n automations (Docker)"),
    "face": ("http://127.0.0.1:5000/health", "Face server (door face recognition)"),
    "camera1": ("http://127.0.0.1:5100/health", "Security camera 1 service"),
    "camera2": ("http://127.0.0.1:5101/health", "Security camera 2 service"),
    "knowledge": ("http://127.0.0.1:5199/health", "Knowledge service (vault search + assistant)"),
    "voice": ("http://127.0.0.1:5320/health", "Voice service (Whisper STT / Piper TTS)"),
    "ollama": ("http://127.0.0.1:11434/api/version", "Ollama local LLM server"),
}


def _user_config() -> dict:
    try:
        return json.loads(USER_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def find_repo(start: Optional[Path] = None) -> Optional[Path]:
    """The Smart Lab repo: SMARTLAB_REPO, the user config, or the first parent of the cwd that looks like it."""
    env = os.environ.get("SMARTLAB_REPO") or _user_config().get("repo")
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / "docker-compose.yml").is_file() and (d / "backend" / "app").is_dir():
            return d
    return None


@dataclass
class Config:
    api: str = "http://localhost:8000/api"
    repo: Optional[Path] = None
    timeout: float = 8.0
    stale_after_s: int = 300
    services: dict = field(default_factory=lambda: dict(DEFAULT_SERVICES))
    serial_log: Optional[Path] = None
    kb_url: str = "http://127.0.0.1:5199"
    ollama_url: str = "http://127.0.0.1:11434"
    camera_ports: tuple = (5100, 5101)

    @classmethod
    def load(cls) -> "Config":
        u = _user_config()
        c = cls()
        c.api = (os.environ.get("SMARTLAB_API") or u.get("api") or c.api).rstrip("/")
        c.repo = find_repo()
        c.timeout = float(os.environ.get("SMARTLAB_TIMEOUT") or u.get("timeout") or c.timeout)
        c.stale_after_s = int(os.environ.get("SMARTLAB_STALE_AFTER_S") or u.get("stale_after_s") or c.stale_after_s)
        log = os.environ.get("SMARTLAB_SERIAL_LOG") or u.get("serial_log")
        c.serial_log = Path(log) if log else None
        c.kb_url = (os.environ.get("SMARTLAB_KB_URL") or u.get("kb_url") or c.kb_url).rstrip("/")
        c.ollama_url = (os.environ.get("SMARTLAB_OLLAMA_URL") or u.get("ollama_url") or c.ollama_url).rstrip("/")
        return c

    # --- secrets: read where the Smart Lab keeps them, never returned to output -----------------------
    def kb_key(self) -> str:
        if os.environ.get("SMARTLAB_KB_KEY"):
            return os.environ["SMARTLAB_KB_KEY"]
        if not self.repo:
            return ""
        try:
            return json.loads((self.repo / "tools/knowledge/config.json").read_text(encoding="utf-8")).get("service_key", "")
        except (OSError, ValueError):
            return ""

    def device_key(self) -> str:
        if os.environ.get("SMARTLAB_DEVICE_KEY"):
            return os.environ["SMARTLAB_DEVICE_KEY"]
        if not self.repo:
            return ""
        try:
            for line in (self.repo / ".env").read_text(encoding="utf-8").splitlines():
                if line.startswith("DEVICE_API_KEY="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            pass
        return ""

    def knowledge_config(self) -> dict:
        """tools/knowledge/config.json without any key, password or literal to redact."""
        if not self.repo:
            return {}
        try:
            raw = json.loads((self.repo / "tools/knowledge/config.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in raw.items()
                if not any(s in k.lower() for s in ("key", "secret", "token", "password", "redact"))}
