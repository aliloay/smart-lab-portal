"""
Lab access setup - information for the person, nothing else.

The door logic is unchanged: step 1 (booking QR or RFID card) then step 2
(fingerprint or face) that must match step 1. This module only records
whether a person's fingerprint and Face ID have been enrolled under their
door identity (USERn), so the portal can tell a new user, as soon as they
sign in, to visit lab staff and get it done. Otherwise they would pass
step 1 at the door and be refused at step 2 without knowing why.

The flags are set by staff on Users & roles once the finger is stored on the
door's sensor and the face photos are on the face server. They open nothing
and are never consulted by the door.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import User
from app.services.notifications import notify

FACTORS = ("fingerprint", "face")
_NAME = {"fingerprint": "Fingerprint", "face": "Face ID"}


def status(user: User) -> dict:
    subject = user.auth_subject
    fp, face = user.fingerprint_enrolled_at, user.face_enrolled_at
    who = f" under your door identity {subject}" if subject else ""
    items = [
        {"key": "identity", "label": "Door identity", "done": bool(subject),
         "value": subject, "at": None,
         "how": "Assigned automatically when your account is created."},
        {"key": "fingerprint", "label": "Fingerprint", "done": bool(fp), "at": fp,
         "how": f"Visit lab staff to register your finger on the door's fingerprint reader{who}."},
        {"key": "face", "label": "Face ID", "done": bool(face), "at": face,
         "how": f"Visit lab staff to take your face photos for the door camera{who}."},
    ]
    pending = [i["label"] for i in items if not i["done"]]
    complete = not pending
    if complete:
        summary = "Your fingerprint and Face ID are confirmed. You are ready for lab access."
    else:
        summary = ("Please visit the lab staff or an administrator to confirm your "
                   + " and ".join(p.replace("Fingerprint", "fingerprint")
                                  for p in pending if p != "Door identity")
                   + ". You can already book a lab and pass the first check at the "
                     "door (QR code or RFID card), but the door cannot complete the "
                     "second check (fingerprint or face) until they are registered.")
    # Only people with a door identity use the door; an account without one
    # (e.g. an administrator who never enters a lab) is not nagged.
    return {"complete": complete, "needed": bool(subject) and not complete,
            "auth_subject": subject, "items": items,
            "pending": pending, "summary": summary}


def mark(db: Session, user: User, factor: str, done: bool) -> bool:
    """Staff confirm (or undo) an enrolment. Returns True if it changed."""
    if factor not in FACTORS:
        raise ValueError(factor)
    col = f"{factor}_enrolled_at"
    if (getattr(user, col) is not None) == done:
        return False
    setattr(user, col, datetime.now(timezone.utc) if done else None)
    db.flush()
    if done:
        st = status(user)
        notify(db, [user.id], "ACCESS_SETUP",
               f"{_NAME[factor]} confirmed"
               + (" - lab access setup complete" if st["complete"] else ""),
               body=("Staff confirmed your " + _NAME[factor].lower() + ". "
                     + ("Everything is set." if st["complete"] else
                        "Still to do: " + ", ".join(st["pending"]) + ".")),
               link="/profile", severity="info",
               dedupe_key=f"access-setup:{factor}:{user.id}:"
                          f"{getattr(user, col).isoformat()}")
    return True


def welcome(db: Session, user: User) -> None:
    """Once, when an account is created: what the person still has to do."""
    st = status(user)
    if not st["needed"]:
        return
    notify(db, [user.id], "ACCESS_SETUP",
           "Action needed: confirm your fingerprint and Face ID",
           body=st["summary"], link="/profile", severity="warning",
           dedupe_key=f"access-setup:welcome:{user.id}")
