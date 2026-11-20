"""
"where is the robotics lab" answers the room from the lab record in one line (2026-11-20). It used to
match the project-documents lookup ("where is ...") and return quoted passages instead.
"""
from app.models import Lab
from app.services.agent import detect
from tests.conftest import auth_headers


def test_where_questions_detect_lab_location():
    for q in ("where is robotics lab", "Where is the PLC lab?", "which room is the robotics lab in",
              "what building is LAB_02"):
        assert detect(q, True) == "lab_location", q
    assert detect("tell me about the PLC lab", True) == "lab_info"
    assert detect("where is the door controller firmware", True) != "lab_location"


def test_answer_is_the_location_only(client, db, staff):
    db.add(Lab(code="LAB_RB", name="Robotics Lab", location="Building S, Floor 2, Room 214"))
    db.commit()
    r = client.post("/api/ai/ask", headers=auth_headers(client, staff.email),
                    json={"question": "where is robotics lab"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["instant"] and "Building S, Floor 2, Room 214" in out["answer"]
    assert "documents" not in out["answer"] and len(out["answer"]) < 120


def test_admin_corrects_the_room_and_it_is_audited(client, db, admin, staff):
    from app.models import AuditLog
    lab = Lab(code="LAB_RB", name="Robotics Lab", location="Building S, Floor 2, Room 214")
    db.add(lab)
    db.commit()
    assert client.patch(f"/api/labs/{lab.id}", headers=auth_headers(client, staff.email),
                        json={"location": "x"}).status_code == 403          # administrators only
    r = client.patch(f"/api/labs/{lab.id}", headers=auth_headers(client, admin.email),
                     json={"location": "Building S, Floor 2, Room 224"})
    assert r.status_code == 200 and r.json()["location"] == "Building S, Floor 2, Room 224"
    a = db.query(AuditLog).filter_by(action="LAB_UPDATED").one()
    assert a.detail["before"]["location"].endswith("214") and a.detail["after"]["location"].endswith("224")
