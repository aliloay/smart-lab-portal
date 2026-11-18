# Tablet, door, TFT and enclosure audit

## Scope rule
Door firmware, auth, credentials, relay and emergency behaviour were **not changed** (CLAUDE.md: the door opens only
from the Master ESP32). Nothing was flashed.

## What exists (STATIC INSPECTION)
- **Door tablet screen:** served by the Master ESP32 itself (firmware/SmartLab_Master_Portal, portal-1.1 NFC recovery compiled earlier, NOT flashed). The portal Devices page links to it; emergency messages can be read aloud "on every screen and the tablet".
- **Master identity:** `MASTER_LAB01` / `LAB_01` (matches the backend seed).
- **Portal pages for screens:** /welcome (door scene) and /scan. Emergency page with voice on/off per message.
- **Face server** (door camera identity): unchanged code. Its auto-enrolment test fixture was made independent of the working directory (test-only). 14 passed, 1 skipped.

## Tests in this integration
| Item | Result | Class |
|---|---|---|
| Phone-width / touch layout of staff pages | workflows.mjs phone-width checks passed (part of 30/30) | LIVE LOCAL SOFTWARE (isolated) |
| Session expiry -> sign-in form | navigation.mjs: ok | LIVE LOCAL SOFTWARE (isolated) |
| Master firmware compile | see ESP_FIRMWARE_AUDIT_EACH_NODE.md | STATIC (compile only) |
| RFID / QR / fingerprint / face at the door, relay, reed, buzzer, LEDs, TFT states | needs the door hardware | BLOCKED (on campus) |
| Tablet kiosk / full-screen, outage state, spoken prompts on the real tablet | needs the tablet + door | BLOCKED (on campus) |

## Enclosure
"Door enclosure component dimensions.md" is not in the repository; it was supplied as an attachment. No mounting
dimensions were invented. The earlier enclosure work (4 enclosures, STLs, door box fit-test release b8c5bdb) is in
history. Its evidence classes (manufacturer verified / variant matched / reference only / unverified) remain the
owner's document.
