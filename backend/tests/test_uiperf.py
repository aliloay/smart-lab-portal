"""Browser freeze reports (2026-10-22): staff browsers post long frames; only admins read them; memory only."""
from tests.conftest import auth_headers

FRAME = {"at": 1.0, "ms": 320, "blocking_ms": 270, "render_ms": 40, "style_layout_ms": 30,
         "scripts": [{"invoker": "Response.json.then", "type": "resolve-promise", "fn": "Xt", "url": "index.js",
                      "char": 10, "ms": 250, "forced_layout_ms": 0}]}


def test_staff_report_and_admin_reads(client, staff, admin):
    r = client.post("/api/uiperf/report", headers=auth_headers(client, staff.email),
                    json={"page": "/admin/equipment?tab=noncons", "dom_nodes": 5400, "canvases": 2, "frames": [FRAME]})
    assert r.status_code == 200
    assert client.get("/api/uiperf/reports", headers=auth_headers(client, staff.email)).status_code == 403
    rows = client.get("/api/uiperf/reports", headers=auth_headers(client, admin.email)).json()["reports"]
    assert rows[-1]["frames"][0]["scripts"][0]["fn"] == "Xt" and rows[-1]["user"] == staff.email


def test_students_cannot_report(client, alice):
    r = client.post("/api/uiperf/report", headers=auth_headers(client, alice.email), json={"page": "/", "frames": []})
    assert r.status_code == 403
