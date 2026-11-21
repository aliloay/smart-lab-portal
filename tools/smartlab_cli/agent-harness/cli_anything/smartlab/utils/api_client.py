"""The ONLY network layer of the CLI. Read-only by construction.

Every request is checked against an explicit allow-list BEFORE anything is sent:
  * Portal API: GET on a fixed set of read-only paths; the one POST is the sign-in (/auth/login).
  * Knowledge service: GET /health /status /gpu-gate; POST /ask only with route "lookup" (search, no AI generation).
  * Ollama: GET /api/version /api/tags /api/ps (never pull, delete, generate).
  * Local service health probes: GET on the configured /health URLs and the cameras' /metrics.
Anything else raises Forbidden. There is no generic "call any URL" function and no shell.
"""
from __future__ import annotations

import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

from .config import TOKEN_FILE, USER_DIR, Config
from .errors import AuthRequired, Forbidden, NotFound, SmartlabError, Unavailable

PORTAL_GET = [re.compile(p) for p in (
    r"/health", r"/auth/me", r"/system/status", r"/system/services", r"/system/health",
    r"/devices", r"/labs", r"/labs/health", r"/labs/overview", r"/alerts", r"/summary",
    r"/robots", r"/robots/[A-Za-z0-9_\-]{1,64}", r"/equipment", r"/security/cameras",
    r"/ai/status", r"/knowledge/status", r"/voice/status",
    r"/inventory/bins", r"/inventory/bins/\d{1,9}/items",
)]
PORTAL_POST = {"/auth/login"}
KB_GET = {"/health", "/status", "/gpu-gate"}
OLLAMA_GET = {"/api/version", "/api/tags", "/api/ps"}
CAMERA_GET = {"/health", "/metrics"}

_LOCAL = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def _allowed_portal(method: str, path: str) -> bool:
    if method == "GET":
        return any(p.fullmatch(path) for p in PORTAL_GET)
    return method == "POST" and path in PORTAL_POST


class Client:
    def __init__(self, cfg: Config, retries: int = 1):
        self.cfg = cfg
        self.retries = retries

    # --- token -----------------------------------------------------------------------------------------
    def token(self) -> Optional[str]:
        if os.environ.get("SMARTLAB_TOKEN"):
            return os.environ["SMARTLAB_TOKEN"]
        try:
            t = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if t.get("api") != self.cfg.api or float(t.get("expires_at", 0)) < time.time() + 30:
            return None
        return t.get("token")

    def save_token(self, token: str, ttl_s: int, who: dict) -> None:
        USER_DIR.mkdir(parents=True, exist_ok=True)
        data = json.dumps({"api": self.cfg.api, "token": token, "expires_at": time.time() + ttl_s, **who})
        fd = os.open(str(TOKEN_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)

    @staticmethod
    def forget_token() -> bool:
        try:
            TOKEN_FILE.unlink()
            return True
        except FileNotFoundError:
            return False

    # --- low level -----------------------------------------------------------------------------------
    def _send(self, method: str, url: str, headers: dict, body: Optional[bytes], timeout: float):
        host = urlparse(url).hostname or ""
        ctx = None
        if url.startswith("https://") and host in _LOCAL:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False          # the local portal uses a self-signed certificate
            ctx.verify_mode = ssl.CERT_NONE
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(url, data=body, method=method, headers=headers)
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                    raw = r.read()
                    return r.status, raw, round((time.perf_counter() - t0) * 1000, 1)
            except urllib.error.HTTPError as e:
                return e.code, e.read(), round((time.perf_counter() - t0) * 1000, 1)
            except (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError) as e:
                last = e
                if method != "GET" or attempt == self.retries:   # retry only idempotent reads
                    break
                time.sleep(0.4)
        reason = getattr(last, "reason", last)
        raise Unavailable(f"{urlparse(url).netloc} not reachable ({reason})",
                          "Is the service running? Start launch.bat (Explorer) / docker compose.")

    @staticmethod
    def _json(raw: bytes) -> Any:
        try:
            return json.loads(raw.decode("utf-8") or "null")
        except (ValueError, UnicodeDecodeError):
            return {"_text": raw[:300].decode("utf-8", "replace")}

    # --- portal --------------------------------------------------------------------------------------
    def portal(self, path: str, params: Optional[dict] = None, auth: bool = True) -> tuple[Any, float]:
        if not _allowed_portal("GET", path):
            raise Forbidden(f"GET {path} is not on the read-only allow-list")
        headers = {"Accept": "application/json"}
        if auth:
            tok = self.token()
            if not tok:
                raise AuthRequired("This needs a portal sign-in (staff or admin).",
                                   "Run: smartlab auth login   (or set SMARTLAB_TOKEN)")
            headers["Authorization"] = f"Bearer {tok}"
        url = self.cfg.api + path + (("?" + urlencode(params)) if params else "")
        status, raw, ms = self._send("GET", url, headers, None, self.cfg.timeout)
        data = self._json(raw)
        if status == 401:
            raise AuthRequired("The portal refused the sign-in (expired or missing token).", "Run: smartlab auth login")
        if status == 403:
            raise AuthRequired("This account may not read that (staff or admin role needed).")
        if status == 404:
            raise NotFound(f"{path} not found")
        if status >= 400:
            raise SmartlabError(f"Portal answered HTTP {status} for {path}")
        return data, ms

    def login(self, username: str, password: str) -> dict:
        if not _allowed_portal("POST", "/auth/login"):
            raise Forbidden("login not allowed")
        body = json.dumps({"email": username, "password": password}).encode()
        status, raw, _ = self._send("POST", self.cfg.api + "/auth/login",
                                    {"Content-Type": "application/json"}, body, self.cfg.timeout)
        data = self._json(raw)
        if status == 429:
            raise SmartlabError("Too many sign-in attempts - wait a minute.")
        if status >= 400 or not isinstance(data, dict) or "access_token" not in data:
            raise AuthRequired("Sign-in refused (wrong username or password).")
        return data

    # --- knowledge service ---------------------------------------------------------------------------
    def kb(self, path: str) -> tuple[Any, float]:
        if path not in KB_GET:
            raise Forbidden(f"knowledge GET {path} is not on the allow-list")
        key = self.cfg.kb_key()
        headers = {"X-KB-Key": key} if key else {}
        status, raw, ms = self._send("GET", self.cfg.kb_url + path, headers, None, self.cfg.timeout)
        if status == 401:
            raise AuthRequired("Knowledge service key missing or wrong.",
                               "Set SMARTLAB_REPO to the Smart Lab repo (key in tools/knowledge/config.json).")
        if status >= 400:
            raise SmartlabError(f"Knowledge service answered HTTP {status}")
        return self._json(raw), ms

    def kb_search(self, question: str) -> tuple[list[dict], float]:
        """Document search only: route 'lookup' never runs the AI model."""
        q = question.strip()[:600]
        body = json.dumps({"question": q, "route": "lookup"}).encode()
        key = self.cfg.kb_key()
        if not key:
            raise AuthRequired("Knowledge service key not found.", "Set SMARTLAB_REPO or SMARTLAB_KB_KEY.")
        status, raw, ms = self._send("POST", self.cfg.kb_url + "/ask",
                                     {"X-KB-Key": key, "Content-Type": "application/json"}, body, max(self.cfg.timeout, 30))
        if status >= 400:
            raise SmartlabError(f"Knowledge search answered HTTP {status}")
        events = []
        for line in raw.decode("utf-8", "replace").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
        return events, ms

    # --- ollama --------------------------------------------------------------------------------------
    def ollama(self, path: str) -> tuple[Any, float]:
        if path not in OLLAMA_GET:
            raise Forbidden(f"Ollama {path} is not on the read-only allow-list")
        status, raw, ms = self._send("GET", self.cfg.ollama_url + path, {}, None, self.cfg.timeout)
        if status >= 400:
            raise SmartlabError(f"Ollama answered HTTP {status}")
        return self._json(raw), ms

    # --- local services --------------------------------------------------------------------------------
    def probe(self, url: str, timeout: float = 3.0) -> dict:
        """GET a configured local health URL. Never raises: returns state + latency."""
        if url not in {u for u, _ in self.cfg.services.values()}:
            raise Forbidden(f"{url} is not a configured health URL")
        try:
            status, raw, ms = self._send("GET", url, {}, None, timeout)
        except Unavailable as e:
            return {"state": "DOWN", "http": None, "ms": None, "detail": e.message}
        return {"state": "UP" if status < 400 else "ERROR", "http": status, "ms": ms,
                "body": self._json(raw) if status < 400 else None}

    def camera(self, port: int, path: str) -> tuple[int, Any, float]:
        if port not in self.cfg.camera_ports or path not in CAMERA_GET:
            raise Forbidden(f"camera {port}{path} is not on the allow-list")
        headers = {"X-Device-Key": self.cfg.device_key()} if path == "/metrics" else {}
        status, raw, ms = self._send("GET", f"http://127.0.0.1:{port}{path}", headers, None, 3.0)
        return status, self._json(raw), ms
