"""Seed accounts never get a fixed, published password (2026-10-18 finding S1, closed 2026-11-16).

seed.py prints and touches the database when imported, so these tests read its source instead.
"""
import re
from pathlib import Path

SEED = (Path(__file__).resolve().parents[1] / "seed.py").read_text(encoding="utf-8")


def test_every_seeded_hash_comes_from_initial_password():
    calls = re.findall(r"hash_password\(([^)]*\)?)\)", SEED)
    assert calls, "seed.py no longer hashes any password?"
    for arg in calls:
        assert arg.strip().startswith("initial_password("), f"seed.py hashes something else: {arg!r}"


def test_initial_password_is_env_or_random_never_a_literal():
    body = re.search(r"def initial_password\(kind: str\) -> str:\n(.*?)\n\n", SEED, re.S)
    assert body, "initial_password() not found"
    src = body.group(1)
    assert "secrets.token_urlsafe" in src and "os.environ.get" in src
    # the only string literals allowed are the env-variable template and the empty default
    literals = [x for x in re.findall(r"""(["'])(.*?)\1""", src) if x[1] not in ("", "SEED_{kind}_PASSWORD")]
    assert not [x for x in literals if "PASSWORD" not in x[1]], literals


def test_no_password_literal_assigned_in_seed():
    for m in re.finditer(r"""(?i)\bpassword\w*\s*=\s*(["'])(.+?)\1""", SEED):
        raise AssertionError(f"seed.py assigns a literal password near: {m.group(0)[:12]}...")
