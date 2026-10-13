"""Project knowledge proxy: staff/admin only, clear errors when the local service is missing."""
from app.core.config import settings
from tests.conftest import auth_headers


def test_students_cannot_use_project_knowledge(client, alice):
    h = auth_headers(client, alice.email)
    assert client.get("/api/knowledge/status", headers=h).status_code == 403
    assert client.post("/api/knowledge/ask", headers=h, json={"question": "what is the door"}).status_code == 403


def test_missing_key_is_a_clear_503(client, staff, monkeypatch):
    monkeypatch.setattr(settings, "KB_SERVICE_KEY", "")
    r = client.post("/api/knowledge/ask", headers=auth_headers(client, staff.email), json={"question": "door"})
    assert r.status_code == 503 and "not set up" in r.json()["detail"]


def test_service_down_is_reported_not_crashed(client, staff, monkeypatch):
    monkeypatch.setattr(settings, "KB_SERVICE_KEY", "x")
    monkeypatch.setattr(settings, "KB_SERVICE_URL", "http://127.0.0.1:9")
    h = auth_headers(client, staff.email)
    assert client.get("/api/knowledge/status", headers=h).json()["ok"] is False
    r = client.post("/api/knowledge/ask", headers=h, json={"question": "door"})
    assert r.status_code == 200 and '"status": "failed"' in r.text and "not running" in r.text


def test_bad_route_rejected(client, staff, monkeypatch):
    monkeypatch.setattr(settings, "KB_SERVICE_KEY", "x")
    r = client.post("/api/knowledge/ask", headers=auth_headers(client, staff.email),
                    json={"question": "door", "route": "shell"})
    assert r.status_code == 422
