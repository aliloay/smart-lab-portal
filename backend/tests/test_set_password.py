"""Local password reset tool (2026-10-27): hidden prompt, policy, audit; never a password on the command line."""
import set_password
from app.core.security import verify_password
from app.models import AuditLog, User


def answers(*vals):
    it = iter(vals)
    return lambda prompt: next(it)


def test_sets_password_with_policy_and_audit(db, admin, capsys):
    good = "Lab-Portal-strong-2026!"
    assert set_password.main([admin.email], answers(good, good), db=db) == 0
    db.refresh(admin)
    assert verify_password(good, admin.hashed_password)
    assert db.query(AuditLog).filter_by(action="PASSWORD_SET_LOCALLY", entity_id=str(admin.id)).count() == 1
    assert good not in capsys.readouterr().out                      # never printed


def test_mismatch_weak_and_unknown_change_nothing(db, admin):
    before = admin.hashed_password
    assert set_password.main([admin.email], answers("Abcdefgh-12345!", "different"), db=db) == 1
    assert set_password.main([admin.email], answers("123", "123"), db=db) == 1
    assert set_password.main(["nobody@x.org"], answers("x", "x"), db=db) == 1
    assert set_password.main(["not-an-email"], answers(), db=db) == 2
    db.refresh(admin)
    assert admin.hashed_password == before
