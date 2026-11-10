# GitHub final release report (10 November 2026)

Branch `docs/include-everything`, to be merged into the protected `main` through a pull request. No force push, no history rewrite.

## What this release contains

- Documentation for every subsystem: hardware nodes, computer vision, digital twins, AR, AI assistants, knowledge base, n8n automation, backend, portal, network and offline operation.
- Root pages: project overview, status, feature matrix, integration matrix, architecture decisions (15), known issues.
- Defense pages: `docs/defense/DEFENSE_BRIEF.md` and `docs/defense/OPTIMIZATION_AND_REMAINING_WORK.md`.
- A copy of the Obsidian vault (322 notes, without chat transcripts), thesis figures, reports, CAD outputs, portal captures and the lab-PC kit scripts.
- Launcher fixes found by the clean-clone test (below).

## Clean-clone launch test

A fresh `git clone` in a separate folder, a new `.env` from `.env.example` with test ports, its own Docker project name and therefore empty volumes. Run by the owner with `.\launch.ps1 -Build` on the Dell G3 (Windows 11, Docker Desktop on WSL 2).

| Check | Result |
|---|---|
| Images build from scratch | Passed: about 16 minutes on the first build (938 s of it `pip install`), 3.5 minutes from cache |
| Database created and migrated on an empty volume | Passed: 42 tables plus `alembic_version`, seed users present |
| All five services healthy (db, backend, frontend, backup, n8n) | Passed |
| API health | `200` on `/api/health` |
| n8n | `200` on `/healthz` |
| Portal opens in a browser | Passed after the fix below: `200` on `/` and `/login`; Command Center `200` on `/command` |
| With a certificate mounted | Passed: HTTP redirects to HTTPS (`301`), HTTPS answers `200`, also after a container restart |

### Defects the test found, and their fixes

1. **n8n was not started by `launch.ps1`** although `.env` enabled automation. Fixed: the launcher adds the `automation` profile (commit `f977db3`).
2. **Host ports were fixed in `docker-compose.yml`.** They can now be overridden from `.env`; the defaults are unchanged (`f977db3`).
3. **A fresh installation could not open the portal.** Without a certificate HTTPS is off, but HTTP still redirected every page to HTTPS. Fixed in `frontend/40-smartlab-tls.sh`: the redirect is switched off while no certificate is mounted, and restored when one is. `launch.ps1` now prints the address that actually works.

### Limits of the test

- One PC, one run of each path. Not repeated on a second machine.
- The first attempt ran under the live project name and failed on the live volumes' credentials. The live data was checked afterwards (read-only) and was unchanged. The attempt is the reason for the `COMPOSE_PROJECT_NAME` note in `KNOWN_ISSUES.md`.
- With non-default host ports, two redirects point at the default ports (`KNOWN_ISSUES.md`).
- `launch.ps1` covers the container stack. The native services of the full lab start (`launch.bat`: cameras, face server, Ollama, voice, robot monitors) need the lab hardware and their private configuration files and were not part of this test.

## What is deliberately not in the repository

`.env`, `camera.env`, `robot.env` and every device key; Wi-Fi and camera passwords; database dumps and records; raw lab captures and recordings that show people; training datasets (about 1.8 GB); nine chat transcripts from the vault; the certificate authority key.

## Open items

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) and [docs/defense/OPTIMIZATION_AND_REMAINING_WORK.md](docs/defense/OPTIMIZATION_AND_REMAINING_WORK.md). The owner still has to change the public seed passwords on live accounts and choose a licence.
