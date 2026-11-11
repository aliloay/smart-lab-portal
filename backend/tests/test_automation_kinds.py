"""Every notification kind the n8n workflows send must be accepted by /api/automation/notify (2026-11-11: seven
workflows sent kinds the backend rejected with 422, so their alerts were lost whenever they found something)."""
import glob
import os
import re

import pytest

from app.api.routes.automation import AUTOMATION_KINDS

WORKFLOWS = os.path.join(os.path.dirname(__file__), "..", "..", "automation", "n8n", "json")


def test_every_workflow_kind_is_accepted():
    files = glob.glob(os.path.join(WORKFLOWS, "*.json"))
    if not files:
        pytest.skip("workflow copies not mounted in this test environment")
    sent = {}
    for f in files:
        for k in re.findall(r'kind: \\"([A-Z_]+)', open(f, encoding="utf-8").read()):
            sent.setdefault(k, os.path.basename(f))
    assert sent, "no notify kinds found - the pattern no longer matches the workflow JSON"
    missing = {k: f for k, f in sent.items() if k not in AUTOMATION_KINDS}
    assert not missing, f"rejected by /automation/notify: {missing}"
