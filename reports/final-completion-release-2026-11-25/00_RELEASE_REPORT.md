# Release 11003b0, 25 Nov 2026

One report with the required sections instead of 13 files. Findings: `../claude-gemini-independent-audit-remediation-2026-11-24/`. Navigation: `../complete-portal-navigation-reorganization-2026-11-24/`.

## Answers
1. **Release candidate ready?** Yes for the portal. The camera, robot and relay fixes are tested offline and need a live run.
2. **Verified live:** backend, frontend, database, build identity, migrations (head a7b3c9d1e240), data counts unchanged, page addresses.
3. **Not verified live:** cameras, robots, relay, PC agents, ESP32, AR with a phone, n8n runs, new pages by clicking.
4. **Deployed?** Yes, on this laptop. Nothing was pushed.
5. **Build:** 11003b0-20261125014121 (backend and frontend the same).
6. **Failed:** nothing in the test suites. First image of one sample file was wrong in my own test data and was repeated.
7. **At the lab (owner says no more visits):** nothing required for the portal. Relay on the engineer PC stays the old one until somebody installs the new kit.
8. **Largest remaining risk:** identity behaviour with real people after the new rules has not been seen live.

## Tests on the merged code
| Suite | Result |
|---|---|
| Backend (throw-away database) | 1052 passed, 3 skipped |
| Cameras | 458 passed, 1 skipped |
| Simulated identity scenarios | 17: 0 false names, 0 name switches |
| Knowledge | 114 passed |
| Robots | 50 passed, 1 skipped |
| PC agent | 44 passed |
| Ops scripts | 32 passed |
| Relay | 9 passed |
| Voice | 6 passed |
| OPC UA | 3 passed |
| Frontend | TypeScript 0 errors, 27 unit, 9 search, build |
| Browser (test copy) | 33 of 33 interactions; 342 pages, 0 blank, 0 console errors, 0 wider than the screen |
| npm audit (production) | 0 vulnerabilities |
Not run: face server, firmware compile, Python dependency audit, load test, n8n execution, AI 50 questions.

## Integration flows
| Flow | State on 25 Nov |
|---|---|
| A IoT telemetry | HISTORICAL (last ENV reading 22 Nov); nodes off |
| B Consumables, C Reusables | HISTORICAL |
| D Cameras | OFFLINE now; HISTORICAL 24 Nov; new rules SIMULATED |
| E Robots | HISTORICAL 24 Nov; new collector MOCKED |
| F PC monitoring | HISTORICAL 24 Nov; relay MOCKED |
| G Assistant | guard LIVE image in a test container; model NOT TESTED |
| H Knowledge | automated tests; index rebuild is started by hand |
| I AR | backend tests only |
| J n8n | containers healthy; workflows NOT TESTED here |

## Backup and rollback
Database: `backups/predeploy_smartlab_20261125_0132.dump` (44 tables listed by pg_restore). Images `:pre-20261125`. Git tag `backup-before-release-2026-11-25`.
Rollback: tag both images `:pre-20261125` as `:latest`, then `docker compose up -d --no-deps backend frontend`. No migration is involved.

## Owner
- Push when you want: `git push origin fix/pre-lab-hardening` and `git push origin fix/pre-lab-hardening:main`.
- Start with `launch.bat` so that cameras and collectors run the new code.
- 1N4007 and 20 RFID cycles at home; crop the twin picture; data_mode; central n8n error handler; backup passphrase.
