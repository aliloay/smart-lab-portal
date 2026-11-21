"""`smartlab doctor`: every check returns PASS / WARN / FAIL / SKIP with the evidence. Read-only."""
from __future__ import annotations

from typing import Any, Callable

from ..utils.api_client import Client
from ..utils.errors import AuthRequired, SmartlabError
from . import ai, devices, repo, services

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"


def _check(name: str, fn: Callable[[], tuple[str, str]]) -> dict:
    try:
        st, detail = fn()
    except AuthRequired as e:
        st, detail = SKIP, f"{e.message} ({e.hint})" if e.hint else e.message
    except SmartlabError as e:
        st, detail = FAIL, e.message
    except Exception as e:  # noqa: BLE001 - a doctor must never crash on one check
        st, detail = FAIL, f"{type(e).__name__}: {e}"
    return {"check": name, "result": st, "detail": detail}


def run(c: Client) -> dict:
    checks: list[dict] = []

    def portal():
        d, ms = c.portal("/health", auth=False)
        v = (d or {}).get("version") or {}
        stamp = v.get("commit") or v.get("id") if isinstance(v, dict) else v
        return (PASS if (d or {}).get("status") in ("ok", "healthy", None) and d else FAIL,
                f"portal answers in {ms} ms; build {stamp or 'unknown'}")
    checks.append(_check("portal API", portal))

    def docker():
        r = services.docker_containers()
        if r["status"] in ("NOT_CONFIGURED", "NOT_ACCESSIBLE"):
            return WARN, f"docker not readable ({r.get('detail', r['status'])})"
        bad = [x["name"] for x in r["containers"] if x["health"] not in ("healthy", "running")]
        return (FAIL if bad else PASS), (f"not healthy: {', '.join(bad)}" if bad else
                                         f"{len(r['containers'])} containers healthy")
    checks.append(_check("docker containers", docker))

    svc = services.services(c)
    for s in svc:
        checks.append({"check": f"service {s['service']}", "result": PASS if s["status"] == "ONLINE" else FAIL,
                       "detail": f"{s['what']}: {s['status']}" + (f" ({s['ms']} ms)" if s.get("ms") else "")})

    def cams():
        rows = services.camera_metrics(c)
        pics = [r for r in rows if r.get("picture") == "ONLINE"]
        if not any(r.get("service") == "ONLINE" for r in rows):
            return FAIL, "camera services not running"
        return (PASS if len(pics) == len(rows) else WARN,
                f"{len(pics)}/{len(rows)} cameras receive a picture"
                + ("" if pics else " (IP cameras unreachable - expected away from the lab)"))
    checks.append(_check("camera pictures", cams))

    def auth():
        if not c.token():
            raise AuthRequired("no portal sign-in", "smartlab auth login")
        me, _ = c.portal("/auth/me")
        return PASS, f"signed in as role {me.get('role')}"
    checks.append(_check("portal sign-in", auth))

    def devs():
        rows, _ = devices.all_devices(c)
        esp = devices.filtered(rows, devices.ESP32_TYPES)
        off = [r["uid"] for r in esp if r["status"] != "ONLINE"]
        return (WARN if off else PASS), (f"ESP32 not online: {', '.join(off)}" if off else
                                         f"all {len(esp)} ESP32 boards online")
    checks.append(_check("ESP32 boards", devs))

    def models():
        m = ai.ollama_models(c)
        have = {r["model"] for r in m["rows"]}
        want = {c.cfg.knowledge_config().get("agent_model") or c.cfg.knowledge_config().get("model")} - {None}
        miss = want - have
        return (FAIL if miss else PASS), (f"configured but not installed: {', '.join(miss)}" if miss
                                          else f"{len(have)} models installed: {', '.join(sorted(have))}")
    checks.append(_check("local AI models", models))

    def gate():
        g, _ = c.kb("/gpu-gate")
        return PASS, f"assistants on {g.get('device')}: {g.get('reason')}"
    checks.append(_check("GPU gate (cameras first)", gate))

    def disks():
        res = services.resources(c)
        low = [d["disk"] for d in res.get("disks", []) if d["used_pct"] >= 90]
        return (WARN if low else PASS), (f"low space on {', '.join(low)}" if low else
                                         ", ".join(f"{d['disk']} {d['free_gb']} GB free" for d in res.get("disks", [])))
    checks.append(_check("disk space", disks))

    def gitc():
        g = repo.git_status(c.cfg.repo)
        a = g.get("ahead_of_origin_main")
        return (WARN if a else PASS), f"{g['branch']}: {a} commit(s) not on origin/main" if a is not None else g["branch"]
    checks.append(_check("git vs GitHub", gitc))

    counts: dict[str, Any] = {k: sum(1 for x in checks if x["result"] == k) for k in (PASS, WARN, FAIL, SKIP)}
    overall = FAIL if counts[FAIL] else WARN if counts[WARN] else PASS
    return {"overall": overall, "counts": counts, "rows": checks, "columns": ["check", "result", "detail"]}
