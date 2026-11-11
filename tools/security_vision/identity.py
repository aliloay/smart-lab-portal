"""
Identity evidence and state for each tracked person (the Labeler decides WHO
by its rules; this module records WHY, HOW SURE, and when that changes).

Every track carries an IdentityRecord:

    state        UNKNOWN / TENTATIVE / FACE_CONFIRMED / DOOR_CONFIRMED /
                 FUSED_CONFIRMED / REID_CONFIRMED / OCCLUDED /
                 IDENTITY_UNCERTAIN / IDENTITY_CONFLICT
    confidence   0-1, from the evidence and how fresh it is
    evidence     the last observations (face match + score, door entry, look
                 match, place hand-back, conflict), each with its time

Rules (all thresholds in IdentityConfig, none tuned on lab data yet):

  * Confidence starts at the strength of what named the person (door entry,
    two agreeing face matches, both together) and DECAYS with a half-life
    while nothing new confirms it. A face match or a clear look match tops
    it up. One weak observation never replaces a name (hysteresis: the
    Labeler only names an unnamed track; this module never renames).
  * A face that clearly says SOMEONE ELSE (FACE_VOTES agreeing matches) does
    not switch the name: the state becomes IDENTITY_CONFLICT and an event is
    raised. A wrong name is worse than an uncertain one.
  * Below uncertain_at the name is shown with "?" (IDENTITY_UNCERTAIN). A
    name only from a face (no door entry) that decays below drop_at is
    removed: the person becomes Unknown again rather than stay mislabelled.
    A door name is never removed here - the door is the authority.

Pure logic, tested in test_identity.py. Nothing biometric is stored here:
only names, scores and times.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

# Names given back by look, place, a crossing re-deal or the other camera: weaker evidence than the
# door or the face that named the person in the first place (2026-10-18: a crossing re-deal used to
# start at the door's 0.90 - as if the door had just named them).
REACQUIRE_HOW = ("look", "place", "crossing", "other camera")

STATES = ("UNKNOWN", "TENTATIVE", "FACE_CONFIRMED", "DOOR_CONFIRMED", "FUSED_CONFIRMED",
          "REID_CONFIRMED", "OCCLUDED", "IDENTITY_UNCERTAIN", "IDENTITY_CONFLICT")


@dataclass
class IdentityConfig:
    door_strength: float = 0.90        # named by the door entry
    face_strength: float = 0.80        # named by agreeing face matches (no door)
    reacquire_strength: float = 0.65   # given back by look or by place after the track was lost
    fused_strength: float = 0.97       # door and face agree
    half_life_s: float = 180.0         # confidence halves after this long without new evidence
    face_boost: float = 0.25           # a fresh matching face moves confidence this far toward its ceiling
    look_boost: float = 0.04           # a clear look match (per second of such evidence)
    look_match_max: float = 0.30       # look distance counted as a match
    uncertain_at: float = 0.50
    drop_at: float = 0.25              # face-only names below this are removed
    face_confirmed_s: float = 30.0     # a face match this recent = FACE / FUSED confirmed
    evidence_kept: int = 12


@dataclass
class Evidence:
    t: float
    kind: str                          # door / face / look / place / conflict / decay / drop
    detail: str
    score: Optional[float] = None

    def as_dict(self) -> dict:
        return {"t": round(self.t, 2), "kind": self.kind, "detail": self.detail,
                "score": None if self.score is None else round(self.score, 3)}


@dataclass
class IdentityRecord:
    label: Optional[str] = None
    state: str = "UNKNOWN"
    confidence: float = 0.0
    source: Optional[str] = None
    named_at: Optional[float] = None
    last_face_at: Optional[float] = None
    last_face_score: Optional[float] = None
    last_evidence_at: float = 0.0
    conflict_with: Optional[str] = None
    evidence: deque = field(default_factory=lambda: deque(maxlen=12))

    def add(self, e: Evidence):
        self.evidence.append(e)

    def as_dict(self) -> dict:
        return {"state": self.state, "confidence": round(self.confidence, 2), "source": self.source,
                "conflict_with": self.conflict_with, "evidence": [e.as_dict() for e in self.evidence]}


@dataclass
class IdentityEvent:
    kind: str                          # PERSON_IDENTITY_CONFIRMED / _UNCERTAIN / _CONFLICT / _DROPPED / _REACQUIRED
    track_id: int
    label: Optional[str]
    detail: str


class IdentityLedger:
    def __init__(self, cfg: Optional[IdentityConfig] = None):
        self.cfg = cfg or IdentityConfig()
        self.records: dict[int, IdentityRecord] = {}
        self._last_t: Optional[float] = None

    # -- observations (called by the Labeler / service) -------------------
    def face_observation(self, track_id: int, label: str, score: Optional[float], now: float):
        rec = self.records.setdefault(track_id, IdentityRecord())
        rec.last_face_at, rec.last_face_score = now, score
        rec.add(Evidence(now, "face", f"face matches {label}", score))

    # -- per analysis frame -------------------------------------------------
    def update(self, tracks: list, now: float, look_distance=None,
               agreed_face=None) -> list[IdentityEvent]:
        """tracks: vision.Track objects (label/source/entered/verified/crowded set by the
        Labeler). look_distance(track, label) -> distance or None. agreed_face(track) ->
        the label FACE_VOTES recent face matches agree on, or None."""
        c = self.cfg
        dt = 0.0 if self._last_t is None else max(0.0, now - self._last_t)
        self._last_t = now
        events: list[IdentityEvent] = []
        live = {t.id for t in tracks}
        for tid in [k for k in self.records if k not in live]:
            del self.records[tid]
        for t in tracks:
            rec = self.records.setdefault(t.id, IdentityRecord())
            if not t.label:
                if rec.label:                              # the name was taken away elsewhere
                    rec.label = None
                rec.state = "TENTATIVE" if (rec.last_face_at and now - rec.last_face_at < 10) else "UNKNOWN"
                rec.confidence, rec.source, rec.conflict_with = 0.0, None, None
                self._export(t, rec)
                continue
            if rec.label != t.label:                       # newly named (by door, face, look or place)
                rec.label, rec.source, rec.named_at = t.label, t.source, now
                how = getattr(t, "named_by", None) or t.source or "?"
                strength = c.reacquire_strength if how in REACQUIRE_HOW else (
                    c.fused_strength if t.verified else
                    c.door_strength if t.source == "door" else c.face_strength)
                rec.confidence = strength
                rec.last_evidence_at = now
                rec.conflict_with = None
                rec.add(Evidence(now, how, f"named {t.label} ({how})", strength))
                events.append(IdentityEvent("PERSON_TRACK_REACQUIRED" if how in REACQUIRE_HOW
                                            else "PERSON_IDENTITY_CONFIRMED", t.id, t.label,
                                            f"{t.label} by {how}"))
            # Decay, then fresh evidence tops up.
            if dt:
                rec.confidence *= 0.5 ** (dt / c.half_life_s)
            ceiling = c.fused_strength if t.verified else (
                c.door_strength if t.source == "door" else c.face_strength)
            face_fresh = rec.last_face_at is not None and now - rec.last_face_at < c.face_confirmed_s
            face_now = agreed_face(t) if agreed_face else None
            if face_now == t.label and rec.last_face_at is not None and rec.last_face_at > rec.last_evidence_at:
                rec.confidence += (max(ceiling, c.face_strength) - rec.confidence) * c.face_boost * 2
                rec.last_evidence_at = rec.last_face_at
            if look_distance and not t.crowded:
                d = look_distance(t, t.label)
                if d is not None and d <= c.look_match_max and dt:
                    rec.confidence = min(ceiling, rec.confidence + c.look_boost * dt)
            rec.confidence = max(0.0, min(1.0, rec.confidence))
            # Conflict: the face clearly says someone else. The name is NOT switched.
            if face_now is not None and face_now != t.label:
                if rec.conflict_with != face_now:
                    rec.conflict_with = face_now
                    rec.add(Evidence(now, "conflict", f"face says {face_now}, name is {t.label}"))
                    events.append(IdentityEvent("PERSON_IDENTITY_CONFLICT", t.id, t.label,
                                                f"named {t.label} ({t.source}), face matches {face_now}"))
            elif face_now == t.label:
                rec.conflict_with = None
            # Face-only name decayed too far: back to Unknown rather than stay wrong.
            if t.source == "face" and not t.entered and rec.confidence < c.drop_at and not t.crowded:
                rec.add(Evidence(now, "drop", f"{t.label} dropped: confidence {rec.confidence:.2f}"))
                events.append(IdentityEvent("PERSON_IDENTITY_DROPPED", t.id, t.label,
                                            f"face-only name {t.label} not confirmed for too long"))
                t.label = t.name = t.role = t.source = None
                t.verified = False
                rec.label, rec.state, rec.confidence = None, "UNKNOWN", 0.0
                self._export(t, rec)
                continue
            old = rec.state
            rec.state = self._state(t, rec, face_fresh)
            if rec.state == "IDENTITY_UNCERTAIN" and old not in ("IDENTITY_UNCERTAIN", "IDENTITY_CONFLICT"):
                rec.add(Evidence(now, "decay", f"confidence {rec.confidence:.2f}"))
                events.append(IdentityEvent("PERSON_IDENTITY_UNCERTAIN", t.id, t.label,
                                            f"{t.label}: no fresh evidence, confidence {rec.confidence:.2f}"))
            self._export(t, rec)
        return events

    def _state(self, t, rec: IdentityRecord, face_fresh: bool) -> str:
        if rec.conflict_with:
            return "IDENTITY_CONFLICT"
        if t.crowded:
            return "OCCLUDED"
        if t.source == "look":                             # a guess from the stored look (vision.Labeler.LOOK_GUESS)
            return "IDENTITY_UNCERTAIN"
        if rec.confidence < self.cfg.uncertain_at:
            return "IDENTITY_UNCERTAIN"
        if t.verified and face_fresh:
            return "FUSED_CONFIRMED"
        if face_fresh:
            return "FACE_CONFIRMED"
        if t.source == "door" and t.entered and rec.named_at is not None and t.verified is False \
                and rec.last_face_at is None:
            return "DOOR_CONFIRMED"
        return "REID_CONFIRMED"                            # kept by look / track continuity since

    @staticmethod
    def _export(t, rec: IdentityRecord):
        t.identity_state, t.identity_confidence = rec.state, round(rec.confidence, 2)

    def explain(self, track_id: int) -> Optional[dict]:
        rec = self.records.get(track_id)
        return rec.as_dict() if rec else None


def half_life_for(confidence_from: float, confidence_to: float, seconds: float) -> float:
    """Helper for choosing half_life_s from a wanted decay (documentation / tuning)."""
    return seconds * math.log(0.5) / math.log(confidence_to / confidence_from)
