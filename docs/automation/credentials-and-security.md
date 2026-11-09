# n8n credentials and security

- The exports in `automation/n8n/json/` contain **no credentials**: every request targets the internal service `http://backend:8000/api/automation/...`, and authentication is a credential reference resolved inside n8n (checked on 9 Nov 2026: no Authorization or key literals in the files).
- Never commit the n8n data volume, its `database.sqlite`, the credentials export or `N8N_ENCRYPTION_KEY`.
- n8n is bound to `127.0.0.1:5678`: it is not reachable from the lab network.
- The backend accepts automation calls only with `AUTOMATION_API_KEY`; the notify endpoint writes portal notifications and sends e-mail only when SMTP is configured.
- Workflows work without internet. E-mail delivery and any external service would need it; none is required by the exported workflows.
