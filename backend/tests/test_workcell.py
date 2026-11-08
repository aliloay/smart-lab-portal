"""Virtual workcell setups: roles, validation, versioned save / restore (no robot involved)."""
from app.models import WorkcellSetup
from tests.conftest import auth_headers

BOX = {"id": "b1", "label": "Fixture", "x": 0.0, "y": 0.1, "z": 0.8, "w": 0.2, "d": 0.2, "h": 0.15}
TABLE = {"present": True, "x0": -0.514, "x1": 0.186, "y0": -0.63, "y1": 0.77, "height": 0.71}


def test_admin_saves_and_everyone_staff_restores_newest(client, db, admin, staff):
    ha, hs = auth_headers(client, admin.email), auth_headers(client, staff.email)
    assert client.put("/api/workcell/UR5E/pick test", headers=ha, json={"table": TABLE, "obstacles": [BOX]}).status_code == 200
    moved = {**BOX, "x": 0.1}
    client.put("/api/workcell/UR5E/pick test", headers=ha, json={"table": TABLE, "obstacles": [moved]})
    rows = client.get("/api/workcell/UR5E", headers=hs).json()
    assert len(rows) == 1 and rows[0]["data"]["obstacles"][0]["x"] == 0.1
    assert rows[0]["data"]["obstacles"][0]["source"] == "MANUAL"
    assert db.query(WorkcellSetup).count() == 2                    # the older version is kept


def test_staff_cannot_save_students_cannot_read(client, staff, alice):
    assert client.put("/api/workcell/UR5E/x", headers=auth_headers(client, staff.email), json={}).status_code == 403
    assert client.get("/api/workcell/UR5E", headers=auth_headers(client, alice.email)).status_code == 403


def test_bad_values_are_refused(client, admin):
    h = auth_headers(client, admin.email)
    assert client.put("/api/workcell/UR5E/x", headers=h, json={"obstacles": [{**BOX, "w": -1}]}).status_code == 422
    assert client.put("/api/workcell/UR5E/x", headers=h, json={"obstacles": [{**BOX, "source": "VERIFIED"}]}).status_code == 422
    assert client.put("/api/workcell/KUKA/x", headers=h, json={}).status_code == 422
    assert client.put("/api/workcell/UR5E/x", headers=h, json={"obstacles": [BOX] * 51}).status_code == 422


def test_robots_are_separate(client, admin, staff):
    ha = auth_headers(client, admin.email)
    client.put("/api/workcell/FANUC/a", headers=ha, json={"obstacles": [BOX]})
    assert client.get("/api/workcell/UR5E", headers=auth_headers(client, staff.email)).json() == []
