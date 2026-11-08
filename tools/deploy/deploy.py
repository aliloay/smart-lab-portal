"""
Safe portal deployment (2026-10-18) - the steps the portal was deployed with by hand, as one command.

    py -I tools/deploy/deploy.py [--skip-tests] [--full-tests] [--allow-migration]

  1. pre-checks: TypeScript check; a quick backend test set (or the full suite with --full-tests)
  2. schema: the database must be at the code's migration head. Behind head -> refused, unless
     --allow-migration: then a dump + an isolated restore-and-migrate drill (tools/evidence/restore_drill.py
     --migrate-test) must pass before `alembic upgrade head` runs on production (additive migrations only)
  3. rollback point: the running backend/frontend images are tagged :previous
  4. version stamp: git commit + dirty flag + time -> backend/app/build_info.json (git-ignored), served by
     /api/health as "version"
  5. build + `up -d --no-deps backend frontend` (nothing else is restarted: cameras, robots, n8n, db untouched)
  6. readiness: /api/health 200 with the new version within 120 s
  7. smoke tests (read-only, credentials from SMARTLAB_EMAIL / SMARTLAB_PASSWORD): sign-in, summary,
     services, briefing, robots, incidents, the web app's index page
  8. on a failed readiness or smoke test: ROLLBACK to the :previous images and verify health again
     (the database is never rolled back - migrations are additive and backward compatible)
  9. every deploy is appended to backups/deploy_history.jsonl (read by the incident investigator)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API = "http://127.0.0.1/api"
QUICK_TESTS = ["tests/test_authz_sweep.py", "tests/test_reliability.py", "tests/test_alert_grouping.py",
               "tests/test_robot_control.py", "tests/test_incidents.py"]


def run(cmd, cwd=REPO, timeout=1800, shell=False):
    t = time.perf_counter()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, shell=shell)
    return r.returncode, (r.stdout + r.stderr)[-2000:], round(time.perf_counter() - t, 1)


def get(path, token=None, timeout=15):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except (OSError, ValueError):
        return 0, None


def login():
    email, pw = os.environ.get("SMARTLAB_EMAIL", "admin@giu-uni.de"), os.environ.get("SMARTLAB_PASSWORD", "")
    req = urllib.request.Request(API + "/auth/login", data=json.dumps({"email": email, "password": pw}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())["access_token"]
    except Exception:
        return None


def wait_ready(version, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        c, h = get("/health", timeout=3)
        if c == 200 and (version is None or (h or {}).get("version", {}).get("id") == version):
            return True
        time.sleep(1)
    return False


def smoke():
    tok = login()
    results = {"sign_in": tok is not None}
    for name, path in (("summary", "/summary"), ("services", "/system/services"), ("briefing", "/reliability/briefing"),
                       ("robots", "/robots"), ("incidents", "/incidents?state=ACTIVE")):
        c, _ = get(path, tok)
        results[name] = c == 200
    try:
        # The web app is served over HTTPS since 2026-10-19 (http:// redirects there); checked with the
        # lab's own CA, never with verification switched off.
        import ssl
        ca = os.path.join(REPO, "deploy", "tls", "smartlab-ca.crt")
        url = "https://127.0.0.1/" if os.path.isfile(ca) else "http://127.0.0.1/"
        ctx = ssl.create_default_context(cafile=ca) if os.path.isfile(ca) else None
        with urllib.request.urlopen(url, timeout=10, context=ctx) as r:
            results["web_app"] = r.status == 200 and b'id="root"' in r.read()
    except OSError:
        results["web_app"] = False
    return results


def main():
    rec = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "steps": {}}
    if "--skip-tests" not in sys.argv:
        c, out, s = run("npx tsc --noEmit -p .", cwd=os.path.join(REPO, "frontend"), shell=True)
        rec["steps"]["typescript"] = {"ok": c == 0, "s": s}
        tests = [] if "--full-tests" in sys.argv else QUICK_TESTS
        c, out, s = run(["docker", "compose", "run", "--rm", "--no-deps", "-T", "-v", f"{REPO}\\backend:/app", "backend",
                         "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests], timeout=3600)
        rec["steps"]["backend_tests"] = {"ok": c == 0, "s": s, "tail": out.strip().splitlines()[-1:] if out else []}
        if not all(v["ok"] for v in rec["steps"].values()):
            return finish(rec, "REFUSED: pre-checks failed")
    # schema
    c, out, _ = run(["docker", "compose", "run", "--rm", "--no-deps", "-T", "-v", f"{REPO}\\backend:/app", "backend",
                     "sh", "-c", "alembic heads | cut -d' ' -f1; alembic current 2>/dev/null | cut -d' ' -f1"])
    lines = [x for x in out.split() if len(x) == 12 and all(ch in "0123456789abcdef" for ch in x)]
    behind = len(lines) >= 2 and lines[0] != lines[1]
    rec["steps"]["schema"] = {"head": lines[0] if lines else None, "db": lines[1] if len(lines) > 1 else None, "behind": behind}
    if behind:
        if "--allow-migration" not in sys.argv:
            return finish(rec, "REFUSED: database behind the code's migration head (use --allow-migration)")
        c, out, s = run(["py", "-I", os.path.join(REPO, "tools", "evidence", "restore_drill.py"), "--migrate-test"], timeout=1800)
        rec["steps"]["migration_drill"] = {"ok": c == 0 and '"exit": 0' in out, "s": s}
        if not rec["steps"]["migration_drill"]["ok"]:
            return finish(rec, "REFUSED: migration drill failed on the isolated copy")
        c, out, s = run(["docker", "compose", "run", "--rm", "--no-deps", "-T", "-v", f"{REPO}\\backend:/app", "backend",
                         "alembic", "upgrade", "head"])
        rec["steps"]["migration"] = {"ok": c == 0, "s": s}
        if c != 0:
            return finish(rec, "FAILED: migration on production failed - nothing deployed")
    # rollback point
    for svc in ("backend", "frontend"):
        run(["docker", "tag", f"smart-lab-portal-{svc}:latest", f"smart-lab-portal-{svc}:previous"])
    # version stamp
    _, sha, _ = run(["git", "rev-parse", "--short", "HEAD"])
    _, dirty, _ = run(["git", "status", "--porcelain"])
    version = f"{sha.strip()}{'-dirty' if dirty.strip() else ''}-{time.strftime('%Y%m%d%H%M%S')}"
    with open(os.path.join(REPO, "backend", "app", "build_info.json"), "w", encoding="utf-8") as f:
        json.dump({"id": version, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, f)
    rec["version"] = version
    c, out, s = run(["docker", "compose", "build", "backend", "frontend"], timeout=1800)
    rec["steps"]["build"] = {"ok": c == 0, "s": s}
    if c != 0:
        return finish(rec, "FAILED: build failed - the running version was not touched")
    c, out, s = run(["docker", "compose", "up", "-d", "--no-deps", "backend", "frontend"])
    rec["steps"]["up"] = {"ok": c == 0, "s": s}
    ready = wait_ready(version)
    rec["steps"]["ready"] = {"ok": ready}
    sm = smoke() if ready else {}
    rec["steps"]["smoke"] = {"ok": bool(sm) and all(sm.values()), "checks": sm}
    if ready and all(sm.values()):
        return finish(rec, "DEPLOYED")
    # rollback
    for svc in ("backend", "frontend"):
        run(["docker", "tag", f"smart-lab-portal-{svc}:previous", f"smart-lab-portal-{svc}:latest"])
    run(["docker", "compose", "up", "-d", "--no-deps", "--no-build", "backend", "frontend"])
    rec["steps"]["rollback"] = {"ok": wait_ready(None), "health_after": get("/health")[0]}
    return finish(rec, "ROLLED BACK: readiness or smoke test failed")


def finish(rec, outcome):
    rec["outcome"] = outcome
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(os.path.join(REPO, "backups", "deploy_history.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec, indent=1))
    return 0 if outcome == "DEPLOYED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
