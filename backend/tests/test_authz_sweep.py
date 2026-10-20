"""Authorization sweep (2026-10-17): every API route is called WITHOUT credentials; anything that answers
2xx must be on the explicit public list below. A new endpoint that forgets its auth dependency fails here."""
import re

from app.main import app

# Public on purpose: health, sign-in / sign-up / password flows, public lab list for the welcome
# page, and the door/booking QR check that the kiosk uses with its own token in the request.
PUBLIC = {
    ("GET", "/api/health"), ("POST", "/api/auth/login"), ("POST", "/api/auth/register"), ("GET", "/api/auth/signup-config"),
    ("POST", "/api/auth/forgot-password"), ("POST", "/api/auth/reset-password"), ("GET", "/api/public/labs"),
    ("GET", "/api/labs/public"),
}


def _routes():
    # app.routes holds the mounted API sub-app; the OpenAPI schema lists every real path.
    for path, ops in app.openapi()["paths"].items():
        for m in ops:
            if m.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                yield m.upper(), path


def test_every_protected_route_refuses_anonymous_callers(client):
    leaks = []
    for method, path in _routes():
        url = re.sub(r"\{[^}]+\}", "1", path)
        r = client.request(method, url, json={} if method in ("POST", "PUT", "PATCH") else None)
        if 200 <= r.status_code < 300 and (method, path) not in PUBLIC:
            leaks.append(f"{method} {path} -> {r.status_code}")
    assert not leaks, "Answered without credentials:\n" + "\n".join(leaks)


def test_students_cannot_reach_staff_only_admin_surfaces(client, alice):
    from tests.conftest import auth_headers
    h = auth_headers(client, alice.email)
    for method, url in [("GET", "/api/system/health"), ("GET", "/api/incidents"), ("GET", "/api/reports-center/alerts"),
                        ("GET", "/api/analytics/anomalies"), ("POST", "/api/equipment/broadcast/start"),
                        ("POST", "/api/robots/1/control/stop"), ("POST", "/api/equipment/1/action"),
                        ("GET", "/api/equipment/1/screen.jpg"), ("POST", "/api/incidents/1/actions")]:
        r = client.request(method, url, headers=h, json={"source": "browser", "action": "lock", "command_id": "abcdefgh1"})
        assert r.status_code in (401, 403), f"{method} {url} -> {r.status_code}"
