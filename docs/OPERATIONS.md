# Smart Lab - operations guide

The one place to start when something has to be started, checked, deployed, recovered or restored.
Details live in the linked documents; this guide says what to do and how to tell that it worked.
Last revised 2026-10-18. Labels: **routine** (any staff member, nothing physical changes) and
**privileged** (administrator / qualified operator / IT approval - written before the step).

## 1. What runs where

| Part | Where | Started by | Health check |
|---|---|---|---|
| PostgreSQL `smartlab` | Docker `db` | Docker (restart: unless-stopped) | `docker compose ps db` (healthy) |
| Backend API (FastAPI) | Docker `backend`, port 8000 behind nginx | Docker | `curl http://127.0.0.1/api/health` -> `status ok`, `version`, `db_time` |
| Portal web app (nginx) | Docker `frontend`, :80 / :443 (local CA) | Docker | http://192.168.1.200 |
| n8n (26 workflows, all active) | Docker `n8n` (profile automation) | Docker | Portal > Reliability > Dependencies |
| Backups (every 6 h, pg_dump + pg_restore --list check) | Docker `backup` -> `./backups` | Docker | `backups/backup_status.json`; Reliability > Backups |
| Security camera 1 / 2 services | native Python 3.14, :5100 / :5101 (127.0.0.1) | `launch.bat` / `start_security_vision.bat [camera2.env]` | `curl http://127.0.0.1:5100/health` (`stream.state`) |
| Face server | native, :5000 | `launch.bat` | Reliability > Dependencies |
| Ollama (portal AI, CPU, 4 threads, one answer at a time) | native, :11434 | Ollama app | `curl http://127.0.0.1:11434/api/version` |
| Knowledge service | native, :5199 (key) | `launch.bat` (`py tools/knowledge/serve.py`) | Reliability > Dependencies |
| Robot collectors (UR5e RTDE / FANUC HTTP, read-only) | native | `tools/robot_monitor/start_*_monitor.bat` | Robots page (telemetry age) |
| PC agent | each approved PC (pilot: this laptop) | `tools/pc_agent/start_pc_agent.bat` | Lab Equipment (agent version, clock offset) |
| ESP32 nodes (door master, bins, environment, ESP32-CAM) | Wi-Fi on Smart_Lab | power | System Devices; Reliability > Dependencies |

Dependencies (who needs whom), live states and a sandboxed what-if: **Portal > Reliability > Dependencies**.

## 2. Start-up order (routine)
1. Laptop on the Smart_Lab cable (192.168.1.200), charger in, sleep off; Settings > Time > **Sync now**.
2. Docker Desktop. The containers come back by themselves (restart policy); check `docker compose ps`.
3. `launch.bat` - face server, knowledge service, Ollama, camera services (camera 2 if `camera2.env` exists).
   Camera windows must show `YOLO26 on directml-gpu1`, `re-id on directml-gpu1`, `process priority: above normal`.
4. Robot collectors if the robots are cabled. PC agent on approved PCs.
5. Verify: `py -I tools/evidence/clock_check.py`, then Portal > Reliability > Briefing.
Shut-down: close the camera / collector windows, then `stop_all.bat` (`docker compose stop`, data kept).

## 3. Deploying portal changes (routine for tested code)
`py -I tools/deploy/deploy.py` (set `SMARTLAB_PASSWORD` in the shell first; never in a file).
It type-checks, runs the quick backend tests, refuses a database behind the migration head (unless
`--allow-migration`, which first runs the isolated restore-and-migrate drill), tags the running images
`:previous`, stamps the version, rebuilds ONLY backend + frontend, waits for readiness, runs read-only smoke
tests, and **rolls back to `:previous`** if any of them fails. Every deploy is appended to
`backups/deploy_history.jsonl`. Check: `/api/health` shows the new `version.id`.
Migrations are additive and backward compatible; the database is never rolled back.

## 4. Recovery (routine unless marked)
| Symptom | First check | Fix |
|---|---|---|
| Portal does not load | `docker compose ps` | `docker compose --profile automation up -d` |
| One device "offline" | Reliability > Incidents > Investigate (shared outage? portal gap?) | power / Wi-Fi of that node on site |
| Several devices offline in the same minute | supply / master switch / router | restore power or network, then watch them report |
| Camera "no picture" incident | `:5100/health` -> `stream.state` RECONNECTING / OFFLINE | camera power / RTSP address; the service retries with backoff (<= 30 s) |
| Camera window closed | - | `start_security_vision.bat [camera2.env]` (**privileged**: interrupts monitoring briefly) |
| AI "busy" | another answer is being generated | ask again; status questions answer instantly |
| Backup FAILED | `docker compose logs backup` | disk space / DB health; it retries in 5 min |
| Robot STOP latched (also after a restart) | the arm is still per feedback | administrator: Recover after STOP (**privileged**; restarts nothing) |

Automatic recovery is limited to Docker's restart policy and the camera reconnect loop. What may run
automatically is in Reliability > Action policy; robot motion, door logic, firmware and safety settings
are never automatic.

## 5. Backup and restore
* Backups: every 6 h, kept indefinitely, each verified with `pg_restore --list`.
* **Restore drill** (routine, production only read): `py -I tools/evidence/restore_drill.py [--migrate-test]` -
  restores the newest dump into a NEW database `smartlab_drill_<time>`, compares every table, records the
  result (Reliability > Backups). Measured 2026-10-18: dump 2 s, restore 5.4-5.7 s, 42 tables, ~49-56 k rows.
  Drill databases are disposable copies (the owner may drop them); `smartlab_restore_drill` is kept.
* **Real restore after a disaster (privileged, owner)**: stop backend + frontend, keep the broken database
  (rename it, never drop it), create a new `smartlab`, `pg_restore --no-owner -d smartlab <dump>`, start the
  backend (it checks the migration head), verify with the evidence run.

## 6. Configuration drift
Reliability > Drift compares the running configuration with `backend/app/config_baseline.json`
(versioned, no secrets). Secrets are only checked for being set and not equal to a published default.
Nothing is corrected automatically. Accept a deviation (administrator) with a reason and an optional
expiry - it stays visible; to change the baseline, edit the file together with the approval it records.

## 7. Alerts and incidents
One incident per continuing condition (fingerprint: device | lab | title, or a source key): repeats while
open are counted (x N, last seen); a return within 30 min of resolution reopens it; the original events stay
in their own tables. Safety alarms (flame, smoke, forced entry) still notify on every occurrence.
Lifecycle OPEN -> ACKNOWLEDGED -> INVESTIGATING -> MITIGATED -> RESOLVED (reopen allowed); acknowledging never
changes a device's own state. Escalation (configurable `INCIDENT_ESCALATE_*`): unacknowledged CRITICAL 15 min /
WARNING 4 h, 20 repeats, 3 reopenings. Investigate: Incidents > an incident > Investigate (ranked
explanations, correlation not proof). Quality: Reliability > Alert quality.

## 8. Performance
Reliability > Performance: per-route p50 / p95 / p99 since the backend started, regressions (last 5 min vs the
hour before, >= 20 samples, cooldown), objectives (95 % of reads < 300 ms; 99.5 % without server errors).
Measured 2026-10-18 (laptop, cameras running): single user p50 36 ms / p95 99 ms; 10 users + 2 live viewers
p50 121 / p95 376 ms. Limit: one backend process (~20 requests/s); many live-view viewers compete with the API.
Resource rules: camera services run above normal priority; the AI uses 4 threads and one answer at a time.

## 9. Physical validation and approvals (never done by software)
Cameras (mounting, calibration, identity scenarios), robots (commissioning, sign-off - docs/ROBOT_CONTROL.md),
ESP32 nodes (power, fuses, sensors - docs/BRINGUP_LOG.md), lab PCs (IT approval - tools/pc_agent/README.md).
Day plan: docs/LAB_GO_NOGO_2026-10-18.md.

## 10. Evidence
`py -I tools/evidence/run_evidence.py --runs 20` (credentials from the environment) -> docs/reports/evidence_*.md
with PASS / FAIL / NOT_AVAILABLE / SIMULATION / PHYSICAL_VALIDATION_REQUIRED / BLOCKED per check.
Identity regression (simulated): `py -3.14 tools/security_vision/scenario_bench.py`. Clocks:
`py -I tools/evidence/clock_check.py`.
