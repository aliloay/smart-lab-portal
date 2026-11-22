# Audit findings: what was done (21 Nov 2026, night)

The audit (this folder) was written read-only by an independent agent. The owner then decided per finding; this is
what happened. The commit is named for each fix; all tests were re-run after the last change (bottom).

| ID | Finding (short) | Status | How / where |
|---|---|---|---|
| F-01 | Recording link token worked as an admin sign-in | **FIXED, deployed** | `backend/app/core/security.py`: sign-in tokens carry `typ=access`, any other typ refused; test in `tests/test_security.py` |
| F-02 | Both networks on 192.168.1.0/24 | OWNER: keep as is | Works via interface metrics; router password unknown, no reset now |
| F-03 | 192.168.1.100 FANUC vs Hemaly PC | OWNER: keep as is | Power the robots (.100/.102) before Hemaly's PC; the PC has no admin rights for a fixed IP |
| F-04 | Camera streams offline | EXPECTED | The IP cameras are at GIU |
| F-05 | Assistants on the CPU although the gate said GPU | **FIXED, live** | `tools/knowledge/gpu_gate.py`: memory held by Ollama's own models counts as available; doctor shows "assistants on gpu: cameras idle" |
| F-06 | One-line facts went through full synthesis | **FIXED, live** | `docs/faq/` (60 Q&A) + instant FAQ path in `tools/knowledge/agent.py` (~40 ms, cited) |
| F-07 | Vault duplicates + broken links | **FIXED, live** | 322 stale mirrors moved to `vault_retired/` (`kb.py retire`); workflow links by note name; wikilinks 48 -> 0 |
| F-08 | ESP32-CAM showed the last booking QR forever | **FIXED, flashed 22 Nov** | QR text visible 10 s only; app-only flash (partition table identical), hash verified, back on Wi-Fi 0 % loss; rollback image `D:/SmartLabData/firmware_backup/esp32cam_app_before_F08_20261122.bin` |
| F-09 | Backups: no retention, uploads unencrypted, no restore test | **FIXED** (encryption: owner decision) | Move-not-delete retention to D: (C: 6.2 -> 2.4 GB); uploads encrypted when BACKUP_PASSPHRASE is set; restore drill passed |
| F-10 | Bin shows ~60 screws while "empty" | OWNER: no change | Owner was testing the bin |
| F-11 | n8n: no error workflow / timeouts / retries | **FIXED, live** | Error handler + 15 s timeouts (82/82 HTTP nodes) + webhook retries; backup `D:/SmartLabData/n8n_backup_20261121` |
| F-12 | Knowledge service started outside the launcher | **FIXED** | Restarted through `launch.bat` (single instance) |
| F-13 | 3 alerts OPEN while resolved | **FIXED** | Resolved through the audited API |
| F-14 | PC-10 agent 0.9; 3 TEST cards | NEEDS GIU | Update PC-10 at the lab; TEST cards are retired rows |
| F-15 | AR boxes lag phone motion | **FIXED, deployed** | Boxes follow the view between detections; detection 1.5 s (3 s with a marker); `frontend/src/pages/arshift.ts` |
| F-16 | No real pose model | **FIXED, live** | `tools/security_vision/pose.py` + YOLOv8n-pose: recorded lab frames 11-16 of 17 joints trusted, 62 ms/pass, 1 pass/s; hidden joints never invented |
| F-17 | Staff edit hid a pending sign-up | **FIXED, deployed** | `admin.py`: only is_active / removal ends pending |
| F-18 | CLAUDE.md model notes outdated | **FIXED** | CLAUDE.md, `.env.example` |
| F-19 | 422 MB loose git objects | **FIXED** | `git gc --prune=never` (nothing deleted): 9,816 loose objects packed |
| F-20 | No compile guard for core 3.2.1 | **FIXED** | `#error` on any other core (verified both ways) |
| F-21 | Face templates USER5/USER7 not in the trained model | OWNER | Re-train / re-enrol those two at the door (identity change - owner) |
| F-22 | Camera /health "ok" without a picture | **FIXED, live** | `status: "no_picture"` (still HTTP 200) |
| F-23 | Notification noise | **FIXED, deployed** | Unattended stock: one notice per bin per hour, none while calibrating |
| F-24 | RFID freezes at relock | OWNER HARDWARE | Fit the 1N4007 across the lock, then 20 relocks |
| F-25 | Commits not pushed | OWNER | Push commands given (agent never pushes) |
| F-26 | Robot collectors retry at home | EXPECTED | Robots at GIU; control stays UNAVAILABLE |

## Tests after the last change (21 Nov 2026, 22:30-23:05)
Backend 890 passed (3 skipped) · cameras 404 · robot monitor 44 · knowledge 72 · face server 22 · PC agent 40 · relay 6 ·
smartlab CLI 107 (incl. live) · frontend tsc + vite build + unit 10 · `smartlab doctor` 15 PASS, 0 FAIL.
Deployed portal build 5f88e92 (backend + frontend); camera services and knowledge service restarted through the launcher.
