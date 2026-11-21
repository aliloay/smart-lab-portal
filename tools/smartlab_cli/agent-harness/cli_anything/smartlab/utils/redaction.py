"""Redaction: nothing secret leaves the CLI, even inside log lines or error messages."""
from __future__ import annotations

import re
from typing import Any

# Whole key names only (e.g. "password", "access_token", "service_key"), so "PASS" counts or "prompt_tokens" survive.
SECRET_KEYS = re.compile(r"(?i)((^|[_\-])(password|passwd|passphrase|secret|token|api[_-]?key|service[_-]?key|"
                         r"device[_-]?key|kb[_-]?key|automation[_-]?key|authorization|cookie|credentials?|jwt)$"
                         r"|^x-(kb|device|automation)-key$|^rtsp)")
_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-_.=]+"), r"\1[REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), "[REDACTED-JWT]"),
    (re.compile(r"(?i)\b((?:pass(?:word)?|secret|token|api[_-]?key|service_key|device[_-]?key|key)\s*[=:]\s*)"
                r"(\"[^\"]*\"|'[^']*'|\S+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)rtsp://[^\s\"']+"), "rtsp://[REDACTED]"),
    (re.compile(r"(?i)(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1[REDACTED]@"),
    (re.compile(r"\bSLB:~?[A-Za-z0-9_\-]{8,}"), "SLB:[REDACTED]"),   # door QR tokens
]


def redact_text(s: str, extra: tuple[str, ...] = ()) -> str:
    if not isinstance(s, str):
        return s
    for pat, rep in _PATTERNS:
        s = pat.sub(rep, s)
    for lit in extra:
        if lit and len(lit) >= 6:
            s = s.replace(lit, "[REDACTED]")
    return s


def redact(obj: Any, extra: tuple[str, ...] = ()) -> Any:
    """Deep copy of obj with secret-looking keys blanked and secret-looking text masked."""
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if isinstance(k, str) and SECRET_KEYS.search(k) and obj[k] not in (None, "", False)
                    else redact(v, extra)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(v, extra) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj, extra)
    return obj
