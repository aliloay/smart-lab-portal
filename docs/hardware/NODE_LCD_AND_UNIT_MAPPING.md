# Node LCD, unit and payload mapping (2026-11-16)

Traced from the firmware source in `firmware/` and the portal routes. **Nothing here was measured on hardware**: the
sources say "compiled, not yet run" for the bin nodes, and every number marked START/VERIFY in the firmware is a
placeholder until measured. Firmware was not changed or flashed.

Label meaning: **measured** = a sensor reads it; **computed (firmware)** = the ESP32 derives it; **derived (backend)** = the
portal derives it from what the node sent.

## 1. Environment node `ENV_LAB01` (firmware `firmware/SmartLab_Environment_Node/`, ENVIRONMENT_NODE 0.1.0)

No LCD and no display: the only outputs are the serial console (115200 baud) and the portal.

| Quantity | Sensor / pin | Raw -> value | Unit sent | Portal field | Source | Notes |
|---|---|---|---|---|---|---|
| Temperature | DHT22, GPIO 4 | library `readTemperature()`, range-checked -40..80 C, read every 2.5 s | `"C"` in `readings[]` key `temperature` | lab environment `temperature` | `env_sensors.h` DHT block, `env_network.h:114` | last valid value kept with its age, never replaced by 0; stale after 15 s (`DHT_STALE_MS`); 3 failures -> SENSOR_FAILURE |
| Humidity | DHT22, GPIO 4 | `readHumidity()` | `"%"` (relative humidity) | `humidity` | same | same validity rules |
| Smoke / gas | MQ-2 AO via 10k/15k divider, GPIO 39 | filtered mV vs 30 s clean-air baseline -> ratio; level 0 normal / 1 warning (ratio >= 1.5 AND rise) / 2 critical (>= 2.0 AND rise) | `"state"`: 1 if level >= WARNING (or DO pin), else 0 | `smoke` | `env_sensors.h` MQ block, `env_network.h:115` | **NOT ppm**: no calibration exists (comment in firmware). The portal gets a 0/1 state only; raw mV/ratio stay on the serial console |
| Flame | 5-channel IR board GPIO 13/32/33/35/36 | confirmed when >= 40 % of samples in 300 ms saw IR; cleared after 3 s | `"state"` 0/1 (any channel) | `flame` | `env_sensors.h` flame block | per-channel values not sent |
| Motion | PIR 1 / PIR 2, GPIO 27 / 26 | 60 s warm-up, 100 ms debounce, 5 s hold | `"state"` 0/1 (either PIR) | `motion` | `env_sensors.h` PIR block | not an alarm by itself (advisory when the lab is closed) |

Reporting: `POST /api/access/telemetry` every 10 s (`SNAPSHOT_INTERVAL_MS`) and immediately on a change; `POST
/api/access/heartbeat` every 30 s with component health (`dht22`, `mq_1`, `pir_1`, `pir_2`, `flame`: true / false / null =
not fitted). Backend publishes `env_update` (and `hazard` for smoke/flame alarms) over `/ws/activity`
(`backend/app/api/routes/access.py:352`, `backend/app/ws/manager.py`). Stale/offline: heartbeat age
(`DEVICE_STALE_SECONDS`). Disclaimer in the firmware README: indicators, not a certified fire or gas detector.

## 2. Consumables bin `BIN_NODE_1` (firmware `firmware/SmartLab_Consumable_Bin/SmartLab_Consumable_Bin.ino`, bin-0.3, bin code `BIN-R10K`, lab `LAB_01`)

The node measures **one thing: mass in grams** (HX711, DT GPIO 25 / SCK GPIO 26). It does **not** measure resistance,
capacitance or LED parameters. "resistors, capacitors, LEDs" are parts the bin holds; a count is a *derived estimate*.

| Quantity | How | Unit | Portal field | LCD (16x2, I2C GPIO 21/22) | Source |
|---|---|---|---|---|---|
| Mass | HX711 raw -> median of 5 -> average of 20 (~2 s) -> `(raw - offset) / scale` | grams (2 decimals sent) | `POST /api/inventory/measurements` `readings[].mass_g` -> bin `last_mass_g` | line 2: `<g, 2 dp> g` | `.ino` pipeline lines 56-70, `sendMass()` |
| Stable flag | spread <= 0.08 g for 1.5 s | bool | not sent (only stable values are posted) | `..` appended while not stable | `.ino` 268-276, `drawLcd()` |
| Piece count | **derived (backend)**: `qty_est` from the bin's calibrated unit mass | pieces | bin `qty_est` / `qty_err` | `~N` after the grams, from the portal's reply | `inventory.py` `post_measurements`, `.ino` `sendMass()` |
| Item name | portal reply `item_name` | text | bin `item_name` | line 1 (else the bin code) | `drawLcd()` |
| Calibration | `tare` then `cal <grams>`; scale (counts/g) + offset in flash | counts/g | heartbeat `calibrated` | `NOT CALIBRATED` until done | `.ino` 171-190, 353-377 |

LCD states (exact): line 1 = item name or `BIN-R10K`; line 2 = `NOT CALIBRATED` | `SETTLING...` | `OVER 1000 g!` | `<v> g[ ~N][ ..]`; a trailing
`!` means the last post to the portal failed. Rated load 1000 g (`MAX_LOAD_G`, the cell's capacity, not its calibration).
Posts only a stable value that moved >= 0.05 g (`SEND_DELTA_G`); heartbeat every 30 s with `hx711`, `calibrated`, `lcd`.
Portal: staff Inventory page, live via `inventory_update` (refetch). Overload and not-ready readings are never reported.

Difference to know: **the LCD shows the value after a 0.04 g display deadband; the portal gets that same displayed value**
(`shownG`), so they should agree to 0.01 g. A `~N` that differs between LCD and portal means the portal's unit mass changed
after the last post.

## 3. Reusables bin `REUSE_BIN_1`

**Which firmware is on the board?** The portal's last heartbeat from this node (30 Oct) reported `firmware_version = reuse-mod-0.1`, i.e. the **Modular**
firmware (`firmware/SmartLab_Reusable_Bin_Modular/`, `config.h`: `DEVICE_ID = "REUSE_BIN_1"`, `LAB_ID = "LAB_01"`). The older single-file firmware
(`firmware/SmartLab_Reusable_Bin/`, reuse-0.3, kept for reference) uses different pins and still has `LAB_ID = "BENCH"`. Both say "not yet run on hardware" in their
own README; confirm the banner on the serial console at the lab before comparing values.

**Lab identity (traced).** Heartbeat `lab_id` is a lab *code* looked up in `Lab.code` (`access.py` `heartbeat` -> `get_lab_by_code`). `LAB_01` = lab id 1 "Robotics Lab"
(live DB). Modular `LAB_01` -> lab 1 -> node row `REUSE_BIN_1` (lab 1) -> Smart-bin card of lab 1. **No `BENCH` lab exists**: a heartbeat saying `BENCH` is answered
`{"status":"unknown_lab"}` and changes nothing (tests: the lab-code tests in `backend/tests/test_reusable.py`). So **no reflash and no database change is needed if the
Modular firmware is the one on the board**; only the legacy file would need `LAB_ID = "LAB_01"` before it were ever flashed.

### 3a. Modular firmware (reuse-mod-0.1) - pins and thresholds from `src/config.h` (values marked VERIFY there are placeholders)
| Item | Pin / source | Notes |
|---|---|---|
| Load cell HX711 | DT GPIO 32, SCK GPIO 33; capacity 1000 g | stable = spread <= 2.0 g for 1 s (VERIFY); a weight change counts from 10 g (VERIFY); boot zero only if < 10 g at power-on |
| LCD 16x2 I2C backpack | SDA 21 / SCL 22 (address scanned at start) | idle text `SMART BIN` / `Ready` |
| NFC PN532 | its own I2C bus SDA 18 / SCL 19 | the tag UID is sent to the portal, never displayed |
| Servo | GPIO 25 (signal only, 5 V external) | presses the bin's own button; no feedback of its own |
| Lid reed | GPIO 27 to GND, pull-up | the only physical lid feedback |

| Flow | Calls | LCD text |
|---|---|---|
| Heartbeat (registers / keeps online) | `POST /api/access/heartbeat` | - |
| Tag scan | `POST /api/reusable/scan` | `lcd1` / `lcd2` from the portal reply (e.g. `UNKNOWN TAG`, `TAKE VIA PORTAL`, `WRONG ITEM`, `CHECKED OUT`) |
| Return (after OPEN_FOR_RETURN) | `POST /api/reusable/complete` (lid opened/closed, mass before/after in grams) | `VERIFYING` / `Please wait...`, then portal text; `LID OPEN` / `Please close` |
| Portal checkout | polls `GET /api/access/commands/next` (OPEN_LID), then `POST /api/reusable/checkout-complete`; progress via `/api/access/commands/{id}/progress` | as above |
| Unexplained weight change | `POST /api/reusable/weight-change` | - |
| Offline | - | `NO CONNECTION` / `Scan again` |

### 3b. Legacy single-file firmware (reuse-0.3) - for reference only
PN532 + LCD on I2C 21/22, servo GPIO 13, reed GPIO 27, HX711 DT 25 / SCK 26; idle `SMART BIN` / `SCAN AN ITEM` (or `READER OFFLINE`); the same API calls.

### 3c. What the portal can honestly say (both firmwares)
After each accepted report the backend pushes `reusable_update {lab_id, kind}` (no UID, name or weight); the Smart-bin card refetches `/api/reusable/items` fresh.
Known: node online/offline, an item's status after a scan/return, "weight changed without a request". **Not known:** how many items are inside the bin, and whether the servo
moved (commanded only; the reed is the only physical feedback).

## 4. Door / Master node `MASTER_LAB01` - TFT (160x128 colour ST7735, `INITR_BLACKTAB`, rotation 3), `firmware/SmartLab_Master_Portal/SmartLab_Master_Portal.ino`

Documentation only: nothing here changes access logic. The screen is chosen in `updateDisplay()` (line ~1404): `emView` (admin emergency) wins over `state`.
Wrapped text lines are at most 25 characters (`wrapText`).

| Screen (function) | Shown when | Exact text | Data source |
|---|---|---|---|
| Boot (`screenBoot`) | power-up | `SMART LAB` / `Starting...` | local |
| Idle (`screenIdle`) | `STATE_IDLE` | `WELCOME`, `Scan your QR code`, `or RFID tag / card`, `STEP 1 OF 2`; extra line: `Readers offline - call staff` / `RFID offline - use QR code` / `Camera offline - use card`; an admin message (up to 3 lines) replaces the note | local reader/camera health (`rfidLinkDown`, `cameraHealthy()`); `emMessage` from the portal's emergency poll |
| Checking (`screenChecking`) | while the portal answers a booking QR | `CHECKING`, `Booking QR code found`, `One moment...` | local, drawn before the reply |
| Step 1 OK (`screenStep1Ok`) | `STATE_WAIT_FINGERPRINT`, before the verify prompt | label `QR CODE OK` / `RFID OK` + the person's display name | `step1Label` (local); name from the door's local user table |
| Verify (`screenVerify`) | `STATE_WAIT_FINGERPRINT` with prompt | `VERIFY`, name, `Look at the camera`, `or place your finger`, `STEP 2 OF 2`, a shrinking bar (20 s; amber in the last 5 s) | local timer `FINGERPRINT_TIMEOUT_MS` = 20000 ms |
| Granted (`screenGranted`) | `STATE_ACCESS_GRANTED`, `STATE_DOOR_UNLOCKED_WAIT_OPEN` | with a stored photo: name band + `ACCESS` `GRANTED`; without: header `DOOR UNLOCKED`, check mark, `ACCESS` `GRANTED`, name | local flash (`user_photos.h`); the unlock is the door controller's own decision |
| Door open (`screenDoorOpen`) | `STATE_DOOR_OPEN_WAIT_CLOSE` | `DOOR OPEN`, `Please close the door`, `behind you`; after 30 s (`DOOR_HELD_OPEN_MS`): `DOOR HELD OPEN`, `CLOSE THE DOOR`, `Open for too long`, `Staff have been notified` | door sensor (local) |
| Denied (`screenDenied`) | `STATE_ACCESS_DENIED`, 2 s (`DENIED_DISPLAY_MS`) | header `DOOR LOCKED`, `ACCESS` `DENIED`, plain reason | `deniedReason` mapped by `friendlyReason()`: `Face does not match`, `Fingerprint mismatch`, `Timed out - try again`, `Card not recognised`, `QR not recognised`, `QR was replaced`, `Booking not started` / `has ended` / `cancelled` / `not confirmed`, `Booked for other lab`, `Account disabled`, `No biometric enrolled`, `Not enrolled at door`, `Portal unreachable`, `Portal disabled`; an unknown code is shown as received |
| Alarm (`screenAlarm`) | `STATE_DOOR_ALARM` | `! SECURITY ALERT !`, `FORCED ENTRY`, `Door opened while locked`, `Staff have been notified`, `Please close the door` | door sensor vs. lock state (local) |
| Emergency (`screenEmergency`) | `emView` 1 or 2 | `! EMERGENCY !`; `DOOR OPEN` (+ `for N min` or `until staff lock it`) or `LAB LOCKED` (+ `set by the lab admin`); the admin's message, else `Please leave calmly` / `No entry at the moment` | portal `GET /api/access/emergency?device_uid=...` (polled); applied by the door controller itself |

Also on the Master: a read-only tablet page (`tablet_display.h`: GET `/`, `/state`, `/photo`; no route can change state or open the door) that mirrors the same state as JSON.
Portal calls seen in the source: `/api/access/validate-qr`, `/grant`, `/deny`, `/events`, `/heartbeat`, `/commands/next`, `/commands/{id}/progress`, `/emergency`.

**Unknown / to see at the lab (not inferred):** exact colours and font rendering; what a malformed portal reply looks like beyond the raw code; how long `Checking` lasts on a slow network.
Lab visual check without operating the door: read the idle screen (`WELCOME` / `STEP 1 OF 2`) and any offline note, and compare the portal's door-state tile with the TFT.
Do not present cards, QR codes or fingers, and do not power-cycle the Master without the owner.

## 5. Lab comparison checklist (LCD vs portal, same moment)

1. Put the phone camera on the LCD and the portal page side by side; note the clock time of each frame.
2. Consumables: place a known mass; wait until `..` disappears; LCD grams must equal the portal bin's last mass to 0.01 g.
   `~N` equals the portal's `qty_est`. Remove the mass; both return to ~0.00 g.
3. Environment: breathe on the DHT22; temperature / humidity rise on the portal within ~10 s (snapshot) or sooner on a change; no gas ppm exists.
4. Reusables: scan an untagged card -> portal "last unknown"; scan a tagged item -> LCD text and the portal card change without a refresh.
5. Record per node: LCD value, portal value, both times. Differences go in the report; do not adjust calibration at the lab without the owner.
