# Workflow deployment

1. In `.env` set `AUTOMATION_API_KEY` (the key n8n sends to the backend), `AUTOMATION_WEBHOOK_BASE` (`http://n8n:5678/webhook` inside the stack) and `N8N_ENCRYPTION_KEY` (random, kept secret).
2. Start the stack (`launch.ps1`); the `n8n` service starts because `AUTOMATION_WEBHOOK_BASE` is set. Open `http://127.0.0.1:5678` on the engineer PC and create the owner account.
3. Import the exports: **Workflows → Import from file** for each file in [`automation/n8n/json/`](../../automation/n8n/json/) (23 files). They are generated from one definition by `automation/n8n/gen.py` / `build_json.mjs`.
4. Create one n8n credential of type **Header Auth** for the backend key (name `X-Automation-Key`, value = `AUTOMATION_API_KEY`) and select it in each workflow's HTTP nodes.
5. Activate the workflows you want. The exports carry `active: false`; activation is a deliberate step in the n8n editor.
6. Check: `automation/n8n/test-automation.ps1` (or `test_automation.bat`) calls the backend endpoints the workflows use; the portal's automation page shows each workflow's last run.

Export back to the repository (read-only against n8n): `py automation/n8n/export_workflows.py`.
