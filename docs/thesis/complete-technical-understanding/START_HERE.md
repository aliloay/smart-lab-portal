# Start here: understanding the Smart Lab

Taught from commit 11003b0 (live on the laptop since 25 Nov 2026). Where this text and the code disagree, the code is right.

## What exists now
| Document | State |
|---|---|
| [LESSON_01.md](LESSON_01.md): the Smart Lab as one system | written |
| [API_CATALOG.md](API_CATALOG.md): 355 routes | generated from the code |
| [DATABASE_RELATIONS.md](DATABASE_RELATIONS.md): 43 tables and their relations | generated from the code |
| Lessons 2 to 12, glossary, question bank, claims and evidence | **not written yet**: one lesson at a time, after your answers |

Already in the repository, checked against the code when its lesson comes: [wiring and pins](../../hardware/wiring-and-pinouts.md), [power](../../hardware/power-distribution.md), [access architecture](../../ARCHITECTURE.md), [measured results of 24 Nov](../../../reports/final-giu-lab-evidence-2026-11-24/RESULTS_FOR_THE_PAPER.md), [home measurements of 21 Nov](../../reports/MEASUREMENTS_2026-11-21.md).

## Order (60 to 90 minutes each)
1. The whole system
2. ESP32 nodes, sensors, pins, power
3. The two bins: weight and NFC
4. The door: two factors and fail closed
5. Backend, database, live updates
6. Frontend: how a page gets its data
7. Cameras 1: detection, tracking, looks
8. Cameras 2: who is allowed to have a name
9. Robots and digital twins
10. PC agents, relay, screens
11. Assistants, knowledge, Obsidian, n8n, AR
12. Results, statistics, limits, defence practice

## Code folders to recognise
`firmware/` nodes · `backend/app/api/routes/` addresses · `backend/app/services/` rules · `backend/app/models/` tables · `frontend/src/pages/` pages · `tools/security_vision/` cameras · `tools/robot_monitor/` robots · `tools/pc_agent/` and `tools/relay/` PCs · `tools/knowledge/` project assistant · `automation/n8n/json/` workflow copies

## Known gaps
1. No live run yet of the identity rules of 25 Nov.
2. No FANUC pendant numbers; the UR5e was compared in one still pose.
3. No independent thermometer reference.
4. 1N4007 diode and 20 RFID cycles open.
5. No ground truth for tracking, so no accuracy percentage may be claimed.
6. Section 8 replay counts and the portal assistant counts have no raw file.
7. Seated people: 3.3 m between the two floor maps.
