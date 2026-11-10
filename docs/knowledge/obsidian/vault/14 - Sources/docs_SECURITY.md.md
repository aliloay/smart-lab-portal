---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/SECURITY.md"
source_hash: "4c1ed11f502c9dff921f6b597304c4d22fdaa8885a75e410bf9a18a065d63d11"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/SECURITY.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docker-compose.yml]] - mentioned by docs
- [[docs_CODEX_PROMPT.md]] - mentioned by docs
- [[docs_HANDOFF_2026-10-09.md]] - mentioned by docs
- [[docs_MONDAY_LAB_2026-10-12.md]] - mentioned by docs
- [[docs_SCAN_THE_LAB.md]] - mentioned by docs

# Security (state on 2026-10-08)

## In place, and tested (backend/tests/test_security_hardening.py)

| Area | What |
|---|---|
| Passwords | New passwords need 10+ characters and 3 of the 4 character kinds (lowercase, uppercase, digit, symbol). Common passwords and passwords containing the person's own name or email are refused (`app/core/password_policy.py`). Existing passwords keep working until they are next changed. |
| Hashing | Argon2id (64 MiB, t=3, p=4) for new hashes. Old bcrypt hashes are re-hashed to Argon2id at the next sign-in. A sign-in for an unknown account does the same work, so timing does not reveal which accounts exist. |
| Sign-in throttling | 8 failures per account, or 30 per address, within 15 min → 429 with Retry-After. Every failed sign-in is in the audit log (`LOGIN_FAILED`), never with the password. |
| Errors | An unexpected error returns `{"detail": "An unexpected error occurred.", "error_id"}`. The full traceback goes only to the server log (repeats are logged in full once a minute). Every response carries an `X-Request-ID`. |
| API docs | `/api/docs` and `/api/openapi.json` are off unless `EXPOSE_API_DOCS=true` (development only). |
| CORS | An explicit list of allowed origins, methods and headers. |
| SQL | ORM and parameterised queries only (a repository scan on 2026-10-08 found no SQL built from strings). |
| Headers (nginx) | CSP (`script-src 'self'`, no external origins, no `unsafe-eval`), X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy, COOP, HSTS on HTTPS only, nginx version hidden, hidden files (`.env`, `.git`) → 404. The CSP allows inline *styles* because React and charts set style attributes; scripts stay strict. |
| Fonts | Bundled with the app: no request leaves the lab network. |
| Secrets | `.env`, `camera.env`, every `secrets.h` and `deploy/tls/*` (keys) are git-ignored. The whole git history was scanned on 2026-10-08: no secret was ever committed. |
| Dependencies | `pip-audit` was clean after the 2026-10-08 upgrades (FastAPI 0.143 / Starlette 1.7, Pillow 12.3, python-multipart 0.0.32, python-jose 3.5) except one `ecdsa` notice with no fix; it does not apply, because tokens are HS256. `npm audit`: 2 moderate React Router notices; they need server rendering or navigation driven by an outside URL, and the portal has neither. The fix needs the v7 major upgrade (planned). |
| Robots | No endpoint can send anything to a robot (enforced by a test). |

## HTTPS on the lab network

There is no internet in the lab, so a local certificate authority (CA) is used:

    py tools/tls/make_local_ca.py --ip 192.168.1.200 --ip 192.168.1.210
    docker compose up -d frontend          (HTTPS turns on by itself when the certificate exists)

Then **trust `deploy/tls/smartlab-ca.crt` once on each device**:
- **Windows:** double-click it → Install Certificate → Local Machine → "Trusted Root Certification Authorities".
- **Android:** Settings → Security → Encryption & credentials → Install a certificate → CA certificate.
- **iPhone:** AirDrop or mail it to the phone → install the profile → Settings → General → About → Certificate Trust Settings → turn it on.

The portal is at `https://<laptop>/` and the Command Center at `https://<laptop>:8443/`.
Plain HTTP on port 80 still works. It is NOT redirected yet, so that no device
breaks before it trusts the CA. The door tablet and the ESP32 nodes talk to the
backend on `:8000` and are not affected.

The CA's private key (`deploy/tls-ca/smartlab-ca.key`, git-ignored) never leaves the laptop.
Anyone holding it can mint certificates the lab devices trust. **Since 2026-10-26 it is no longer in
`deploy/tls`**: that folder is mounted into the nginx container, which needs only `server.crt` / `server.key`
(and serves the public `smartlab-ca.crt` at `/smartlab-ca.crt` for the Phone setup page). `make_local_ca.py`
moves an old key out by itself and reads it from `deploy/tls-ca/`.

Phones: the portal's **Phone setup** page (`/phone-setup`, staff) checks the secure context, offers the CA
download with the Android / iPhone trust steps and shows a QR that opens `https://<laptop>/scan` on the phone.
Camera and microphone are allowed for this site only (`Permissions-Policy: camera=(self), microphone=(self)`).

## Open items

- Redirect HTTP → HTTPS once every lab device trusts the CA.
- React Router v7 upgrade (the 2 moderate notices).
- The backend's port 8000 is open on the LAN because the ESP32 nodes post to
  it. Moving the nodes to HTTPS through nginx needs a firmware change.
- The local PostgreSQL 18 Windows service (development database) listens on
  all interfaces. Windows Firewall blocks it (no inbound rule). Set
  `listen_addresses = 'localhost'` in its `postgresql.conf` if it is kept.

