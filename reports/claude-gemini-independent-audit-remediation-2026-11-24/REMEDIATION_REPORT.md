# Gemini audit of 24 Nov 2026: what was true, what was fixed

One report and one table (`REMEDIATION_FINDINGS.csv`) instead of 22 files.

## Result
The bugs in pages 11 to 20 of the PDF (identity, seats, robot collector, relay) are **real**. Each was reproduced: 16 of the 17 new camera tests and all 5 new robot tests fail on the old code and pass now. Some of the failures on the old code are simply the missing new field, so the count alone is not the proof; the assertions are in the files.
Gemini's `test_reproduce_bugs.py` was not found on this laptop. The tests here are new.

## The PDF contradicts Gemini's own CSV and this project
Checked, and **not** used:
| PDF says | Found |
|---|---|
| `_door_look_memory`, `look_return`, `identity_confirmed`, `CROSS_CAM_DIST_M`, `embedded_mask`, `check_guard` | in no source file |
| `access_logs`, 11 tables, 26 sensor rows, 5 to 9 Nov | no such table; 44 tables; 102,911 rows from ENV_LAB01, 5 Oct to 22 Nov |
| ESP32_DOOR_MASTER and four others | real names: MASTER_LAB01, ENV_LAB01, BIN_NODE_1, REUSE_BIN_1, CAM_LAB01 |
| BMP280 pressure | no such sensor |
| MX130 GPU | GTX 1650 |
| single-frame p95 307 / 294 ms | single frames were not logged |
| 80 % / 96 % after 00a3ba9 | no such run |
| ESP32s offline because of the hotspot name | they were at home on 24 Nov |
| guard bypass fully closed | Gemini's CSV (S-2b): open, and it was. Fixed |
| /api/metrics came with 66e79c1 | 66e79c1 is camera code; the routes were already live |

Applied to the paper results: window p95 added, 9 and 10 people, 99.8 %, loopback note, refusals wording, missing raw files, overlap wording.

## Identity rules now
- Confirmed = door, this camera's own face, or staff; or a floor pairing with a confirmed name of the other camera.
- Look (here or across the cameras), desk and seat: a marked guess.
- A doubted name returns only by face, door or staff.
- Seen in one picture with the confirmed person: never their name, on any path.
Cost: seated people and people seen only by look are named less often. How much is **not measured**: that needs the live cameras.

## Limits
- All fixes offline. Cameras and collectors take them at their next start.
- A swap during a touch right after the staff confirmation, before any clean view, cannot be detected.
- Elimination (one unnamed person, one free name) still names; it was not part of the findings.
- Robot view: synthetic pictures only.
