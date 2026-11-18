# N8N_OBSIDIAN_AND_TABLET.md

- **Evidence Class**: `LIVE_SERVICE` + `STATIC_INSPECTION`.

---

## 1. n8n Automation Audit (`LIVE_SERVICE`)

- **Container**: `smart-lab-portal-n8n-1` (`n8nio/n8n:2.40.7`), bound to `127.0.0.1:5678`, status `Up (healthy)`, `/healthz` responds `HTTP 200` in `8 ms`.
- **Backup & Encryption Key Persistence**:
  - Backed up in `D:\SmartLabData\n8n_backup_20261118` and persisted in Docker volume `n8n_data` with `N8N_ENCRYPTION_KEY` in `.env` (never printed).
- **Workflow Inventory (`26 / 26` Active Workflows Verified via `docker exec smart-lab-portal-n8n-1 n8n list:workflow`)**:
  - `Smart Lab 01` through `Smart Lab 23` (Booking confirmation briefing, Upcoming booking reminders, Access denial intelligence, Device offline alert with escalation, Maintenance automation, Daily/Weekly lab reports, Sensor threshold alerts, Pre-booking lab readiness, Post-session follow-up, Daily data quality check, Rule-based anomaly detection, Environment hazard escalation, Environment/bin node offline, Consumable below reorder, Stock change with nobody inside, Reusable item overdue, Robot offline or fault, Robot running without booking, Lab PC offline, Exam-mode reports, Robotics Lab daily summary, Emergency warning).
  - `Knowledge 1` (`Local source sync`), `Knowledge 2` (`Vault health check`), `Knowledge 3` (`Weekly knowledge summary`).
- **Retry & Loop Safety (Commit `39e8aef`)**:
  - All 18 scheduled HTTP read nodes and 4 knowledge job nodes have `retryOnFail: true, maxTries: 5, waitBetweenTries: 5000` (5 retries, 5 s apart) so transient portal restarts or deploy windows do not fail scheduled runs.
  - Notification/POST side-effect nodes and webhook workflows were deliberately left without automatic retry to prevent duplicate alerts, and no production side-effecting workflows were triggered during this audit.

---

## 2. Obsidian Project Vault Audit (`LIVE_SERVICE` + `STATIC_INSPECTION`)

- **Configuration (`tools/knowledge/config.json`)**:
  - Configured at `C:/Users/dell/SmartLabKnowledge/vault` (index data at `C:/Users/dell/SmartLabKnowledge/data`, last built `2026-11-18T13:20:39+02:00`, `embeddings: true`).
  - Also mirrored in repo subtree `docs/knowledge/obsidian/vault/`.
  - Per privacy and safety rules, only project-generated index health and repo configuration were inspected (personal notes outside the project scope are never read).
- **Link Integrity**:
  - Commit `39e8aef` excluded generated vault copies from `kb.py` source ingestion, reducing broken wiki/markdown links from `27` to **`0`**.

---

## 3. Tablet / Door TFT / Enclosure Audit (`STATIC_INSPECTION`)

### 3.1 Master Door Controller TFT & Read-Only Tablet Mirror (`docs/hardware/NODE_LCD_AND_UNIT_MAPPING.md`)
- **Hardware**: `MASTER_LAB01` (`firmware/SmartLab_Master_Portal/SmartLab_Master_Portal.ino`) drives a `160x128` ST7735 colour TFT (`INITR_BLACKTAB`, rotation 3, `25 char` line wrap) and serves a read-only tablet web mirror (`tablet_display.h`: `GET /`, `/state`, `/photo` — zero state-changing or door-unlocking routes).
- **Verified Screen States**:
  1. `screenBoot`: `SMART LAB` / `Starting...`
  2. `screenIdle`: `WELCOME` / `Scan your QR code` / `or RFID tag / card` / `STEP 1 OF 2` + reader/camera health notes (`RFID offline - use QR code`, `Camera offline - use card`)
  3. `screenChecking`: `CHECKING` / `Booking QR code found` / `One moment...`
  4. `screenStep1Ok`: `QR CODE OK` or `RFID OK` + user display name
  5. `screenVerify`: `VERIFY` + name + `Look at the camera` / `or place your finger` + `STEP 2 OF 2` + 20 s countdown bar
  6. `screenGranted`: `DOOR UNLOCKED` / `ACCESS GRANTED` + name (and stored photo if enrolled in `user_photos.h`)
  7. `screenDoorOpen`: `DOOR OPEN` / `Please close the door`; escalates after `30 s` (`DOOR_HELD_OPEN_MS`) to `DOOR HELD OPEN`
  8. `screenDenied`: `DOOR LOCKED` / `ACCESS DENIED` + `friendlyReason()` mapping
  9. `screenAlarm`: `! SECURITY ALERT !` / `FORCED ENTRY` / `Door opened while locked`
  10. `screenEmergency`: `! EMERGENCY !` / `DOOR OPEN` or `LAB LOCKED` + admin message.

### 3.2 Door Enclosure Component Dimensions (`reports/Door enclosure component dimensions.md`)
- Retained exact source confidence labels without inventing unmeasured dimensions:
  - **DATASHEET VERIFIED**: GROW R307 body (`44.10 x 20 x 23.50 mm`, sensing aperture `15 x 11.19 mm`, side notches `1.50 mm` deep at `22.90 mm` from front; must verify 44.1 mm R307 vs 52 mm R307S before printing); ST7735 1.8" TFT glass (`34.70±0.2 x 46.70±0.2 x 2.40±0.1 mm`, active area `28.03 x 35.04 mm`); CNC Kitchen M3 standard insert (`Ø4.0 mm` hole, `1.6 mm` min wall); cable glands (`PG7` `12.5–12.8 mm`, `M12` `12.0–12.3 mm`, `PG9` `15.2–15.5 mm`, `M16` `16.0–16.3 mm`).
  - **VARIANT MATCHED**: MSP1803 TFT PCB (`34.50 x 58.00 mm`, `4 x Ø3.20 mm` holes on `28.50 x 52.00 mm` grid); Most 5 V active buzzer (`Ø12.0 x 9.5 mm`); Ekostra PN532 V3 outline (`42.7 x 40.4 x 4 mm`); ESP32 30-pin CH340 (`51.5 x 28.5 mm`); XL4016 buck (`~64 x 47 x 26 mm`); WAGO PCT-212 clone (`21 x 12.5 x 14.5 mm`).
  - **REFERENCE ONLY / UNVERIFIED**: PN532 V4 CAD hole pattern (`27.80 x 25.20 mm`, `Ø3.05 mm` — slot holes for red V3 clone); internal module mounting holes (ESP32, XL4016, HW-307 relay, SYB-170 breadboard, DC-022 jack `7.8 mm` vs `12 mm` panel hole conflict — require caliper check + test coupon before final print).
