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

## 3. Reusables bin `REUSE_BIN_1` (firmware `firmware/SmartLab_Reusable_Bin/` reuse-0.3 = the one matching the current portal routes; `SmartLab_Reusable_Bin_Modular/` is a rewrite, not run on hardware)

| Item | Sensor / actuator | Sent | Portal | LCD text | Source |
|---|---|---|---|---|---|
| Tag scan | PN532 on I2C 0x24, NTAG213; repeat of the same tag within 3 s ignored | `POST /api/reusable/scan` `{nfc_uid}` (+ `mass_delta_g` after a checkout) | asset status; unknown tag remembered for staff | the portal reply's `lcd1` / `lcd2`, e.g. `UNKNOWN TAG` / last 8 hex, `TAKE VIA PORTAL`, `WRONG ITEM`, `CHECKED OUT` | `.ino` `handleScan()`; `reusable.py` `_scan_impl` |
| Lid | reed switch GPIO 27 (LOW = closed); servo GPIO 13 presses the bin's own button (0 -> 60 deg, held 8 s) | `lid_opened`, `lid_closed` in `/reusable/complete`; heartbeat `lid_closed` | return recorded only if the lid really opened | `SCAN <item>` / `TO CONFIRM` | `.ino` constants, `lidCycle()` |
| Mass change | HX711 (GPIO 25/26) stable within 1 g for 0.8 s; before/after the lid cycle | `mass_before_g`, `mass_after_g` (grams) | weight check verdicts; unexplained change -> alert via `/reusable/weight-change` | not shown | `.ino` 161, 240-275 |
| Idle / errors | - | - | - | `SMART BIN` / `SCAN AN ITEM` or `READER OFFLINE`; `NO CONNECTION` / `TRY AGAIN`; `NOT RECORDED` / `CALL STAFF`; `TAKE <item>` / `THEN SCAN IT` | `.ino` 97-110, 256, 272, 294, 306 |

Portal live path (new 2026-11-16): after each accepted report the backend pushes `reusable_update {lab_id, kind}`
(no UID, name or weight inside); the Smart-bin card refetches `/api/reusable/items` fresh. **What the portal can honestly say**: node online/offline,
the item's status after a scan/return, and "bin weight changed without a request". It does **not** know a count of items inside the bin,
and servo state is *commanded*, never confirmed (only the reed gives physical feedback).
**Check before the lab test**: the firmware file sets `LAB_ID = "BENCH"`; the live DB has the node in lab 1 (last seen 30 Oct). If the board runs
this file as is, its heartbeat names a lab the portal may not have (the consumables firmware had the same note and was changed to `LAB_01`).

## 4. Door / Master node `MASTER_LAB01` (firmware `firmware/SmartLab_Master_Portal/`) - read-only notes, not remapped here

Local display is a 160x128 colour TFT (ST7735), not an LCD; a read-only tablet page (`tablet_display.h`: GET `/`, `/state`, `/photo`,
no route can change state or open the door) mirrors it. It talks to `/api/access/*` (validate-qr, grant, deny, events, heartbeat, commands,
emergency). Door state reaches the portal as `door_state`. Screen wording and access rules were **not** re-documented or touched in this pass.

## 5. Lab comparison checklist (LCD vs portal, same moment)

1. Put the phone camera on the LCD and the portal page side by side; note the clock time of each frame.
2. Consumables: place a known mass; wait until `..` disappears; LCD grams must equal the portal bin's last mass to 0.01 g.
   `~N` equals the portal's `qty_est`. Remove the mass; both return to ~0.00 g.
3. Environment: breathe on the DHT22; temperature / humidity rise on the portal within ~10 s (snapshot) or sooner on a change; no gas ppm exists.
4. Reusables: scan an untagged card -> portal "last unknown"; scan a tagged item -> LCD text and the portal card change without a refresh.
5. Record per node: LCD value, portal value, both times. Differences go in the report; do not adjust calibration at the lab without the owner.
