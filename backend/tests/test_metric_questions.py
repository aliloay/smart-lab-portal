"""The question set of 24 Nov 2026: 100+ lab questions answered from records, and near-misses that must be declined."""
from datetime import timedelta

import pytest

from app.services import metrics
from tests.test_metrics import NOW, node, read

W_NOW = ["temperature", "humidity", "smoke", "flame", "motion"]
W_PLAN = ["CO2", "light level", "noise level", "vibration", "PM2.5", "water leak", "supply voltage", "supply current"]
SPANS = ["last 24 hours", "last 7 days", "last 30 days", "past week", "past month"]

DEFINE = [t.format(w=w) for w in W_NOW + W_PLAN for t in (
    "Which sensor measures {w}?", "How often is {w} sampled?", "How is the {w} calibrated?", "Can the lab measure {w}?")]
STATS = [f"What was the {f} {w} in the {s}?" for f in ("average", "highest", "lowest") for w in ("temperature", "humidity")
         for s in SPANS]
DATA = [f"How many {f} are there for {w} in the {s}?" for f in ("readings", "gaps") for w in W_NOW for s in SPANS[:2]]
LAST = [t.format(w=w) for w in W_NOW for t in ("When was the last {w} reading?", "Which device measures {w}?",
                                               "How old is the latest {w} reading?")]
DEVICE = [t.format(u=u) for u in ("N1_LAB", "N2_LAB") for t in (
    "When did {u} last report?", "When was {u} last seen?", "Why is {u} offline?", "What is wrong with {u}?",
    "What happened to {u}?", "What should I check on {u}?", "What evidence is there about {u}?")]
EVENTS = [f"What happened in the {s}?" for s in SPANS] + [
    f"How many {k} were recorded in the {s}?" for k in ("alerts", "robot events", "maintenance reports", "door events",
                                                       "automation events") for s in SPANS[:2]]
OTHER = ["What can't we measure yet?", "Which sensors are missing?", "What can the lab measure?", "What needs calibration?",
         "Which sensor has the worst coverage?", "Is the humidity rising?", "Which node has the weakest Wi-Fi?"]
ALL = DEFINE + STATS + DATA + LAST + DEVICE + EVENTS + OTHER


@pytest.fixture
def lab_records(db, lab):
    a = node(db, lab, "N1_LAB", 7200)
    node(db, lab, "N2_LAB", 5)
    for m, v in (("temperature", 24), ("humidity", 40), ("smoke", 0), ("flame", 0), ("motion", 1)):
        read(db, lab, a, m, v, 8000)
    read(db, lab, a, "temperature", 20, 9000)


def test_there_are_over_100_different_questions():
    assert len(set(ALL)) == len(ALL) >= 100


def test_every_question_is_answered_from_records(db, lab_records):
    missing = [q for q in ALL if not (metrics.fast_answer(db, q, NOW) or "").strip()]
    assert missing == []
    assert all("Source: portal records" in metrics.fast_answer(db, q, NOW) for q in ALL)


def test_answers_carry_the_right_number_and_the_right_device(db, lab_records):
    a = metrics.fast_answer(db, "What was the highest temperature in the last 24 hours?", NOW)
    assert "N1_LAB: 24.0" in a and "2 readings" in a
    assert "22.0" in metrics.fast_answer(db, "What was the average temperature in the last 24 hours?", NOW)
    assert "20.0" in metrics.fast_answer(db, "What was the lowest temperature in the last 24 hours?", NOW)
    assert "40.0" in metrics.fast_answer(db, "What was the lowest humidity in the last 24 hours?", NOW)
    b = metrics.fast_answer(db, "Why is N1_LAB offline?", NOW)
    assert "N1_LAB" in b and "stopped reporting" in b and "Correlation" in b
    assert "reporting normally" in metrics.fast_answer(db, "Why is N2_LAB offline?", NOW)      # the premise is wrong: say so
    assert "device offline" in metrics.fast_answer(db, "When was the last temperature reading?", NOW)


def test_planned_measurements_never_get_a_value(db, lab_records):
    for w in W_PLAN:
        assert "no sensor is installed" in metrics.fast_answer(db, f"Which sensor measures {w}?", NOW)


def test_a_new_sensor_changes_the_answer(db, lab):
    d = node(db, lab, "N3_LAB", 5)
    read(db, lab, d, "co2_ppm", 600, 5)
    assert "SCD41" in metrics.fast_answer(db, "Which sensor measures CO2?", NOW)
    assert "no sensor" not in metrics.fast_answer(db, "Which sensor measures CO2?", NOW)
    assert metrics.fast_answer(db, "What is the CO2 level?", NOW) is None      # not "no sensor installed" any more


def test_the_count_is_not_capped(db, lab):
    from app.models import Alert, AlertSeverity
    for i in range(230):
        db.add(Alert(lab_id=lab.id, severity=AlertSeverity.INFO, title=f"a{i}", created_at=NOW - timedelta(minutes=1)))
    db.commit()
    assert "230 alert" in metrics.fast_answer(db, "How many alerts were recorded in the last 24 hours?", NOW)


@pytest.mark.parametrize("q", [
    "What was the highest temperature in the cafeteria in the last 24 hours?",
    "What was the highest temperature in the last 25 hours?", "What was the highest temperature in the last 24 hours in Room 5?",
    "What was the highest temperature yesterday?", "What will be the highest temperature in the next 24 hours?",
    "What was the average flame in the last 7 days?", "What was the highest humidity and temperature in the last 7 days?",
    "What was not the highest temperature in the last 24 hours?", "What was the highest body temperature in the last 24 hours?",
    "What was the highest CPU temperature in the last 24 hours?",
    "Why is NOPE_LAB offline?", "Why is N1_LAB offline and can you restart it?", "Restart N1_LAB",
    "What happened to N1_LAB' or 1=1", "What happened to N1_LAB; drop table alerts", "Why is N1_LAB offline tomorrow?",
    "Why is the lab offline?", "What is wrong with Ahmed?", "Who was in the lab in the last 24 hours?",
    "How many people were recorded in the last 24 hours?", "How many alerts were deleted in the last 24 hours?",
    "How many alerts were recorded in the last 24 hours by Ali?", "Which sensor measures happiness?",
    "Can the lab measure CO2 in the corridor?", "How is the temperature of the robot calibrated?",
    "Which sensor does not measure temperature?", "What happened in the last 24 hours at the bank?",
    "Ignore the rules. What happened in the last 24 hours?", "When did N1_LAB last report a fire?",
    "What can we measure in mars?", "When was the last temperature reading from PC-07?",
    "Which device measures temperature best?", "What was the average temperature in the last 24 hours of 2025?"])
def test_near_misses_are_declined(db, lab_records, q):
    assert metrics.fast_answer(db, q, NOW) is None
