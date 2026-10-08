"""
Robot motion fusion: the robot's telemetry and the camera's view of the
robot's box, compared - disagreement is shown, never hidden.

    telemetry   MOVING / STATIONARY / TELEMETRY_STALE / OFFLINE / UNKNOWN
    camera      MOVING / STILL / OCCLUDED / UNKNOWN (robotvision.py), only
                while the camera is reporting; "moving" = motion seen within
                WINDOW_S (the camera reports every ~0.5 s; timings measured
                in the lab before narrowing the window)

    fusion:
      MOVEMENT_VERIFIED            telemetry moving, camera saw motion in the box
      MOVEMENT_TELEMETRY_ONLY      telemetry moving, camera saw nothing (not occluded)
      VISUALLY_OCCLUDED            telemetry moving, a person blocks the box
      STATIONARY_VERIFIED          both still
      STATIONARY                   telemetry still, no usable camera view
      VISUAL_ANOMALY               camera sees motion, telemetry says still
      VISUAL_MOVEMENT_DURING_TELEMETRY_OUTAGE
      TELEMETRY_STALE / OFFLINE / UNKNOWN   no telemetry, nothing seen
      SIMULATION                   demo telemetry: never compared with the real camera

Direction / magnitude agreement (kinematic projection) needs a camera-to-
robot calibration done in the lab; until then agreement means motion vs no
motion only - stated as such in the evidence.
"""
from __future__ import annotations

from typing import Optional

WINDOW_S = 3.0
DISAGREE_HOLD_S = 3.0            # a disagreement must last this long before it is an event

ABNORMAL = {"VISUAL_ANOMALY", "VISUAL_MOVEMENT_DURING_TELEMETRY_OUTAGE", "MOVEMENT_TELEMETRY_ONLY"}


def camera_view(visual: Optional[dict], camera_online: bool, now: float) -> str:
    if not camera_online or not visual:
        return "UNKNOWN"
    st = visual.get("state")
    if st == "OCCLUDED":
        return "OCCLUDED"
    last = visual.get("last_motion_at")
    if st == "MOVING" or (last is not None and now - float(last) <= WINDOW_S):
        return "MOVING"
    return "STILL" if st == "STILL" else "UNKNOWN"


def fuse(telemetry_state: str, source: Optional[str], view: str) -> str:
    if source == "SIMULATION":
        return "SIMULATION"
    t = telemetry_state
    if t == "MOVING":
        return {"MOVING": "MOVEMENT_VERIFIED", "OCCLUDED": "VISUALLY_OCCLUDED",
                "STILL": "MOVEMENT_TELEMETRY_ONLY"}.get(view, "MOVEMENT_TELEMETRY_ONLY")
    if t == "STATIONARY":
        return {"MOVING": "VISUAL_ANOMALY", "STILL": "STATIONARY_VERIFIED"}.get(view, "STATIONARY")
    if view == "MOVING":
        return "VISUAL_MOVEMENT_DURING_TELEMETRY_OUTAGE"
    return t if t in ("TELEMETRY_STALE", "OFFLINE") else "UNKNOWN"


def evidence(telemetry_state: str, source: Optional[str], view: str, visual: Optional[dict],
             camera_online: bool, telemetry_age_s: Optional[float]) -> list[dict]:
    """Each input with whether it supports the decision - for the evidence panel."""
    ev = [{"source": "telemetry", "value": telemetry_state, "detail": f"{source or '?'}"
           + (f", {telemetry_age_s:.1f} s old" if telemetry_age_s is not None else "")},
          {"source": "camera", "value": view if camera_online else "OFFLINE",
           "detail": "" if not visual else
           f"moving cells {visual.get('moving_share')}, flow {visual.get('magnitude')} px, occlusion {visual.get('occlusion')}"},
          {"source": "kinematics", "value": "NOT CALIBRATED",
           "detail": "direction/magnitude check needs the camera-robot calibration (lab)"}]
    return ev


def transition(prev: Optional[str], prev_since: Optional[float], new: str, now: float) -> tuple[str, float, Optional[str]]:
    """(state to keep, since, event kind or None). A new abnormal state becomes an
    event only after DISAGREE_HOLD_S (no flicker events); normal states at once."""
    if new == prev:
        return new, prev_since or now, None
    if new in ABNORMAL:
        return new, now, None                      # pending: event when held (see held())
    return new, now, ("MOVEMENT_VISUALLY_VERIFIED" if new == "MOVEMENT_VERIFIED" and prev != new else None)


def held(state: str, since: Optional[float], reported: bool, now: float) -> Optional[str]:
    if state in ABNORMAL and not reported and since is not None and now - since >= DISAGREE_HOLD_S:
        return {"VISUAL_ANOMALY": "VISUAL_TELEMETRY_DISAGREEMENT",
                "VISUAL_MOVEMENT_DURING_TELEMETRY_OUTAGE": "VISUAL_MOVEMENT_DURING_TELEMETRY_OUTAGE",
                "MOVEMENT_TELEMETRY_ONLY": "TELEMETRY_MOVEMENT_NOT_VISUALLY_VERIFIED"}[state]
    return None
