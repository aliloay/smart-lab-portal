# Smart Research Lab: executive readiness report (19 Nov 2026)

**Verdict: the software is release-ready for the local thesis demo and exhibition.**
What remains needs hardware or a person: the ESP32 nodes at home, a robot power-on, one router setting, one password change, and a lab re-measurement.
Nothing was pushed to GitHub. No robot, door, relay, alarm or n8n workflow was touched.

## What was done in this closure (18–19 Nov)

| Stage | Result | Status |
|---|---|---|
| 1. Media inventory | 14 sources reviewed with contact sheets; privacy problems listed per clip (VIDEO_SOURCE_INVENTORY.md) | DONE |
| 2. Showcase film | `SMART_RESEARCH_LAB_FINAL_SHOWCASE.mp4`, 3 min 07 s, 1080p30 + `.srt`; 7 chapters; real lab photos, the real UR5e with its twin, phone AR, node close-ups; Piper narration, original synthesised music and sound effects; faces, phone number, user names and the sign-in removed or blurred. **19 Nov correction:** v1 still showed lab Windows account names (48-60 s, 168-175 s) and a third person's name (175-180 s); blurred in v2, v1 kept on D: | FIXED AND VERIFIED (v2 frame-checked, full decode OK) |
| 3. AI speed | worst case 41 s → 22 s cold at home; investigate prompt 1,825 → 1,046 tokens; repeated questions instant (cache); live service 5.3 s for a new question | FIXED AND VERIFIED (home); lab re-measure NOT TESTED |
| 3. AI quality | fixed the "three layers" hallucination (chunking); added the lab-PC relay code to the vault; a guard answers unsafe, secret and impossible questions before the model (6/6 adversarial now refused or corrected) | FIXED AND VERIFIED |
| 4. Handoffs | opt branch merged (fc18c99); Gemini's fixes already merged (3e4ca30); build stamp live (`ecbb167-20261118231702`); PC-14 card → **PC-11**; old TEST cards confirmed hidden (kept, no deletion) | FIXED AND VERIFIED |
| 5. Checks | backend 841 + contract fix, cameras 396, AI 64, robots 44, PC agent 40, relay/LAN/voice/OPC UA 21, tsc + vite; live smoke 200s; **25 concurrent logins 25/25**, 50 parallel dashboards 200/200 | TESTED — PASSED |
| 6. Reports | this file + FINAL_TEST_RESULTS, FINAL_OPEN_ISSUES.csv, FINAL_UNRUN_TESTS.csv, FINAL_OPERATOR_ACTIONS, FINAL_RELEASE_READINESS_SCORECARD, FINAL_TEST_EVIDENCE_INDEX, AI_PERFORMANCE_BEFORE_AFTER, AI_QUALITY_VALIDATION, VIDEO_* logs, GEMINI_ARGON_FULL_INSPECTION_PROMPT | DONE |

## Readiness by area (detail in FINAL_RELEASE_READINESS_SCORECARD.md)
- **READY:** portal and navigation, build traceability, login capacity, AI grounding and safety, knowledge vault, showcase film.
- **READY WITH NOTES:**
  - cameras (rare crossing name swaps are guarded);
  - lab PCs (PC-11 sticker, PC-10 = GIULAB20-PC13 agent 0.9);
  - robots and twins (power-on check pending);
  - AI speed (lab re-measure pending);
  - n8n (starts with `launch.bat`);
  - AR (phones warn about the self-signed certificate);
  - security hygiene (password change).
- **BLOCKED (not software):**
  - ESP32 nodes (at home);
  - Hemaly-PC IP conflict (router);
  - unmeasured thesis numbers.

## Owner actions, in order (FINAL_OPERATOR_ACTIONS.md)
1. **Change the admin password** before the exhibition.
2. **Router:** stop Hemaly's PC getting .100/.102 by DHCP. Move the pool above .110, reserve the robot addresses, or give Hemaly's Smart_Lab card a static .210.
3. **Connect the ESP32 nodes** when ready. Claude then builds and flashes one step at a time (ESP32-CAM on core 3.2.1).
4. **Power on UR5e/FANUC** once and confirm the twins go ONLINE (read-only).
5. Confirm the **PC-11** sticker. Optionally update PC-10's agent (hostname GIULAB20-PC13).
6. At the next lab session: re-measure AI answer time with both cameras live, and take the missing thesis numbers (door latency, cold start, power-cut recovery, load-cell accuracy, cost, node power).
7. Optional: run the **Gemini Argon full inspection** (prompt ready) for an independent "what is left" list.
8. Push to GitHub when you decide.

## Deployment and rollback
- **Live:** backend `034e51c2a97b`, frontend `f24859878193`, stamp `ecbb167-20261118231702`.
- **Rollback:** `docker tag smart-lab-portal-backend:pre-merge-20261119 smart-lab-portal-backend:latest`, the same for frontend, then `docker compose up -d --no-deps backend frontend`.
- **DB backup before deploy:** `D:\SmartLabData\db_dumps\predeploy_2026-11-19.dump`.
- **Knowledge index backup:** `D:\SmartLabData\kb_backup_2026-11-19\`.
