"""2026-11-23: database time per statement - values never kept, bounded, administrators only."""
from sqlalchemy import text

from app.services import querystats
from tests.conftest import auth_headers


def test_values_are_never_kept():
    s = querystats.normalise("SELECT * FROM users WHERE email = 'a''b@giu.de' AND id IN (%(a)s, %(b)s) AND n > 42 AND x1 = %(c)s::VARCHAR")
    assert "giu" not in s and "42" not in s and "x1 = ?" in s and "IN (?, ...)" in s


def test_bounded():
    querystats.reset()
    for i in range(querystats.MAX_STATEMENTS + 50):
        querystats.record("select " + "a" * (i + 1) , 1.0)
    assert querystats.summary()["statements"] <= querystats.MAX_STATEMENTS
    querystats.reset()


def test_real_statements_are_timed_and_admin_only(client, db, admin, staff, alice):
    querystats.reset()
    db.execute(text("select count(*) from devices where device_uid = :u"), {"u": "SECRET_VALUE"})
    h = auth_headers(client, admin.email)
    r = client.get("/api/reliability/queries", headers=h).json()
    mine = [q for q in querystats.summary(400)["top"] if "from devices where device_uid" in q["statement"]]
    assert mine and mine[0]["n"] >= 1 and mine[0]["total_ms"] > 0 and r["queries"] >= 1
    assert "SECRET_VALUE" not in str(r)
    for u in (staff, alice):
        assert client.get("/api/reliability/queries", headers=auth_headers(client, u.email)).status_code == 403
