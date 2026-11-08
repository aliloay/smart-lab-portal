"""
Data provenance and thesis experiments.

  * a new record takes the current data mode; switching the mode never
    changes existing records, and the application refuses to rewrite a
    record's provenance;
  * a RUNNING experiment stamps new records with its own mode and id, so its
    events can be counted exactly; only one runs at a time;
  * administrators set the data mode; staff run experiments; students do
    neither.
"""
import pytest

from app.models import AccessEvent, Alert, AlertSeverity, EventType, ExperimentTrial
from app.services import provenance
from app.services.events import log_event
from tests.conftest import auth_headers


@pytest.fixture(autouse=True)
def _fresh_cache():
    provenance.invalidate()
    yield
    provenance.invalidate()


def _event(db, lab):
    e = log_event(db, EventType.DOOR_CLOSED, lab_id=lab.id, message="test")
    db.commit()
    db.refresh(e)
    return e


def test_new_rows_take_the_mode_old_rows_keep_theirs(client, db, lab, admin):
    first = _event(db, lab)
    assert first.provenance == "SOFTWARE_TEST"                 # the test suite's default
    h = auth_headers(client, admin.email)
    r = client.put("/api/system/data-mode", headers=h, json={"mode": "BENCH_TEST"})
    assert r.status_code == 200 and r.json()["mode"] == "BENCH_TEST"
    second = _event(db, lab)
    db.refresh(first)
    assert (first.provenance, second.provenance) == ("SOFTWARE_TEST", "BENCH_TEST")
    assert client.get("/api/system/data-mode", headers=h).json()["mode"] == "BENCH_TEST"


def test_provenance_cannot_be_rewritten(db, lab):
    e = _event(db, lab)
    e.provenance = "REAL_OPERATION"
    with pytest.raises(provenance.ProvenanceImmutable):
        db.flush()
    db.rollback()


def test_running_experiment_stamps_its_records(client, db, lab, staff):
    h = auth_headers(client, staff.email)
    exp = client.post("/api/experiments", headers=h, json={
        "name": "Door: valid RFID x10", "subsystem": "DOOR", "test_condition": "card held 2 cm",
        "expected_result": "10 grants"}).json()
    assert exp["code"].startswith("EXP-") and exp["status"] == "PLANNED"
    assert client.post(f"/api/experiments/{exp['id']}/start", headers=h).status_code == 200
    inside = _event(db, lab)
    db.add(Alert(severity=AlertSeverity.INFO, title="t", detail=""))
    db.commit()
    assert (inside.provenance, inside.experiment_id) == ("PHYSICAL_TEST", exp["id"])
    t = client.post(f"/api/experiments/{exp['id']}/trials", headers=h, json={
        "repeat_number": 1, "input": "card A", "expected": "grant", "actual": "grant",
        "measurement": 0.84, "unit": "s", "result": "PASS"})
    assert t.status_code == 201
    second = client.post("/api/experiments", headers=h, json={"name": "x", "subsystem": "DOOR"}).json()
    assert client.post(f"/api/experiments/{second['id']}/start", headers=h).status_code == 409
    assert client.post(f"/api/experiments/{exp['id']}/stop", headers=h,
                       json={"actual_result": "10 grants", "result": "PASS"}).status_code == 200
    after = _event(db, lab)
    assert after.experiment_id is None and after.provenance == "SOFTWARE_TEST"
    d = client.get(f"/api/experiments/{exp['id']}", headers=h).json()
    assert d["status"] == "FINISHED" and d["result"] == "PASS"
    assert d["records"]["access_events"] == 1 and d["records"]["alerts"] == 1
    assert len(d["trials"]) == 1 and db.query(ExperimentTrial).count() == 1


def test_who_may_do_what(client, alice, staff):
    student, h_staff = auth_headers(client, alice.email), auth_headers(client, staff.email)
    assert client.put("/api/system/data-mode", headers=h_staff, json={"mode": "REAL_OPERATION"}).status_code == 403
    assert client.post("/api/experiments", headers=student, json={"name": "x", "subsystem": "DOOR"}).status_code == 403
    assert client.put("/api/system/data-mode", headers=auth_headers(client, staff.email),
                      json={"mode": "NOT_A_MODE"}).status_code in (403, 422)
