---
type: "source-mirror"
source_kind: "documentation"
source_path: "firmware/SmartLab_Reusable_Bin_Modular/README.md"
source_hash: "2edbc359e36e29817a7eafaf9219c7781514f5ee1afd56b5d37a3300aac1dd8c"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `firmware/SmartLab_Reusable_Bin_Modular/README.md` - edit the original in the repository, not this note.

Systems: [[Reusables bin]]

# Smart Reusable Equipment Bin — modular firmware

**Status:** compiles for ESP32 (Arduino core 3.3.12) in HARDWARE_TEST_MODE and
FULL_SYSTEM_MODE. **Not yet run on hardware.** Every value marked `VERIFY` in
`src/config.h` is a placeholder until measured on the real bin. Nothing below
is a measured result; the "expected output" blocks show the *format* the
firmware prints, not readings.

The earlier single-file firmware (`../SmartLab_Reusable_Bin/`, reuse-0.3) is
kept unchanged for reference. This one talks to the same portal API.

---

## 1. Files

| File | Role |
|---|---|
| `SmartLab_Reusable_Bin_Modular.ino` | setup/loop: starts the enabled parts, runs test mode or the full system |
| `src/config.h` | **the only file to edit**: mode, enabled tests, pins, thresholds, portal paths |
| `src/secrets.h` | Wi-Fi + this bin's device key (gitignored; template `secrets.example.h`) |
| `src/LoadCellManager.*` | HX711 + load cell: raw, grams/kg, stability, change detection, calibration |
| `src/DisplayManager.*` | 16×2 I2C LCD: address by scan, rewrites only changed lines; `i2cScan()` |
| `src/NFCManager.*` | PN532 (I2C): firmware-version check, UID, duplicate suppression |
| `src/ServoManager.*` | MG90S on the pedal: press / hold / release, detach at rest, lockout |
| `src/LidSensorManager.*` | reed switch: LID_UNKNOWN / LID_OPEN / LID_CLOSED, debounced |
| `src/RFIDManager.*` | **experimental**, reader-agnostic inventory (disabled until the reader is identified) |
| `src/InventoryManager.*` | inventories as sets; `removed = before − after`, `added = after − before` |
| `src/Verification.*` | cross-check of a lid cycle (lid, weight, RFID) → VERIFIED / FLAGGED + `selftest` |
| `src/TransactionManager.*` | the state machine (FULL_SYSTEM_MODE) |
| `src/WiFiManager.*`, `src/BackendClient.*` | Wi-Fi with retry; the portal's real endpoints |
| `src/FaultManager.*` | fault flags (component, lid, network) |
| `src/HardwareTests.*` | per-component tests + the Serial command menu |
| `platformio.ini` | PlatformIO build of the same sources (not built here) |

## 2. Libraries (installed and used for the verified build)

| Library | Version | Author | Used for |
|---|---|---|---|
| esp32 Arduino core | 3.3.12 | Espressif | board, WiFi, HTTPClient, Preferences, Wire |
| HX711 | 0.6.5 | Rob Tillaart | load cell ADC |
| LiquidCrystal I2C | 1.1.2 | Frank de Brabander | LCD (warns "avr only" - works on ESP32, as on the other nodes) |
| Adafruit PN532 | 1.3.4 (+ Adafruit BusIO 1.17.4) | Adafruit | NFC |
| ESP32Servo | 3.2.1 | Kevin Harrington, John K. Bennett | servo PWM |
| ArduinoJson | 7.4.3 | Benoit Blanchon | portal replies |
| RFID | **none chosen** | — | until the old reader's model is known |

Board: **ESP32 Dev Module** (FQBN `esp32:esp32:esp32`).

## 3. Pin map (proposed; change only in `config.h`)

| Part | ESP32 | Notes |
|---|---|---|
| HX711 DT / SCK | GPIO32 / GPIO33 | HX711 VCC per its board; DT is pulled up so a missing HX711 reads "not responding", not noise |
| I2C SDA / SCL | GPIO21 / GPIO22 | LCD backpack and PN532 share the bus (different addresses) |
| PN532 | I2C 0x24 | S1 = ON, S2 = OFF (I2C mode); IRQ/RESET not wired |
| LCD backpack | I2C, found by scan | 0x20–0x27 / 0x38–0x3F, never 0x24. **Measure its SDA/SCL pull-up voltage before connecting**: 5 V pull-ups need level shifting (hardware decision) |
| Servo signal | GPIO25 | servo + and − from the **external 5 V** supply, GND common with the ESP32 |
| Reed switch | GPIO27 → GND | internal pull-up; which level means "closed" is `REED_LEVEL_WHEN_CLOSED` (VERIFY) |
| RFID | not assigned | `RFID_PIN_A..D = -1` until the reader is identified |

## 4. Configuration

`src/config.h`:
- `BIN_MODE` — `HARDWARE_TEST_MODE` (default) or `FULL_SYSTEM_MODE`.
- `ENABLE_*_TEST` — which parts are started in test mode (default: **load cell only**).
- Load cell: `WEIGHT_SAMPLE_COUNT`, `WEIGHT_STABILITY_THRESHOLD_G`, `WEIGHT_STABLE_TIME_MS`, `WEIGHT_CHANGE_THRESHOLD_G` (all VERIFY). The calibration factor is **not** in this file: it is measured with `cal` and saved in flash.
- Servo: no angles in this file; `servo set idle/open` saves them in flash. `OPEN_HOLD_MS`, `SERVO_MOVE_MS` VERIFY; `SERVO_MAX_HOLD_MS` caps every hold.
- Lid: `REED_LEVEL_WHEN_CLOSED`, `LID_OPEN_TIMEOUT_MS`, `LID_CLOSE_TIMEOUT_MS`.
- Portal paths, `DEVICE_ID = REUSE_BIN_1`, `LAB_ID`, static IP `.154`.

## 5. Serial Monitor

115200 baud, line ending **Newline**. Type `help`. Every line starts with a tag:
`[BOOT] [LOADCELL] [LCD] [I2C] [NFC] [SERVO] [REED] [RFID] [WIFI] [BACKEND] [TRANSACTION] [SYSTEM] [ERROR]`.

| Command | Does |
|---|---|
| `status` | every part's state, faults, uptime |
| `i2c` | scan the I2C bus |
| `selftest` | runs the transaction-logic examples (no hardware needed) |
| `tare` / `cal <grams>` / `show` / `watch on|off` / `calclear` | load cell |
| `lcd <text>` | write on the LCD |
| `nfc` | PN532 status |
| `servo angle <n>` / `servo center` / `servo stop` | manual moves (test mode) |
| `servo set idle <n>` / `servo set open <n>` | save the calibrated angles |
| `servo open` / `servo close` | press / release with the saved angles |
| `servo clear` / `fault clear` | unlock after a lid fault |
| `reed` | lid state |
| `rfid scan` / `rfid status` | experimental RFID |

---

## 6. Bring-up order (one part at a time)

0. **ESP32 only** — flash the default build (all tests except load cell can stay off; with nothing connected the load-cell test just reports "not responding"). Check the boot lines and run `selftest`.
1. **Load cell + HX711** (§7)
2. **LCD** (§8)
3. **PN532** (§9)
4. **Servo** (§10)
5. **Reed switch** (§11)
6. **RFID** (§12)
7. **Integration** (§13)

After each step: power off, connect the next part, enable its `ENABLE_*_TEST`, re-flash.

## 7. Load cell + HX711 test and calibration

Enabled by default (`ENABLE_LOAD_CELL_TEST`).

1. Mechanics: the load cell's fixed end bolted to the base, the load end carries the bin/platform (arrow on the bar = load direction). Nothing else may touch the weighed part: no cable, wall or lid linkage.
2. Wiring (power **off**): load cell → HX711 E+ E− A+ A− (wire colours of this cell are unknown: identify the excitation pair and signal pair from its datasheet or by measuring resistance, do not guess); HX711 VCC/GND to the ESP32's 3.3 V/GND; DT → GPIO32, SCK → GPIO33.
3. Flash, open the Serial Monitor. Expect (format):
   ```
   [BOOT] Smart Reusable Bin - reuse-mod-0.1 - HARDWARE_TEST_MODE
   [LOADCELL] Initializing HX711 (DT=GPIO32, SCK=GPIO33)...
   [LOADCELL] OK - HX711 answering
   [LOADCELL] NOT calibrated: raw counts only (run: tare, then cal <grams>)
   [LCD] Not enabled
   ...
   [LOADCELL] raw <counts> (not calibrated)          every 0.5 s
   ```
4. Press gently on the platform: **raw must change** and come back when released. Record the raw spread with nothing on it for 1 min (noise).
5. Platform empty → `tare`.
6. Put a **reference mass you weighed on a trusted scale** → `cal <its grams>` (e.g. `cal 500` if the trusted scale said 500.0 g). The factor is computed and saved.
7. Now each line shows `raw | g | kg | spread | state`. Remove/replace the mass and watch `WEIGHT_DECREASE` / `WEIGHT_INCREASE` lines.
8. Record for the thesis: reference vs reading at several masses (error %), repeatability (same mass 10×), noise (spread over 10 min), drift (hours), settling time after placing a mass. Then set `WEIGHT_STABILITY_THRESHOLD_G` and `WEIGHT_CHANGE_THRESHOLD_G` from those numbers.

## 8. LCD test

Enable `ENABLE_LCD_TEST`. **Before connecting:** power the backpack alone and measure SDA and SCL to GND. If they sit at ~5 V, do not connect them to the ESP32 without a level shifter.
Expect `[I2C] Device found at 0x..` and `[LCD] I2C device found at 0x.. - LCD started`; the LCD shows `LCD TEST OK` / `0x.. up <s>s`, updated once a second without flicker. `lcd hello` writes text. Not found → `[ERROR] LCD not found` and everything else still runs.

## 9. NFC (PN532) test

Enable `ENABLE_NFC_TEST`. PN532 switches **S1 ON, S2 OFF**. Expect `[I2C] Device found at 0x24 (PN532 address)` and `[NFC] PN532 detected: chip PN532, firmware <x.y>` (the firmware version is read from the chip, not assumed). Hold a tag: `[NFC] Tag UID 04.. (7-byte UID, ISO14443A) at <ms>`. The same tag again within 3 s is ignored (duplicate suppression); a different tag is reported at once.
Record: read success rate, maximum distance, orientation sensitivity.
> Note: the hardware list has one PN532 so far, the door's. The bin needs its own.

## 10. Servo test (pedal)

Enable `ENABLE_SERVO_TEST`. **The servo never moves at boot.**
1. Servo powered from the external 5 V supply, GND common with the ESP32, signal on GPIO25. Servo horn **not yet linked** to the pedal.
2. `servo angle 90` → it moves and holds; `servo stop` → torque off.
3. Link the horn to the pedal mechanism with the servo at a known angle. Find, in small steps (`servo angle <n>`), the angle where the pedal is fully released (**idle**) and the smallest angle that opens the lid fully (**open**). Stop if anything binds.
4. Save: `servo set idle <n>`, `servo set open <n>`.
5. `servo open` (presses and holds), `servo close` (releases, then detaches). A hold is released automatically after 15 s.
Record: angles, lid opening time, supply voltage sag while pressing (multimeter on the servo's 5 V).

## 11. Reed switch test

Enable `ENABLE_REED_TEST`. Reed between GPIO27 and GND; magnet on the lid. The monitor prints `[REED] LID OPEN` / `LID CLOSED` every second and on every change. If it shows the opposite, change `REED_LEVEL_WHEN_CLOSED`. Record: the gap at which it switches, bounce (repeated lines when the lid moves).

## 12. RFID (experimental)

**The reader's model, interface, voltage, pins, range and multi-tag ability are unknown, so nothing is implemented for a specific reader.** Default: `RFID_READER_MODEL RFID_NONE` → `[RFID] Disabled / not configured` and the bin works without it.
1. Identify the module (markings, chip, datasheet): frequency band (125 kHz LF / 13.56 MHz HF / UHF), interface (UART/SPI/I2C/Wiegand), supply and logic voltage.
2. Add a reader class (`src/RFIDManager.h`, "Adding a reader"), enable `ENABLE_RFID_TEST`.
3. Test with 1, 2, 3 … tags inside the bin: `rfid scan` prints every tag seen in the 1.5 s window with the time it was first seen.
4. Record: how many tags it reads at once (if any more than one), range, effect of the bin walls and of the items themselves.
Do not report RFID inventory as working until these measurements show it.
> Note from earlier bring-up: an old MFRC522 (13.56 MHz HF) was retired from the door. If that is this reader: it reads ISO14443A cards at a few cm, so listing items inside a bin is unlikely — measure, do not assume either way.

## 13. Full integrated test (FULL_SYSTEM_MODE)

1. Set `#define BIN_MODE FULL_SYSTEM_MODE` (or build with `-DBIN_MODE=2`).
2. In the portal: issue this bin's own key (Devices → REUSE_BIN_1 → Issue key) into `src/secrets.h` (`DEVICE_KEY`). Without it every call is refused (401).
3. Boot: `[WIFI] Connected`, `[SYSTEM] Self-test: faults ...`, `[SYSTEM] READY`; LCD `SMART BIN / Ready`. Faults such as `SERVO_ANGLES_NOT_SET` keep the lid shut (LCD `FAULT`).
4. In the portal, assign each item's NFC tag (Inventory → Reusable items → Assign tag → Use last scanned).
5. **Return:** item checked out → scan its tag → `VERIFYING` → `AUTHORIZED / Opening...` → `RETURN ITEM / Place item` → `CLOSING` → `VERIFYING` → `VERIFIED / Transaction OK` (or the portal's `CHECK WEIGHT`).
6. **Checkout:** person checked in at the door → Lab page → Smart bin → Take → `OPEN / Take <item>` → lid closes → `SCAN <item> / to confirm` → scan → `CHECKED OUT`.
7. Faults to provoke: hold the lid shut during opening (→ `LID_POSITION_TIMEOUT_OPEN`, servo locked out until `servo clear`); unplug Wi-Fi (→ `Offline`, scans show `NO CONNECTION`, the lid stays shut); wrong item's tag at checkout (→ `WRONG ITEM`).

---

## 14. How the before/after RFID inventory works

An inventory is a **set** of unique tag IDs (sorted, no duplicates). The bin
takes one just before the lid opens and one after it closes:
- `removed = before − after`, `added = after − before` (any number of items).
- Checkout of A001: `{A001, A002, A003}` → `{A002, A003}` ⇒ removed `{A001}`.
- Return of A001: `{A002, A003}` → `{A001, A002, A003}` ⇒ added `{A001}`.
- `{A001, A002, B001, E001}` → `{A002, E001}` ⇒ removed `{A001, B001}` (flagged: more than one item).
Because a reader may return one tag per read, each inventory is the union over
a 1.5 s window. Which item an RFID ID belongs to is the portal's data.

## 15. How the load-cell verification works

Before opening and after closing, the bin waits (up to 3 s / 6 s) for a
**stable** mass: the window spread below `WEIGHT_STABILITY_THRESHOLD_G` for
`WEIGHT_STABLE_TIME_MS`. Δ = after − before. |Δ| below
`WEIGHT_CHANGE_THRESHOLD_G` = no change; a return expects an increase, a
checkout a decrease. The portal also compares |Δ| with the item's learnt mass
(`weight_check`: MATCH / MISMATCH / LEARNED / NO_SCALE) and alerts staff on a
mismatch. Uncalibrated or unstable = "not weighed": the transaction is still
recorded, without a weight check.

## 16. How the transaction state machine works

```
BOOT → SELF_TEST → IDLE ⇄ OFFLINE (no Wi-Fi) ⇄ FAULT (lid/servo fault)
IDLE --scan--> WAITING_FOR_AUTHORIZATION --portal OPEN_FOR_RETURN--> AUTHORIZED
IDLE --portal OPEN_LID (checkout)----------------------------------> AUTHORIZED
AUTHORIZED (weigh + RFID before) → OPENING (servo press; reed must say OPEN
within 3 s, else LID_POSITION_TIMEOUT_OPEN + servo lockout) → OPEN →
WAITING_FOR_USER (pedal held 8 s) → CLOSING (release; reed must say CLOSED
within 8 s, else LID OPEN / Please close) → VERIFYING (weigh + RFID after,
cross-check) → return: POST /reusable/complete → TRANSACTION_VERIFIED | _FAILED
                         checkout: AWAITING_TAG_CONFIRMATION (scan the item) →
                         TRANSACTION_VERIFIED | _FAILED → IDLE
```
VERIFIED = the portal recorded it **and** the local cross-check found nothing
(lid opened and closed, weight in the expected direction, RFID agrees) **and**
the portal's weight check is not MISMATCH. Anything else = flagged for review,
with the reasons (`LID_LEFT_OPEN`, `NO_WEIGHT_CHANGE`, `WEIGHT_WRONG_DIRECTION`,
`RFID_NO_CHANGE`, `MULTIPLE_ITEMS_CHANGED`, `WRONG_ITEM`, `SENSOR_MISMATCH` ...).
The reasons are also sent to the portal as `local_verification`; today's portal
ignores that field (it changes nothing there).

**Authorisation policy:** the portal decides every opening. With no portal
the bin does not open (no offline authorisation is invented).

## 17. Portal endpoints used (they exist today)

| Call | When |
|---|---|
| `POST /api/access/heartbeat` | every 30 s (registers REUSE_BIN_1, `reusable_bin: true`, component states) |
| `POST /api/reusable/scan` | every NFC scan (with `mass_delta_g` when confirming a checkout) |
| `POST /api/reusable/complete` | after a return's lid cycle (masses before/after, lid opened/closed) |
| `GET /api/access/commands/next` | every 2 s while idle (checkout `OPEN_LID`) |
| `POST /api/access/commands/{id}/progress` | checkout progress |

Not in the portal yet (so not called): an RFID-inventory endpoint
(`PATH_RFID_INVENTORY` is empty).

## 18. Troubleshooting

| Symptom | Check |
|---|---|
| `HX711 not responding` | VCC/GND at the HX711, DT↔GPIO32 and SCK↔GPIO33 not swapped, common GND |
| raw changes but grams `n/a` | not calibrated: `tare`, then `cal <g>` |
| `Only N counts above zero` on `cal` | mass not on the platform, tare not done empty, or E/A wires swapped (raw moves the wrong way) |
| weight never `STABLE` | something touches the platform, vibration, or the stability threshold is tighter than the measured noise |
| `No I2C device answered` | SDA/SCL swapped, no common GND, module not powered |
| LCD found but blank | contrast potentiometer on the backpack |
| `PN532 not found at 0x24` | S1 ON / S2 OFF, power, 1 s after power-up |
| servo jitters / ESP32 resets when it moves | servo powered from the ESP32 or a weak 5 V supply; separate 5 V, common GND |
| `LID_POSITION_TIMEOUT_OPEN` | linkage slipped or open angle too small; reed not seeing the magnet; then `servo clear` |
| lid OPEN/CLOSED inverted | `REED_LEVEL_WHEN_CLOSED` |
| `[BACKEND] ... -> 401` | device key not issued / not in `secrets.h` |
| `[BACKEND] ... -> -1` | Wi-Fi down, laptop not at 192.168.1.200, portal not running |

