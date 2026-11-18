# Security, RBAC and privacy audit (release candidate, 2026-11-18)

## P0: owner action (pre-existing, NOT fixed by agents; rotating credentials is not authorised)
**Two live accounts still use the PUBLISHED default passwords:** `admin@giu-uni.de` (ADMIN) and `ramy@giu-uni.de` (LAB_STAFF).
- Checked LIVE LOCAL SOFTWARE with the backend's own `briefing.default_passwords_in_use()` (hash check only, nothing printed).
- Those defaults are in public source (backend/app/services/briefing.py, PUBLISHED_DEFAULTS), so anyone on the lab LAN can sign in as admin.
- Fix, per account, run by the owner (it asks for the new password interactively):
  `docker compose exec backend python set_password.py admin@giu-uni.de`, then the same for `ramy@giu-uni.de`.

## Verified in this integration
| Area | Evidence | Class |
|---|---|---|
| Server-side role checks on every route | tests/test_authz_sweep.py (part of the 826 backend tests) | UNIT TEST |
| Student cannot read cameras / incidents | test_camera_activity, test_incidents (403) | UNIT TEST |
| Role menus, no admin page for students, expired session goes to sign-in | e2e navigation.mjs: 98 checks, 0 problems (student / staff / admin, isolated copy) | LIVE LOCAL SOFTWARE (isolated) |
| AI / MCP tools cannot act physically | MCP e2e: 9 tools all read-only, `unlock_door` refused; tool_gateway FORBIDDEN list (unlock, open_door, relay, move, jog, ...) | LIVE LOCAL SOFTWARE |
| Rejected device report pushes nothing | live_bin.mjs: HTTP 401, 0 pushes | LIVE LOCAL SOFTWARE (isolated) |
| Security headers | live nginx response: CSP default-src 'self', frame-ancestors 'none', X-Frame-Options DENY, nosniff, Vary Origin | LIVE LOCAL SOFTWARE |
| Secrets in tracked files | pattern scan (AWS/private key/GitHub/OpenAI/Slack): 0 hits; no .env, camera*.env, robot.env, secrets.h or config.json tracked; tools/ops/test_no_published_passwords.py passes | STATIC INSPECTION / UNIT TEST |
| Firmware compiled with placeholders | secrets.example.h copied in scratch copies only; real secrets.h never copied or read | STATIC INSPECTION |
| Live socket auth | one-time 30 s ticket (POST /api/auth/ws-ticket), token not in URL (since 11 Nov) | UNIT TEST (existing) |
| Device key scope | door reports only from door devices; own key speaks only for itself (SEC-01/02, existing tests) | UNIT TEST |

## Changes in this release that touch security or privacy
- **Build stamp:** the stamp file is in .dockerignore, so nothing stale or local is baked into images. The stamp holds only the commit and build time.
- **Incidents:** same staff-only dependency; `view=summary` returns fewer fields; the cursor holds no secrets (epoch microseconds + id).
- **Camera:** pose output no longer claims an OBSERVED body part (no keypoint model exists). The backend does not store the per-joint estimates. No face images or biometric material were exported in this work.
- **No weakening anywhere:** confirmed-identity vetoes only got stricter (Argon). RBAC, CORS, CSP and device keys are unchanged.

## Not done / blocked
- Live-account click-through with the real staff and admin passwords: BLOCKED. Credentials are not available to agents, and real passwords are never requested or guessed. The isolated copy with seeded random-password accounts was used instead (above).
- Device-key rotation and n8n credential checks: not performed (owner only). The n8n credential names were listed; no values were read.
- Relay ACL: Argon's fallback bind to 0.0.0.0 keeps the subnet allow-list (`allow=allow` is passed through; tools/relay tests 6/6). GIU firewall is still BLOCKED (GIU IT).
