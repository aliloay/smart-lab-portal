"""23 Nov closure regression tests (reports/claude-final-execution-closure-2026-11-23)."""
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.api.routes import face_submissions as fsub
from app.models import FaceSubmission


def test_locked_reread_sees_an_approval_committed_meanwhile(db, alice):
    """C-01 (B-11 follow-up): approve() first reads the submission, then re-reads it FOR UPDATE. The locked
    re-read must refresh the row: if another Approve finished in between, the stale in-memory 'PENDING'
    copy let the second request enrol the same photos again."""
    s = FaceSubmission(user_id=alice.id, status="PENDING", photo_count=1)
    db.add(s)
    db.commit()
    assert db.get(FaceSubmission, s.id).status == "PENDING"          # the first read (identity map)
    db.execute(text("UPDATE face_submissions SET status = 'APPROVED' WHERE id = :i"), {"i": s.id})
    with pytest.raises(HTTPException) as e:
        fsub._waiting_or_409(db, s.id)
    assert e.value.status_code == 409
