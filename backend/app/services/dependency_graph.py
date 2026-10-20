"""
Dependency graph and live state model of the Smart Lab (2026-10-18) - a lightweight digital twin.

Nodes are DISCOVERED, not invented: the infrastructure the portal itself runs on, the network
services the health monitor checks, and every registered device (devices table). Edges say "A needs
B to do its job". Each node carries:

  state         HEALTHY / DEGRADED / STALE DATA / OFFLINE / SIMULATED / UNKNOWN / BLOCKED /
                PHYSICAL VALIDATION REQUIRED (from /system/services - a real check or heartbeat)
  evidence      live (checked or reported), inferred (implied by another observation) or simulated
  physical      what software cannot see and still needs a person (static, from the lab records)

Every edge comes from the code or configuration (who posts to whom, which process reads which
camera); an edge that is only a reasonable assumption is marked inferred=True.

impact(node) lists everything that needs that node (transitively). whatif(node) is a SANDBOXED
simulation of that node failing: the affected nodes, the alerts the portal would raise and the
recovery order (dependencies first). It reads the live state and changes nothing - no command, no
database write, nothing physical.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Optional

# Physical checks software cannot do (lab records: docs/LAB_GO_NOGO_2026-10-18.md, BRINGUP_LOG.md).
PHYSICAL = {
    "robot": "commissioning with the qualified operator (cable, E-stops, Home program, clearance, sign-off)",
    "security_camera": "mounting, floor calibration and the identity scenarios with people",
    "door": "lock / egress behaviour and power-loss state checked at the door",
    "environment": "sensor bench test (flame / smoke / PIR) and supply voltages",
    "bin": "load-cell accuracy with known masses, NFC and lid / servo behaviour",
    "pc": "agent install on IT-approved lab PCs",
    "entry_camera": "face capture at the door",
}
_STATE_MAP = {"ONLINE": "HEALTHY", "DEGRADED": "DEGRADED", "STALE": "STALE DATA", "OFFLINE": "OFFLINE",
              "UNKNOWN": "UNKNOWN", "SIMULATION": "SIMULATED"}
_BAD = {"OFFLINE", "STALE DATA", "DEGRADED", "UNKNOWN"}
_FAILING = {"OFFLINE", "STALE DATA", "DEGRADED"}      # UNKNOWN = not checked, not "failing"


def _node(key, name, kind, state="UNKNOWN", evidence="inferred", detail="", **kw) -> dict:
    return {"key": key, "name": name, "kind": kind, "state": state, "evidence": evidence, "detail": detail,
            "needs": [], **kw}


def build(services: list[dict], now: Optional[datetime] = None) -> dict:
    """services: the list from /system/services (health monitor cache + device heartbeats)."""
    now = now or datetime.now(timezone.utc)
    by_key = {s["key"]: s for s in services}
    nodes: dict[str, dict] = {}

    def add(n: dict):
        nodes[n["key"]] = n
        return n

    def from_service(key, name, kind, **kw):
        s = by_key.get(key)
        if s is None:
            return add(_node(key, name, kind, "UNKNOWN", "inferred", "not checked by this portal", **kw))
        return add(_node(key, s.get("name") or name, kind, _STATE_MAP.get(s["state"], s["state"]), "live",
                         s.get("detail") or "", last_ok=s.get("last_ok") or s.get("last_seen"),
                         failing_since=s.get("failing_since"), guidance=s.get("guidance"), **kw))

    # --- infrastructure the portal runs on (this request proves the backend; the rest by checks) ----
    add(_node("laptop", "Portal laptop (192.168.1.200)", "host", "HEALTHY", "inferred",
              "the backend answers, so the laptop and Docker are running"))
    add(_node("router", "Smart_Lab router (192.168.1.1)", "network", "UNKNOWN", "inferred",
              "not probed by the backend; inferred from the devices that report through it"))
    from_service("database", "PostgreSQL", "service")
    from_service("backend", "Backend API", "service")
    add(_node("frontend", "Portal web app (nginx)", "service", "HEALTHY", "inferred",
              "serves the pages that call this API"))
    from_service("websocket", "Live stream", "service")
    from_service("face", "Face server", "service")
    from_service("ai", "AI (local model, Ollama)", "service")
    from_service("knowledge", "Project knowledge service", "service")
    from_service("n8n", "Automation (n8n)", "service")
    from_service("entry_camera", "Door camera (ESP32-CAM)", "device", physical=PHYSICAL["entry_camera"])
    add(_node("backups", "Database backups (every 6 h)", "job", "UNKNOWN", "inferred", "see the backup status"))

    edges = [("frontend", "backend"), ("backend", "database"), ("backend", "laptop"), ("database", "laptop"),
             ("websocket", "backend"), ("face", "laptop"), ("ai", "laptop"), ("knowledge", "laptop"),
             ("knowledge", "ai"), ("n8n", "backend"), ("backups", "database"), ("entry_camera", "router")]
    inferred_edges = {("knowledge", "ai")}

    # --- devices (each from its own heartbeat) -------------------------------------------------
    for s in services:
        g = s.get("group")
        if not g:
            continue
        uid = s.get("device_uid") or s["key"]
        kind = "bin" if g == "environment" and "BIN" in uid.upper() else g
        n = from_service(s["key"], s.get("name") or uid, kind, device_uid=uid, device_id=s.get("device_id"),
                         physical=PHYSICAL.get(kind), open_alerts=s.get("open_alerts", 0))
        if n["state"] == "SIMULATED":
            n["evidence"] = "simulated"
        if g == "robot" and n["state"] not in ("SIMULATED",):
            n["control"] = "DRY RUN - motion BLOCKED until commissioning sign-off"
        # who this device needs
        if g in ("door", "environment"):                  # ESP32 over Wi-Fi -> POST to the backend
            edges += [(s["key"], "router"), (s["key"], "backend")]
            if g == "door":
                edges += [(s["key"], "face"), (s["key"], "entry_camera")]
                inferred_edges.add((s["key"], "entry_camera"))
        elif g == "security_camera":                      # camera -> native vision service -> backend
            svc = f"vision:{uid}"
            add(_node(svc, f"Vision service {uid}", "process",
                      "HEALTHY" if n["state"] in ("HEALTHY", "DEGRADED") else n["state"], "inferred",
                      "posts the camera state; its own /health is on the laptop"))
            cam = f"camhw:{uid}"
            add(_node(cam, f"Camera hardware {uid}", "device",
                      "OFFLINE" if n["state"] == "DEGRADED" else ("HEALTHY" if n["state"] == "HEALTHY" else n["state"]),
                      "inferred", "picture arrives" if n["state"] == "HEALTHY" else
                      "no picture reported by its vision service" if n["state"] == "DEGRADED" else "",
                      physical=PHYSICAL["security_camera"]))
            edges += [(s["key"], svc), (svc, cam), (cam, "router"), (svc, "backend"), (svc, "face")]
            inferred_edges.add((svc, "face"))
        elif g == "robot":                                # controller -> collector on the laptop -> backend
            col = f"collector:{uid}"
            add(_node(col, f"Robot collector {uid}", "process",
                      "HEALTHY" if n["state"] in ("HEALTHY", "DEGRADED") else n["state"], "inferred",
                      "reports to the portal"))
            ctl = f"controller:{uid}"
            add(_node(ctl, f"Robot controller {uid}", "device",
                      "OFFLINE" if n["state"] == "DEGRADED" else n["state"], "inferred",
                      "no joint data" if n["state"] == "DEGRADED" else "", physical=PHYSICAL["robot"]))
            edges += [(s["key"], col), (s["key"], ctl), (col, ctl), (ctl, "router"), (col, "backend")]
        elif g == "pc":
            edges += [(s["key"], "backend"), (s["key"], "router")]
            inferred_edges.add((s["key"], "router"))
        elif g == "entry_camera":
            edges += [(s["key"], "router")]

    for a, b in edges:
        if a in nodes and b in nodes and b not in [x["node"] for x in nodes[a]["needs"]]:
            nodes[a]["needs"].append({"node": b, "inferred": (a, b) in inferred_edges})

    # The router is not probed: if anything that reaches the backend through it reports now, it works.
    # (a camera's hardware node is HEALTHY only when its live report says frames arrive)
    through = [k for k, n in nodes.items() if any(x["node"] == "router" for x in n["needs"])
               and n["evidence"] in ("live", "inferred") and n["state"] == "HEALTHY"]
    if through:
        nodes["router"].update(state="HEALTHY", detail=f"{len(through)} device(s) report through it")
    for n in nodes.values():
        n["needed_by"] = sorted(k for k, m in nodes.items() if any(x["node"] == n["key"] for x in m["needs"]))
    return {"generated_at": now.isoformat(), "nodes": list(nodes.values()),
            "summary": {s: sum(1 for n in nodes.values() if n["state"] == s) for s in
                        ("HEALTHY", "DEGRADED", "STALE DATA", "OFFLINE", "SIMULATED", "UNKNOWN")}}


def impact(graph: dict, key: str) -> list[str]:
    """Every node that needs `key`, directly or through others."""
    by = {n["key"]: n for n in graph["nodes"]}
    seen, q = set(), deque([key])
    while q:
        k = q.popleft()
        for up in by.get(k, {}).get("needed_by", []):
            if up not in seen:
                seen.add(up)
                q.append(up)
    return sorted(seen)


def likely_roots(graph: dict) -> list[dict]:
    """Failing nodes whose own dependencies are fine: where a fault most likely starts. Correlation from
    the graph and the current states - a hint for diagnosis, never proof."""
    by = {n["key"]: n for n in graph["nodes"]}
    out = []
    for n in graph["nodes"]:
        if n["state"] not in _FAILING or n["evidence"] == "simulated":
            continue
        deps_bad = [x["node"] for x in n["needs"] if by.get(x["node"], {}).get("state") in _FAILING]
        if not deps_bad:
            affected = [k for k in impact(graph, n["key"]) if by[k]["state"] in _FAILING]
            out.append({"node": n["key"], "name": n["name"], "state": n["state"],
                        "also_failing_because_of_it": affected})
    return sorted(out, key=lambda r: -len(r["also_failing_because_of_it"]))


def whatif(graph: dict, key: str) -> dict:
    """SIMULATION: what the portal would show if `key` failed now. Changes nothing."""
    by = {n["key"]: n for n in graph["nodes"]}
    if key not in by:
        return {"error": "unknown node", "node": key}
    hit = impact(graph, key)
    devices = [k for k in [key, *hit] if by[k]["kind"] in ("door", "environment", "bin", "security_camera",
                                                            "robot", "pc", "entry_camera")]
    # recovery order: the failed node first, then whatever needs it, nearest first (BFS order)
    order, q, seen = [key], deque([key]), {key}
    while q:
        k = q.popleft()
        for up in by[k]["needed_by"]:
            if up not in seen:
                seen.add(up)
                order.append(up)
                q.append(up)
    return {"kind": "SIMULATED - nothing was changed", "node": key, "name": by[key]["name"],
            "affected": [{"node": k, "name": by[k]["name"], "now": by[k]["state"]} for k in hit],
            "expected_alerts": [f"{by[k]['name']} offline" for k in devices],
            "recovery_order": order,
            "note": "Recover in this order and confirm each step with its own check before the next."}
