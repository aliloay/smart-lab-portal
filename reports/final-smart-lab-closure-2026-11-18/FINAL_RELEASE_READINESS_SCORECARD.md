# Final release readiness scorecard (19 Nov 2026)

Scale: **READY** (works and verified) · **READY WITH NOTES** (works; a known limit is documented) · **BLOCKED** (needs hardware or a person) · **NOT IN SCOPE**.

| # | Area | Score | Evidence | What is left |
|---|---|---|---|---|
| 1 | Portal (pages, navigation, roles) | **READY** | 841 backend tests + tsc + vite build; live smoke all 200; deployed `ecbb167` | — |
| 2 | Build stamp / deploy traceability | **READY** | `/api/health` and `/version.json` = `ecbb167-20261118231702`; rollback tags `pre-merge-20261119` | — |
| 3 | Login capacity | **READY** | 25 simultaneous logins 25/25 (max 2.0 s); 50 parallel dashboards 200/200 (max 4.3 s) under full CPU load | — |
| 4 | Security cameras (identity, numbering, seats) | **READY WITH NOTES** | 396 tests; live at GIU 18 Nov | Names drawn by the camera can still swap in rare crossings (guarded, documented) |
| 5 | Lab PCs (agent, relay, wall, share, message, maintenance) | **READY WITH NOTES** | live at GIU 18 Nov on 11 PCs; 40 + 6 tests | PC-11 sticker to confirm; PC-13 agent 0.9 |
| 6 | Hemaly's engineer PC / network | **BLOCKED** (router) | owner report: DHCP .100–.103 collides with robot IPs | OA-2: DHCP pool / reservation / static .210 |
| 7 | Robots + digital twins | **READY WITH NOTES** | twins + liveness live 18 Nov (controllers off → OFFLINE shown honestly); 44 tests | Power-on check (read-only) |
| 8 | 4 ESP32 nodes + ESP32-CAM | **BLOCKED** (hardware at home) | firmware in repo; last heartbeat 17 Nov | Owner connects boards → step-by-step flash/test |
| 9 | AI assistant (speed) | **READY WITH NOTES** | worst case 41 s → 22 s cold at home; repeats instant; 1,825 → 1,046 prompt tokens | Re-measure at the lab with cameras live |
| 10 | AI assistant (grounding / safety) | **READY** | 12-question check incl. 6 adversarial: all correct or refused; 64 tests | One weak phrasing ("How does the door open?") documented |
| 11 | Knowledge vault (Obsidian) | **READY** | 445 notes, 13,153 chunks, 0 broken links; lab-PC code added | — |
| 12 | n8n automations | **READY WITH NOTES** | 23 workflows in repo; live n8n not started at home (rule) | Starts with `launch.bat` on lab days |
| 13 | AR (phone) | **READY WITH NOTES** | 17 Nov test: UR5e 52 %, FANUC 89 %, door 93 %, bin 80 %, markers → LIVE | HTTPS "Not Secure" warning on phones (self-signed cert) |
| 14 | Showcase video | **READY** (after final check) | `SMART_RESEARCH_LAB_FINAL_SHOWCASE.mp4` + `.srt`; privacy checklist in the clip log | Optional: blur camera name labels |
| 15 | Security hygiene | **READY WITH NOTES** | no secrets in git (config.json ignored); secrets never in vault/AI | Admin password change before exhibition (OA-1) |
| 16 | Thesis measurements | **BLOCKED** (hardware) | latency/resources/AI speed measured | Door end-to-end latency, cold start, power-cut recovery, load-cell accuracy, cost, power per node |

**Overall:** software is release-ready for a local demo. The remaining items are hardware (nodes, robots power-on), one router setting, one password change, and lab re-measurements.
