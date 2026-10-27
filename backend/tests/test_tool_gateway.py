"""Read-only lab tool gateway (services/tool_gateway.py, /api/ai/tools): typed schemas, validation, role checks,
timeouts and audit; no physical action can be reached."""
import time

import pytest

from app.models import AuditLog
from app.services import tool_gateway
from tests.conftest import auth_headers


def test_schemas_are_typed_and_bounded():
    s = {t["name"]: t for t in tool_gateway.schemas()}
    assert "get_environment" in s and all(t["read_only"] for t in s.values())
    days = s["get_operations_overview"]["input_schema"]["properties"]["days"]
    assert days["type"] == "integer" and (days["minimum"], days["maximum"]) == (1, 365)
    assert s["get_anomalies"]["input_schema"]["properties"]["hours"]["maximum"] == 336
    assert all(t["input_schema"]["additionalProperties"] is False for t in s.values())


@pytest.mark.parametrize("name,args,msg", [
    ("unlock_door", {}, "not allowed"), ("move_robot", {"joint": 1}, "not allowed"), ("set_relay", {}, "not allowed"),
    ("get_report", {}, "missing required argument: period"), ("get_report", {"period": "yearly"}, "one of"),
    ("get_trends", {"weeks": 999}, "between 2 and 52"), ("get_trends", {"weeks": "many"}, "integer"),
    ("list_labs", {"sql": "drop table"}, "unknown argument"),
])
def test_bad_calls_are_refused(name, args, msg):
    with pytest.raises(tool_gateway.ToolRefused, match=msg):
        tool_gateway.validate(name, args)


def test_lenient_mode_clamps_for_the_portal_model():
    assert tool_gateway.validate("get_trends", {"weeks": 999, "extra": 1}, strict=False) == {"weeks": 52}


def test_api_is_staff_only_audited_and_works(client, db, staff, alice, lab):
    assert client.get("/api/ai/tools", headers=auth_headers(client, alice.email)).status_code == 403
    h = auth_headers(client, staff.email)
    assert len(client.get("/api/ai/tools", headers=h).json()["tools"]) >= 9
    r = client.post("/api/ai/tools/list_labs", json={"arguments": {}, "via": "mcp"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "ok" and "LAB_TEST" in r.json()["result"]
    assert client.post("/api/ai/tools/unlock_door", json={}, headers=h).status_code == 422
    rows = db.query(AuditLog).filter_by(action="LAB_TOOL_CALL").all()
    assert {(a.entity_id, a.detail["status"]) for a in rows} == {("list_labs", "ok"), ("unlock_door", "refused")}
    assert any(a.detail["via"] == "mcp" for a in rows)


def test_a_slow_tool_times_out_instead_of_hanging(db, staff, monkeypatch):
    monkeypatch.setattr(tool_gateway, "_run_isolated", lambda name, args: (time.sleep(2), ("{}", False))[1])
    r = tool_gateway.call(db, staff, "list_labs", {}, timeout_s=0.3)
    assert r["status"] == "timeout" and r["ms"] < 1500
