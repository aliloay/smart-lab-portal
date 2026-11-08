---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/SECURITY_FINDINGS_2026-10-18.md"
source_hash: "0a325fb43927a63162dbbf8d6607830d285f965ecad12836ca6e1d2fc855175a"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/SECURITY_FINDINGS_2026-10-18.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_LAB_GO_NOGO_2026-10-18.md]] - mentioned by docs
- [[docs_PROGRESS_CHECKPOINT.md]] - mentioned by docs
- [[docs_DEMO.md]] - mentioned by docs
- [[docs_How_To_Run_System.md]] - mentioned by docs

# Security findings - 2026-10-18

Scope: what was checked tonight on the running system and in the repository. This is **not** an exhaustive
audit or a penetration test.

Checked:
* response headers (curl);
* sign-in and abuse limits (code);
* token lifetime and CORS (running configuration);
* secrets: present / not a published default (drift check; values never printed);
* authorisation on every API route (`tests/test_authz_sweep.py`, all routes via OpenAPI);
* frontend production dependencies (`npm audit --omit=dev`);
* backend package versions (pip list);
* new endpoints (reliability, search, incidents quality).

## Confirmed - needs the owner (credentials change)
| # | Severity | Finding | Evidence | Remediation |
|---|---|---|---|---|
| S1 | **High** | The live **administrator account still uses the published seed password**. The same password is printed in `backend/seed.py`, `docs/DEMO.md`, `docs/How_To_Run_System.md` and several e2e scripts, and the repository is public. | e2e sign-in with the seed password succeeds | Change the admin password in the portal (Profile) and the seed-account passwords of staff / students that are real. Then set `SMARTLAB_PASSWORD` / `E2E_PASSWORD` only in the shell for tests. Rotating is the owner's decision; it was not done automatically. |
| S2 | Medium | The portal is also served over plain HTTP on the lab LAN, so sign-in passwords can be read on that network. | :80 serves the app | HTTPS exists (:443, local CA `deploy/tls/smartlab-ca.crt`). After the CA is imported on the lab browsers, redirect :80 to :443 (an nginx change, owner's decision). |

## Fixed tonight
| # | Finding | Fix |
|---|---|---|
| F1 | New test / evidence scripts embedded the admin password (copied pattern). | `frontend/e2e/robot_readiness.mjs`, `frontend/e2e/reliability.mjs`, `tools/evidence/run_evidence.py`, `tools/deploy/deploy.py` read credentials from the environment only. Older e2e files still have a fallback default - covered by S1. |
| F2 | A resolved camera alert made the next event of the same box fail (unique key, HTTP 500, event and snapshot **lost**) - a data-integrity defect. | Incidents now group by fingerprint (`app/services/alert_grouping.py`); regression test `test_resolved_camera_alert_does_not_break_the_next_event`. |
| F3 | Stale "offline" incidents stayed open while the device reported again (wrong health picture). | Cleared on the next liveness refresh, verified by the device's own fresh report. |
| F4 | Request-timing keys could grow without bound (random URLs from a scanner). | Unmatched routes share one key; at most 500 keys. |
| F5 | The robot STOP latch was cleared by a backend restart (an implicit recovery nobody approved). | Rebuilt from the audit log at start-up; test plus a live restart check (latched after 26.6 s restart). |

## Verified as in place
* **Headers:** CSP (`default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`), nosniff, X-Frame-Options DENY, Referrer-Policy, Permissions-Policy, COOP, HSTS on HTTPS. `server_tokens off`.
* **Sign-in:**
  * lockout after repeated failures (HTTP 429);
  * sign-up limit per network;
  * emergency-password lockout;
  * hourly AI question limit for students.
* **Access tokens:** 8 h lifetime. CORS limited to the dev origins; the portal itself is same-origin behind nginx.
* **Production refuses to start** with the default `SECRET_KEY` / `DEVICE_API_KEY`. The drift check confirms neither, nor the database password, is a published default.
* **Device endpoints:** device keys; camera, knowledge, face and Ollama services are bound to 127.0.0.1.
* **Authorisation:** every API route needs authentication. Student, staff and admin rules are checked by the sweep test and per-feature tests (new reliability, search and incident-quality routes: staff only; drift acceptance and performance baseline: admin only).
* **Audit:** robot control, STOP, recovery, PC screen views, broadcasts, incident actions, drift acceptance, policy evaluations and diagnostics are written to `audit_logs` (insert-only from the application).
* **Frontend dependencies:** `npm audit --omit=dev`: **0** known vulnerabilities (any severity), 2026-10-18.
* **Backend packages:**
  * FastAPI 0.143.0, Starlette 1.7.0, SQLAlchemy 2.0.36, pydantic 2.10.4, httpx 0.28.1, psycopg 3.2.3;
  * python-jose 3.5.0 (after the 2024 fixes);
  * passlib 1.7.4 is unmaintained - informational.
  * `pip-audit` is not installed: installing it needs the owner's approval, so the Python CVE scan is **NOT AVAILABLE**.

## Accepted risks (documented)
| Risk | Why accepted |
|---|---|
| A token can't be revoked server-side before it expires (8 h). | Small closed user group; sign-out clears the browser. Shorten `ACCESS_TOKEN_EXPIRE_MINUTES` if needed. |
| One backend process holds the robot-control, screen-sharing and long-poll state in memory. | Simpler and consistent. The STOP latch now survives restarts through the audit log. |

## Needs administrative or IT approval
* PC agents on student PCs: university IT approval (visible preview, visible lock only; no keylogging, no hidden capture, no remote shell).
* Browser tab titles / URLs: only through an IT-managed browser extension or enterprise policy. Not implemented.

