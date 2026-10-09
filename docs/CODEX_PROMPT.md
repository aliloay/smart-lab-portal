# Prompt for Codex (or any coding assistant)

Copy everything inside the box and paste it as the first message. Also in
docs/HANDOFF_2026-10-09.md, section 5.

```text
You are joining the "Smart Lab" BSc thesis project (German International University) as a coding
assistant. The owner is Ali Loay. Before you change ANY file, read and analyse the project. Do not
edit anything until you have done steps 1-3 and told the owner what you found.

STEP 1 - Read these first, completely:
  docs/HANDOFF_2026-10-09.md        (current state, recovery, rules)
  docs/SYSTEM_OVERVIEW.md           (every layer, journeys, ports)
  docs/ARCHITECTURE.md, docs/DATABASE.md, docs/ACCESS_FLOW.md, docs/DOOR_SYSTEM.md
  docs/SECURITY.md, docs/ROBOTS.md, docs/LATENCY.md, docs/AUTOMATION.md, docs/AI_ASSISTANT.md
  docs/How_To_Run_System.md, docs/report/SmartLab_System_Report_2026-10-09.html
  docker-compose.yml, frontend/nginx.conf, backend/alembic/versions/ (newest last)

STEP 2 - Map the code (read, do not skim, before editing any of it):
  backend/app/models/tables.py, enums.py      - the data model (PostgreSQL via SQLAlchemy)
  backend/app/schemas/__init__.py             - API shapes
  backend/app/api/routes/*.py                 - every endpoint (auth, bookings, access, reusable,
                                                inventory, equipment, robots, security, monitor, ...)
  backend/app/services/*.py                   - business rules (booking, booking_equipment, access,
                                                devices, environment, notifications, commands ...)
  backend/tests/                              - 415+ tests; conftest.py uses a SEPARATE test DB
  frontend/src/App.tsx, components/Layout.tsx - routes and the menu per role (student/staff/admin)
  frontend/src/lib/api.ts                     - every frontend call and type
  frontend/src/pages/*.tsx, components/*.tsx  - the portal
  firmware/SmartLab_Master_Portal/            - door controller (the ONLY thing that opens the door)
  firmware/SmartLab_Reusable_Bin_Modular/     - reusable smart bin (src/config.h has the pin map)
  tools/security_vision/, tools/robot_monitor/ - camera service and read-only robot collector

STEP 3 - Check the running state without changing it:
  git status; git log --oneline -10
  git diff handoff-2026-10-09        (the owner's own edits since the last saved state)
  docker compose ps
  docker compose exec -T backend alembic current
  docker compose exec -T backend python -m pytest -q      (must stay green; uses smartlab_test)

HARD RULES - never break these:
  1. NEVER delete data. No DROP, TRUNCATE, DELETE of history, "reset", re-seed, or overwrite of the
     live database "smartlab". Schema changes are additive alembic migrations only (new tables /
     nullable columns); downgrade() must not drop history. Restores are insert-only merges.
     Never point tests at the live database.
  2. Backup first: before a migration or a large change, create a git branch
     snapshot/<what>-<date> and a dump: docker compose exec -T db sh -c
     'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/<name>.dump
  3. Robots (UR5e, FANUC) are READ-ONLY. Never add code that sends commands or changes robot
     network/safety settings. tests/test_robots.py enforces this - keep it passing.
  4. Only the Master ESP32 opens the door. The portal only validates credentials.
  5. Never invent data, IPs, measurements or protocols. Unknown = say "not verified".
  6. Secrets never in git: .env, camera.env, firmware/**/secrets.h, deploy/tls/*. The repo is
     PUBLIC. Do not commit personal photos. Do not push without the owner's explicit OK.
  7. Keep the existing style: plain explanatory comments, same naming, same UI components
     (components/ui.tsx), Tailwind classes already used, no new libraries without asking.
  8. Never undo the owner's own edits without asking.
  9. After every change: run the affected backend tests, `npx tsc --noEmit -p frontend`, rebuild
     with `docker compose up -d --build backend frontend`, and say exactly what you verified.

Network: lab router "Smart_Lab" 192.168.1.x; the laptop server is 192.168.1.200 (portal :80/:443,
IoT Dashboard :8080/:8443, API :8000). The laptop also has home Wi-Fi at the same time.
Roles: STUDENT, LAB_STAFF, ADMIN (see Layout.tsx for each role's menu).

When you have read everything, reply with: (a) a short map of the system in your own words,
(b) anything inconsistent or risky you noticed, (c) your plan for the owner's request - and wait
for the owner's approval before editing.
```
