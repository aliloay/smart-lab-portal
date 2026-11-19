# What is left (19 Nov 2026)

Software that could be fixed safely from the laptop is done (see GEMINI_RECONCILIATION_AND_FIXES_2026-11-19.md and
FINAL_INTEGRATION_AND_DEPLOYMENT_NOTES.md). What remains needs the owner, the hardware or a decision.

## Before the presentation
| Pri | Item | Who | Status |
|---|---|---|---|
| P0 | Change the admin@ and ramy@ passwords (`docker compose exec backend python set_password.py <email>`), then update `E2E_PASSWORD` | owner | OPERATOR ACTION REQUIRED |
| P0 | Hemaly's PC vs robot addresses .100 / .102 (router DHCP pool or a fixed .210) | owner / GIU IT | OPERATOR ACTION REQUIRED |
| P0 | Thesis: Appendix B pin tables (HX711 32/33, PN532 on Wire1 18/19, LCD 21/22, servo 25) and the 8 Nov door relay stage | owner (writing week) | OPERATOR ACTION REQUIRED |
| P1 | Flash the 17-18 Nov firmware on the four nodes + ESP32-CAM (core 3.2.1), measure the VERIFY constants | owner + hardware | NEEDS HARDWARE |
| P1 | Thesis numbers with no measurement yet: door latency, cold start, power-cut recovery, node power draw, 30-min offline run, priced BOM | owner + hardware | NEEDS HARDWARE |
| P1 | Robots powered once: twins go online and follow, then show offline after power-off | owner at GIU | NEEDS HARDWARE |
| P1 | Assistant times re-measured with both cameras running | owner at GIU | NEEDS HARDWARE |
| P2 | Film: keep or blur the names the camera software draws on its boxes | owner decision | OPERATOR ACTION REQUIRED |
| P2 | PC-11 sticker check; PC-10 (GIULAB20-PC13) agent 0.9 -> 1.0 | owner at GIU | NEEDS HARDWARE |
| P2 | Optional clips: a real door entry without third-party faces; FANUC moving with its twin | owner | OPERATOR ACTION REQUIRED |
| P2 | Thesis admin: acknowledgements, Eng. Shehab's full title | owner | OPERATOR ACTION REQUIRED |

## Software items deliberately not done
| Item | Why |
|---|---|
| Duplicate device-offline notifications (portal at L1 + n8n workflow 04 at L1) (B-15) | Fix belongs in the live n8n workflow, which must not be edited; the portal side is correct. Owner can set workflow 04 to notify from L2 |
| 322 orphan mirror notes in the vault (B-18) | Removing them is a deletion; the owner may delete `14 - Sources\docs_knowledge_obsidian_vault_*.md` by hand |
| Marker art for GIU PCs (B-22) | Rejected: the art pictures carry PC_01's QR; GIU PCs correctly use generated cards |
| Large tracked files (STEP copies, retired ONNX, B-30) | Rewriting history / deleting is the owner's call after the defense |
| Push to GitHub | Not authorised; check `reports/` privacy first |
