# Security policy

## Reporting

Please report security problems privately to the repository owner (GitHub: @aliloay) rather than in a public issue.

## What is never in this repository

`.env` files, `secrets.h` (Wi-Fi and device keys), `camera*.env` (camera accounts), `tools/knowledge/config.json`, the PC install kit's enrolment key, face enrolment data and models, unblurred camera images, database dumps and the n8n data volume. All are git-ignored; templates (`*.example*`) contain placeholders only.

## Practices in the code

- Passwords hashed with Argon2id (bcrypt hashes upgraded on sign-in); JWT sessions; role checks per route.
- Device, automation and knowledge keys compared in constant time; services bound to 127.0.0.1 where they need no LAN access.
- HTTPS with a local CA (the CA private key is kept outside the nginx folder); strict security headers and a CSP that allows only the portal itself.
- Firewall rules limited to 192.168.1.0/24 and exact ports.
- No endpoint can command a robot; assistants cannot act on hardware.

## Known exposure

The demo seed passwords are published in tests and in `backend/app/services/briefing.py`, which warns while an account still uses one. Change every live account that uses a default. Git history has not been rewritten.

Details: [docs/SECURITY.md](docs/SECURITY.md), [docs/release/REPOSITORY_PRE_UPDATE_AUDIT.md](docs/release/REPOSITORY_PRE_UPDATE_AUDIT.md).
