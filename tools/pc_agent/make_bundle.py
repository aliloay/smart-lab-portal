"""
Build + sign the PC agent update on the admin's laptop (2026-11-04):

    py tools/pc_agent/make_bundle.py           writes backend/data/pc_agent_bundle/bundle.json and the kit's agent files
    (then rebuild the backend: every lab PC updates itself within about a minute, no flash drive)

The private key lives ONLY at %USERPROFILE%\\.smartlab\\agent_sign_key.json - never in the repository, never on the
flash drive. It is created the first time, and its public half is written into agent_update.py. Lose it and the PCs
need one more flash-drive run with a new key. Standard library only.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import secrets
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
KEY_FILE = os.path.join(os.path.expanduser("~"), ".smartlab", "agent_sign_key.json")
BUNDLE = os.path.join(REPO, "backend", "data", "pc_agent_bundle", "bundle.json")
KIT = os.path.join(REPO, "lab_usb_kit", "pc_agent")
FILES = ["agent_boot.py", "agent_update.py", "exam_lockdown.py", "notice.py", "pc_agent.py", "status_tray.py"]
PLACEHOLDER = "@@PUBLIC_N_HEX@@"
E = 65537


def _probably_prime(n: int, rounds: int = 64) -> bool:
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        x = pow(secrets.randbelow(n - 3) + 2, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(bits: int) -> int:
    while True:
        c = secrets.randbits(bits) | (3 << (bits - 2)) | 1
        if math.gcd(c - 1, E) == 1 and _probably_prime(c):
            return c


def new_key() -> dict:
    p, q = _prime(1024), _prime(1024)
    while p == q:
        q = _prime(1024)
    n = p * q
    return {"n": format(n, "x"), "d": format(pow(E, -1, (p - 1) * (q - 1)), "x")}


def load_key() -> dict:
    if os.path.isfile(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as f:
            return json.load(f)
    key = new_key()
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        json.dump(key, f)
    print(f"new signing key: {KEY_FILE} (keep it; never copy it to the flash drive or the repository)")
    return key


def sign(data: bytes, key: dict) -> str:
    import agent_update
    n, d = int(key["n"], 16), int(key["d"], 16)
    size = (n.bit_length() + 7) // 8
    return format(pow(int.from_bytes(agent_update.padded(hashlib.sha256(data).digest(), size), "big"), d, n), "x")


def embed_public_key(key: dict) -> None:
    """Fill the placeholder once; a different key afterwards would lock the installed PCs out, so refuse it."""
    path = os.path.join(HERE, "agent_update.py")
    with open(path, encoding="utf-8", newline="") as f:
        src = f.read()
    if PLACEHOLDER in src:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(src.replace(PLACEHOLDER, key["n"]))
    elif f'"{key["n"]}"' not in src:
        raise SystemExit("agent_update.py holds another public key than the signing key - stopping")


def main() -> None:
    key = load_key()
    embed_public_key(key)
    import importlib

    import agent_update
    importlib.reload(agent_update)
    files, blobs = [], {}
    for name in FILES:
        with open(os.path.join(HERE, name), "rb") as f:
            raw = f.read()
        files.append({"name": name, "sha256": hashlib.sha256(raw).hexdigest()})
        blobs[name] = base64.b64encode(raw).decode()
    bundle_id = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12]
    manifest = {"seq": int(time.time()), "id": bundle_id, "files": files}
    sig = sign(agent_update.canonical(manifest), key)
    if not agent_update.verify(agent_update.canonical(manifest), sig):
        raise SystemExit("signature does not verify - stopping")
    os.makedirs(os.path.dirname(BUNDLE), exist_ok=True)
    with open(BUNDLE, "w", encoding="utf-8") as f:
        json.dump({"manifest": manifest, "sig": sig, "files": blobs}, f)
    # The flash-drive kit carries exactly the same files and starts at the same sequence number.
    if os.path.isdir(KIT):
        for name in FILES:
            shutil.copy2(os.path.join(HERE, name), os.path.join(KIT, name))
        agent_update.write_state(KIT, {"seq": manifest["seq"], "id": bundle_id})
    print(f"bundle {bundle_id} seq {manifest['seq']}: {len(files)} files, {os.path.getsize(BUNDLE)} bytes")


if __name__ == "__main__":
    main()
