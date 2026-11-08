---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/policy.py"
source_hash: "c8cb5dd8a0ecda12b7a338c25ab93800931771711941b147d6d50448342eae0e"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/policy.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_reliability.py]] - imports
- [[backend_app_services_investigate.py]] - imports

```py
"""
Central action policy (2026-10-18): may this action run, and how?

    ALLOWED AUTOMATICALLY   low-risk, reversible, verifiable; may run without a person
    REQUIRES APPROVAL       a person with the right role confirms it first (and it is audited)
    DRY RUN ONLY            evaluated and logged, nothing is sent (robot motion until sign-off)
    PROHIBITED              never from the portal / never automatically
    INSUFFICIENT EVIDENCE   the action is not known to this policy: not allowed until it is reviewed

Physical robot motion, controller changes, door-lock behaviour, firmware flashing, safety settings and
production data changes are never automatic. The software STOP is not a safety-rated emergency stop.
evaluate() is pure; the API that exposes it records each evaluation in the audit log.
"""
from __future__ import annotations

ALLOWED, APPROVAL, DRY, PROHIBITED, UNKNOWN = ("ALLOWED AUTOMATICALLY", "REQUIRES APPROVAL", "DRY RUN ONLY",
                                               "PROHIBITED", "INSUFFICIENT EVIDENCE")

# action: (when automatic, when a person asks, role, why)
RULES: dict[str, tuple[str, str, str, str]] = {
    "health.recheck": (ALLOWED, ALLOWED, "staff", "read-only checks; bounded timeouts"),
    "report.regenerate": (ALLOWED, ALLOWED, "staff", "local report from existing records"),
    "evidence.run": (ALLOWED, ALLOWED, "admin", "read-only evidence tool; bounded load"),
    "incident.note": (PROHIBITED, ALLOWED, "staff", "a note is a person's statement"),
    "incident.resolve": (PROHIBITED, ALLOWED, "staff", "closing needs a person's reason; conditions that clear "
                                                       "resolve their own alert"),
    "service.restart.backend": (ALLOWED, APPROVAL, "admin", "Docker restart policy, bounded by Docker; data kept "
                                                            "in PostgreSQL"),
    "service.restart.camera": (PROHIBITED, APPROVAL, "admin", "interrupts monitoring; the operator restarts it"),
    "service.restart.robot_collector": (PROHIBITED, APPROVAL, "admin", "read-only collector, but a robot cell is "
                                                                       "involved: the operator decides"),
    "robot.home": (PROHIBITED, DRY, "staff", "physical motion: DRY RUN until commissioning sign-off "
                                             "(ROBOT_CONTROL=live), then owner + confirmation"),
    "robot.stop": (PROHIBITED, ALLOWED, "staff", "software stop, any staff member; NOT a safety-rated emergency stop"),
    "robot.config_change": (PROHIBITED, PROHIBITED, "-", "controller configuration is changed on the pendant only"),
    "door.open": (PROHIBITED, PROHIBITED, "-", "only the master ESP32 opens the door"),
    "door.lock_logic_change": (PROHIBITED, PROHIBITED, "-", "firmware / wiring review required"),
    "firmware.flash": (PROHIBITED, APPROVAL, "admin", "authorised bench procedure with rollback image"),
    "pc.lock": (PROHIBITED, APPROVAL, "staff", "visible Win+L lock, confirmed and audited; IT policy applies"),
    "pc.screen_view": (PROHIBITED, APPROVAL, "staff", "visible notice on the PC; audited"),
    "pc.agent_install": (PROHIBITED, APPROVAL, "admin", "needs university IT approval"),
    "n8n.activate_workflow": (PROHIBITED, APPROVAL, "admin", "production automations change only with approval"),
    "config.correct": (PROHIBITED, APPROVAL, "admin", "no setting is on the auto-correct whitelist yet"),
    "database.restore_production": (PROHIBITED, PROHIBITED, "-", "restore drills use an isolated database only"),
    "data.delete_history": (PROHIBITED, PROHIBITED, "-", "records are kept (retention: indefinitely)"),
    "device.physical_check": (PROHIBITED, APPROVAL, "staff", "a person on site"),
}


def evaluate(action: str, context: dict | None = None) -> dict:
    ctx = context or {}
    rule = RULES.get(action)
    if rule is None:
        return {"action": action, "result": UNKNOWN, "reason": "not in the action policy - review it before use",
                "role": None}
    auto, manual, role, why = rule
    result = auto if ctx.get("automatic") else manual
    if action == "robot.home" and not ctx.get("automatic") and ctx.get("robot_control") == "live":
        result, why = APPROVAL, "live mode signed off: portal owner + explicit confirmation, completion from feedback"
    return {"action": action, "result": result, "reason": why, "role": role}


def table() -> list[dict]:
    return [{"action": a, "automatic": r[0], "on_request": r[1], "role": r[2], "why": r[3]} for a, r in RULES.items()]

```
