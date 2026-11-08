"""
Signed self-update of the lab PC agent (2026-11-04, owner: "make it the final run for the flash drive").

The portal serves one bundle (backend/data/pc_agent_bundle/bundle.json, built by make_bundle.py on the admin's
laptop). An agent takes it only if the RSA-2048 signature matches the public key below: the private key never
leaves the laptop, so nobody on the GIU network and no device key can push code to the lab PCs. Standard library
only: the check is one modular exponentiation and a comparison of the WHOLE padded block (no parsing, so the
classic forged-padding attacks do not apply).

A sequence number only ever goes up, so an old signed bundle cannot be replayed. Before a file is replaced its
current version goes to update_prev/. A bundle whose agent crashes before its first good report with the portal is
rolled back by agent_boot.py and never taken again.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
from typing import Optional

PUBLIC_E = 65537
PUBLIC_N_HEX = "c9f3c0b4eb99511050d8db7f2f027946bb2483fe5ad87836c4ee69a48a507ab35bd9b8a2d366a4ed65b2ded291636f88db9dcd006b534ed7d052cb6d816f6adca70dee0ba0dd9ee546fceb897fe3037d0a6500e390afb34374fe17a5c871b0fccf0ccf30e4e1baf98fd412e3df9843bb96c28fd44e3b9f3eab1efb01f94d0d3d3cd92b9dcb0fa72c5b9d6b822968c7a3b690622a09342b8b3e9fd463fc26ba3a450dbc1212e760eec3dab538e10e289048074b11114072708a496f75ee2a868f5f41f8d0622e47bf97f7b6988549a590df191631df07db9bd83108e9c0b6f36bbf62e295703c3a9a4f5188a773145d8fcedfe6ff5914b11632c6b7d0aae61bb7"
EXIT_UPDATED = 75                                 # the agent's exit code: "new files in place, start me again"
STATE_FILE = "update_state.json"
PREV_DIR, NEW_DIR = "update_prev", "update_new"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_]+\.(py|json)$")
_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")   # DER DigestInfo of SHA-256


class BundleRefused(Exception):
    pass


def canonical(manifest: dict) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()


def padded(digest: bytes, size: int) -> bytes:
    """EMSA-PKCS1-v1_5 for SHA-256 (RFC 8017, section 9.2)."""
    t = _SHA256_PREFIX + digest
    return b"\x00\x01" + b"\xff" * (size - len(t) - 3) + b"\x00" + t


def verify(data: bytes, sig_hex: str, n: Optional[int] = None) -> bool:
    n = n or int(PUBLIC_N_HEX, 16)
    size = (n.bit_length() + 7) // 8
    try:
        s = int(sig_hex, 16)
    except (TypeError, ValueError):
        return False
    if not 0 < s < n:
        return False
    return pow(s, PUBLIC_E, n).to_bytes(size, "big") == padded(hashlib.sha256(data).digest(), size)


def read_state(agent_dir: str) -> dict:
    try:
        with open(os.path.join(agent_dir, STATE_FILE), encoding="utf-8") as f:
            s = json.load(f)
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(agent_dir: str, state: dict) -> None:
    tmp = os.path.join(agent_dir, STATE_FILE + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, os.path.join(agent_dir, STATE_FILE))


def wanted(state: dict, seq) -> bool:
    """A newer bundle than this PC has, and not one that was already rolled back here."""
    return isinstance(seq, int) and seq > int(state.get("seq") or 0) and seq > int(state.get("bad_seq") or 0)


def apply_bundle(agent_dir: str, bundle: dict, n: Optional[int] = None) -> int:
    """Check everything first, then put the files in place. Returns the new sequence number."""
    manifest, sig, blobs = bundle.get("manifest"), bundle.get("sig"), bundle.get("files")
    if not isinstance(manifest, dict) or not isinstance(blobs, dict) or not verify(canonical(manifest), sig, n):
        raise BundleRefused("bad signature")
    state = read_state(agent_dir)
    seq = manifest.get("seq")
    if not wanted(state, seq):
        raise BundleRefused(f"bundle {seq} is not newer than {state.get('seq')} (bad {state.get('bad_seq')})")
    data: dict[str, bytes] = {}
    for item in manifest.get("files") or []:
        name = item.get("name", "")
        if not _SAFE_NAME.fullmatch(name):
            raise BundleRefused(f"unsafe file name {name!r}")
        raw = base64.b64decode(blobs[name])
        if hashlib.sha256(raw).hexdigest() != item.get("sha256"):
            raise BundleRefused(f"{name}: wrong content")
        data[name] = raw
    if not data:
        raise BundleRefused("empty bundle")
    new_dir, prev_dir = os.path.join(agent_dir, NEW_DIR), os.path.join(agent_dir, PREV_DIR)
    for d in (new_dir, prev_dir):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
    for name, raw in data.items():
        with open(os.path.join(new_dir, name), "wb") as f:
            f.write(raw)
    existed = []
    for name in data:
        cur = os.path.join(agent_dir, name)
        if os.path.isfile(cur):
            shutil.copy2(cur, os.path.join(prev_dir, name))
            existed.append(name)
    write_state(agent_dir, {**state, "seq": seq, "id": manifest.get("id"), "prev_seq": int(state.get("seq") or 0),
                            "prev_id": state.get("id"), "changed": list(data), "existed": existed,
                            "pending_health": True})
    try:
        for name in data:
            os.replace(os.path.join(new_dir, name), os.path.join(agent_dir, name))
    except OSError:
        rollback(agent_dir)
        raise
    shutil.rmtree(new_dir, ignore_errors=True)
    return seq


def rollback(agent_dir: str) -> bool:
    """Back to the files before the last update; that bundle is never taken again on this PC."""
    state = read_state(agent_dir)
    if not state.get("changed"):
        return False
    prev_dir = os.path.join(agent_dir, PREV_DIR)
    for name in state["changed"]:
        cur = os.path.join(agent_dir, name)
        if name in (state.get("existed") or []):
            shutil.copy2(os.path.join(prev_dir, name), cur)
        elif os.path.isfile(cur):
            os.remove(cur)
    write_state(agent_dir, {"seq": state.get("prev_seq") or 0, "id": state.get("prev_id"),
                            "bad_seq": max(int(state.get("seq") or 0), int(state.get("bad_seq") or 0))})
    return True


def mark_healthy(agent_dir: str) -> None:
    """The agent after an update has reported to the portal: the update stays."""
    state = read_state(agent_dir)
    if state.get("pending_health"):
        write_state(agent_dir, {**state, "pending_health": False})
