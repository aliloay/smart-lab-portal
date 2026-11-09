# Authentication and authorisation

| Caller | Credential | Checked in |
|---|---|---|
| Portal users | Bearer JWT from `POST /api/auth/login` (HS256, `SECRET_KEY`, 8 h lifetime) | `deps.get_current_user` |
| Roles | student, staff, admin; enforced per route | `deps.py` role dependencies |
| ESP32 nodes, camera and robot services, PC agents | `X-Device-Key` (per device, or `DEVICE_API_KEY`) | `deps.require_device` |
| n8n | `X-Automation-Key` = `AUTOMATION_API_KEY` (constant-time compare) | `routes/automation.py` |
| Knowledge service | `X-KB-Key` (127.0.0.1 only) | `tools/knowledge/serve.py` |

Passwords: new hashes use **Argon2id**; older bcrypt hashes still verify and are upgraded on login (`core/security.py`). Sign-up is configurable: `SIGNUP_ENABLED`, `SIGNUP_EMAIL_DOMAINS`, `SIGNUP_REQUIRES_APPROVAL`.

Seed accounts: the database seed creates demo accounts whose default passwords are published in the tests and in `briefing.py` (which warns while a default is unchanged). **Change them before any real use**; the portal's briefing lists accounts that still use a default.

Physical access credentials (time-bound QR codes, RFID cards, fingerprints, face enrolment) are separate from portal logins and managed on the enrolment pages; see [ACCESS_FLOW.md](../ACCESS_FLOW.md).
