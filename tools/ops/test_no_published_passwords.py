"""No published seed/demo password may live in tracked source, CI or scripts (audit S1, closed 2026-11-16).

Run: py -m pytest -q tools/ops/test_no_published_passwords.py
Allowed: isolated backend test fixtures (their own throw-away DB), the detector list in briefing.py that warns when a
live account still uses a published default, docs/ (history), and this file.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = re.compile(r"\b(Student|Staff|Admin|Demo|Lab)#20\d\d\b")
FALLBACK = re.compile(r"""E2E_PASSWORD\s*(\|\||\?\?)\s*['"]""")
ALLOW_PREFIX = ("backend/tests/", "docs/", "tools/ops/test_no_published_passwords.py")
ALLOW_FILES = {"backend/app/services/briefing.py"}   # PUBLISHED_DEFAULTS: the detector, not a credential in use


def _tracked():
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    for rel in out:
        if rel.endswith((".png", ".jpg", ".pdf", ".onnx", ".lock", ".glb", ".dae", ".stl", ".woff2")):
            continue
        yield rel


def _scan(rx, allow=True):
    hits = []
    for rel in _tracked():
        if allow and (rel.startswith(ALLOW_PREFIX) or rel in ALLOW_FILES):
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{rel}:{n}")
    return hits


def test_no_published_demo_password_in_source_ci_or_scripts():
    assert _scan(PUBLISHED) == []


def test_no_e2e_script_falls_back_to_a_literal_password():
    assert _scan(FALLBACK, allow=False) == []


def test_ci_generates_its_seed_passwords():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "openssl rand" in ci and "add-mask" in ci
    assert not re.search(r"SEED_\w+_PASSWORD:\s*\S", ci)


def test_fast_backend_test_script_uses_a_random_database_password():
    ps = (ROOT / "tools/ops/test_backend_fast.ps1").read_text(encoding="utf-8")
    assert "RandomNumberGenerator" in ps and "$dbPass" in ps
    assert not re.search(r"POSTGRES_PASSWORD=(?!\$)\S+", ps), "a fixed POSTGRES_PASSWORD is back"
    assert not re.search(r"smartlab:(?!\$\{?dbPass)[^@\s]+@smartlab-testdb", ps), "a fixed test-DB URL password is back"
