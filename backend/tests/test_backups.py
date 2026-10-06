"""
Database backups are watched: the backup service writes backup_status.json
after every run; a failed run, or no success for too long, raises ONE
critical alert (and tells the admins); a later success resolves it.
"""
import json
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models import Alert, Notification
from app.services import backups
from tests.conftest import auth_headers


def _status(tmp_path, ok=True, age_h=0.5, every_h=6):
    t = (datetime.now(timezone.utc) - timedelta(hours=age_h)).isoformat()
    p = tmp_path / "backup_status.json"
    p.write_text(json.dumps({"ok": ok, "last_attempt": t, "last_success": t if ok else None,
                             "file": "auto_smartlab_x.dump", "size_kb": 212, "every_hours": every_h}))
    return p


def _open(db):
    return db.query(Alert).filter(Alert.title.like("Database backup%"), Alert.is_resolved.is_(False)).all()


def test_fresh_success_raises_nothing(db, tmp_path, monkeypatch, admin):
    monkeypatch.setattr(settings, "BACKUP_STATUS_PATH", str(_status(tmp_path)))
    info = backups.check(db)
    assert info["state"] == "OK" and info["size_kb"] == 212 and _open(db) == []


def test_failed_backup_alerts_once_then_clears(db, tmp_path, monkeypatch, admin):
    monkeypatch.setattr(settings, "BACKUP_STATUS_PATH", str(_status(tmp_path, ok=False)))
    backups.check(db)
    backups.check(db)
    assert len(_open(db)) == 1 and _open(db)[0].severity.value == "CRITICAL"
    assert db.query(Notification).filter(Notification.user_id == admin.id).count() == 1
    _status(tmp_path, ok=True)
    assert backups.check(db)["state"] == "OK" and _open(db) == []


def test_no_success_for_too_long_alerts(db, tmp_path, monkeypatch, admin):
    monkeypatch.setattr(settings, "BACKUP_STATUS_PATH", str(_status(tmp_path, age_h=14, every_h=6)))
    assert backups.check(db)["state"] == "STALE" and len(_open(db)) == 1


def test_system_status_shows_the_backup(client, tmp_path, monkeypatch, admin):
    monkeypatch.setattr(settings, "BACKUP_STATUS_PATH", str(_status(tmp_path)))
    r = client.get("/api/system/status", headers=auth_headers(client, admin.email))
    assert r.status_code == 200 and r.json()["backup"]["state"] == "OK"


def test_not_configured_is_silent(db, monkeypatch, admin):
    monkeypatch.setattr(settings, "BACKUP_STATUS_PATH", "")
    assert backups.check(db)["state"] == "NOT_CONFIGURED" and _open(db) == []
