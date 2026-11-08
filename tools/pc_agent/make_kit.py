"""
Build the final flash-drive kit (lab_usb_kit/), reproducibly, on the admin's laptop (2026-11-04):

    py tools/pc_agent/make_kit.py            builds + signs the agent bundle, writes enroll.key and MANIFEST.json, checks for secrets
    py tools/pc_agent/make_kit.py --stick E: also mirrors the kit to E:\\lab_usb_kit and verifies every file there

It refuses to finish if the door boards' key, the backend's secret or the signing key is found in ANY file of the kit.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
KIT = os.path.join(REPO, "lab_usb_kit")
sys.path.insert(0, HERE)
import make_bundle  # noqa: E402

VERSION = "1.1"
# Old content of the kit: kept, but off the stick (backups/kit_old_<date>/), so nobody runs the wrong thing.
OBSOLETE = ["INSTALL_SMARTLAB.ps1", "CHECK_INSTALLATION.ps1", "UNINSTALL_SMARTLAB.ps1", "device.key", "old_bat_files", "README.txt", "SMART_LAB_PC_DEPLOYMENT_GUIDE.md",
            os.path.join("pc_agent", "start_pc_agent.bat"), os.path.join("pc_agent", "agent.env.example"),
            os.path.join("pc_agent", "wheels"),
            os.path.join("python", "Lib", "site-packages", "numpy.libs")]


def env_value(name: str) -> str:
    with open(os.path.join(REPO, ".env"), encoding="utf-8") as f:
        for line in f:
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def enroll_code(device_api_key: str) -> str:
    """Must match app.api.deps.pc_enroll_code()."""
    return hmac.new(device_api_key.encode(), b"smartlab-pc-enroll-v1", hashlib.sha256).hexdigest()


def tidy() -> None:
    stamp = time.strftime("%Y%m%d")
    for rel in OBSOLETE:
        src = os.path.join(KIT, rel)
        if not os.path.exists(src):
            continue
        if rel == "device.key":                 # the shared key is in .env; a second copy must not survive anywhere
            os.remove(src)
            print("removed lab_usb_kit/device.key (the shared door-board key)")
            continue
        dst = os.path.join(REPO, "backups", f"kit_old_{stamp}", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            shutil.rmtree(dst, ignore_errors=True) if os.path.isdir(dst) else os.remove(dst)
        shutil.move(src, dst)
        print(f"moved out of the kit: {rel}")
    for root, dirs, _files in os.walk(os.path.join(KIT, "pc_agent")):
        for d in list(dirs):
            if d == "__pycache__" or d.startswith("update_"):
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                dirs.remove(d)


def all_files(top: str):
    for root, dirs, files in os.walk(top):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if not name.endswith(".pyc"):
                yield os.path.join(root, name)


def secret_scan(top: str, secrets: dict) -> list[str]:
    """Plain bytes, UTF-16 too (a .bat or a registry export could hold either)."""
    needles = {}
    for label, value in secrets.items():
        if value:
            needles[label] = value.encode()
            needles[label + " (utf-16)"] = value.encode("utf-16-le")
    hits = []
    for path in all_files(top):
        with open(path, "rb") as f:
            data = f.read()
        hits += [f"{os.path.relpath(path, top)}: {label}" for label, n in needles.items() if n in data]
    return hits


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(state: dict) -> dict:
    files = {}
    for path in all_files(KIT):
        rel = os.path.relpath(path, KIT).replace(os.sep, "/")
        if rel != "MANIFEST.json":
            files[rel] = sha256(path)
    m = {"version": VERSION, "bundle_seq": state.get("seq"), "bundle_id": state.get("id"),
         "built": time.strftime("%Y-%m-%d %H:%M"), "files": dict(sorted(files.items()))}
    with open(os.path.join(KIT, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=0)
    return m


def to_stick(stick: str, manifest: dict) -> None:
    target = os.path.join(stick.rstrip("\\/") + os.sep, "lab_usb_kit")
    rc = subprocess.run(["robocopy", KIT, target, "/MIR", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP"],
                        capture_output=True).returncode
    if rc >= 8:
        raise SystemExit(f"copy to the stick failed (robocopy {rc})")
    bad = [rel for rel, want in manifest["files"].items()
           if not os.path.isfile(os.path.join(target, rel)) or sha256(os.path.join(target, rel)) != want]
    if bad or os.path.exists(os.path.join(target, "device.key")):
        raise SystemExit(f"the stick does not match the kit: {bad[:5]}")
    print(f"stick {stick}: {len(manifest['files'])} files verified, no device.key")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stick", help="also mirror to <drive>\\lab_usb_kit and verify, e.g. E:")
    ap.add_argument("--no-bundle", action="store_true", help="keep the current signed bundle")
    args = ap.parse_args()
    device_key, secret_key = env_value("DEVICE_API_KEY"), env_value("SECRET_KEY")
    if not device_key:
        raise SystemExit(".env has no DEVICE_API_KEY")
    tidy()
    if not args.no_bundle:
        make_bundle.main()
    shutil.copy2(os.path.join(REPO, "tools", "relay", "relay.py"), os.path.join(KIT, "relay", "relay.py"))
    with open(os.path.join(KIT, "enroll.key"), "w", encoding="utf-8") as f:
        f.write(enroll_code(device_key))
    signing = make_bundle.load_key()
    hits = secret_scan(KIT, {"DEVICE_API_KEY": device_key, "SECRET_KEY": secret_key, "signing key": signing["d"],
                             "DB password": env_value("POSTGRES_PASSWORD"), "n8n key": env_value("N8N_ENCRYPTION_KEY")})
    if hits:
        raise SystemExit("SECRET FOUND IN THE KIT, stopping:\n  " + "\n  ".join(hits))
    forbidden = [p for p in all_files(KIT) if os.path.basename(p).lower() in (".env", "camera.env", "robot.env", "device.key", "agent_sign_key.json")]
    if forbidden:
        raise SystemExit(f"file that must not be in the kit: {forbidden}")
    import agent_update
    m = write_manifest(agent_update.read_state(os.path.join(KIT, "pc_agent")))
    size = sum(os.path.getsize(p) for p in all_files(KIT))
    print(f"kit {m['version']} bundle {m['bundle_id']}: {len(m['files'])} files, {size // 1_000_000} MB, secret scan clean")
    if args.stick:
        to_stick(args.stick, m)


if __name__ == "__main__":
    main()
