# ESP32 and Wi-Fi connectivity audit

- **Time:** 19:10–19:20 local.
- **Method:** read-only. Ping from the laptop, ARP, PnP enumeration, DB SELECT, one GET to the ESP32-CAM `/status`.
- **Not done:** no serial port was opened (COM6 is held by the owner's logger), and nothing was flashed or configured.

## Per-board results

| Device | IP (DB) | Firmware (DB / source) | USB / COM | Ping, 20 packets | Last heartbeat (age) | Sensor / component state |
|---|---|---|---|---|---|---|
| CAM_LAB01 (ESP32-CAM) | 192.168.1.150 | (not reported) / core 3.2.1 build per docs | COM8, CH340 (identity not opened) | **0 % loss**, avg 20 ms, max 54 ms | 4.7 s (via the master's report) | `/status`: online true, last QR 6.1 h ago, last face 2.5 h ago |
| MASTER_LAB01 | 192.168.1.151 | portal-1.2 / `.ino:1817` portal-1.2 ✔ | COM6, CP210x (held by `master_monitor.py`) | **0 %**, avg 8 ms, max 12 ms | 4.7 s | rfid ✔, fingerprint ✔, camera ✔ |
| ENV_LAB01 | 192.168.1.152 | env-0.1.1 / `env_config.h` 0.1.1 ✔ | not on USB | **0 %**, avg 10 ms, max 18 ms | 0.4 s | readings flow (`sensor_readings` 219k rows); no component flags |
| BIN_NODE_1 | 192.168.1.153 | bin-0.6 / source bin-0.6 ✔ | COM7, CH340 (identity not opened) | **0 %**, avg 11 ms, max 26 ms | 0.5 s | hx711 ✔, calibrated ✔, boot_reading "empty", uptime 26,896 s |
| REUSE_BIN_1 | 192.168.1.154 | reuse-mod-0.5 / source ✔ | not on USB | **0 %**, avg 9 ms, max 19 ms | 29.5 s | hx711 ✔, scale and servo calibrated, rfid "RFID_DISABLED" |

- **Answer:** all five are connected on the network (LIVE-VERIFIED).
- **USB:** only three are on USB (COM6 CP210x = master, COM7 CH340, COM8 CH340). This matches the checkpoint (COM6 master, COM7 bin, COM8 CAM).
- **COM7/COM8 identity:** unverified, because I did not open the ports. Opening them can reset the boards through DTR.

### Not available

- **RSSI, gateway, reconnect counters:** not reported by any node's heartbeat. `component_state` has no `rssi` field.
- **Wi-Fi association quality:** therefore not verifiable from the portal. Recommendation: add `rssi` and `reconnects` to the heartbeats at the next planned reflash. This is a firmware change requiring owner sign-off.

## Laptop network (LIVE-VERIFIED)

| Interface | Network | IPv4 | Gateway | Interface metric | Gateway MAC (ARP) |
|---|---|---|---|---|---|
| Ethernet | Smart_Lab router ("Unidentified network") | 192.168.1.200 | none | **10** | 80-7d-14-9f-ea-ba |
| Wi-Fi | Vodafone_5G | 192.168.1.8 | 192.168.1.1 | **35** | 14-89-cb-71-64-2d |

- Both have an on-link route for 192.168.1.0/24. The default route goes via Wi-Fi.
- The ARP entries for .150–.154 are all on the Ethernet interface, which is correct.

### Conflicts

1. **Same subnet and the same gateway IP on two different routers.** It works today only because Windows prefers the lower metric (Ethernet) for on-link 192.168.1.x.
   - Risks:
     - A Vodafone-side device at .150–.154 or .100–.103 is unreachable or ambiguous.
     - Any metric change (driver update, a Wi-Fi adapter with "automatic metric") could send ESP32 traffic to the Vodafone router.
     - Reaching the Smart_Lab router's admin page at 192.168.1.1 depends on the interface.
   - **Recommendation (owner decision):**
     - Long term: re-address the Smart_Lab router (for example 192.168.50.0/24), with firmware IP changes in each `secrets.h` and DHCP reservations.
     - Short term: set static interface metrics and document them.
   - Do not change this before the defense without a tested reflash plan.
2. **192.168.1.100 is used by both FANUC and Hemaly's PC.** See ROBOTS and PC_FLEET (F-03).

## Consumables: empty bin and invalid sensor handling

### From code and data (VERIFIED)

- The node reports `hx711` (sensor alive), `calibrated` and `boot_reading`.
- The portal computes stock = (mass − item tare) ÷ unit mass.
- When the node is offline, the device state becomes OFFLINE after 90 s. The bin card uses the device state, plus `last_measured_at` for the measurement's age.
- An invalid HX711 (`hx711:false`) raises a component alert, keyed by the open alert (`devices.py` component section), rather than being read as zero.

### Today's data contradicts "no stock"

| Value | Grams |
|---|---|
| `last_mass_g` (17:17 UTC) | 175.67 |
| Selected item "Screws" tare | 143.65 |
| Bin tare | 144.318 |
| Bin notes ("Cup tared EMPTY") | 128.63 |

- (175.67 − 143.65) ÷ 0.5225 ≈ **61 units**, which equals `stock_max` 60.
- Either items or another object are on the scale, or the tare is wrong. **A physical check is needed** (F-10).
- The resistor item (0.199 g/unit, noise 0.04 g) caused 54 "added/taken 1 pcs" notifications in 24 h. This is noise-level flapping.

### Cases needing a hardware test

- Valid zero (empty cup).
- Load cell unplugged → expect the `hx711:false` alert, not "0 left".
- Uncalibrated → expect a "calibration required" state.
- Node power-off → OFFLINE after 90 s.
- See OWNER_ACTIONS_AND_HARDWARE_TEST_PLAN.md.

## Door hardware

- **Problem:** the PN532 freezes at relock. Per the owner's 21 Nov measurement (HISTORICAL), the relock guard held 7/8 cycles and froze at the 8th. The guard is documented as a workaround at `SmartLab_Master_Portal.ino:1106`.
- **Proposed fix:** a 1N4007 flyback diode across the lock coil, plus a new buzzer. NEEDS HARDWARE.
- I did not operate the lock.
- The safe procedure is in OWNER_ACTIONS_AND_HARDWARE_TEST_PLAN.md.

## ESP32-CAM core 3.2.1

- **Documented** in `docs/DOOR_SYSTEM.md`, the checkpoint and `MEASUREMENTS_2026-11-21.md`. The toolchain is at `D:\SmartLabData\arduino_core321`.
- **Not enforced** in source: there is no `ESP_ARDUINO_VERSION` guard (F-20).
- **Security:** `/status` is unauthenticated and returns the last booking QR token (redacted in this report), which stays reusable for the whole booking window (F-08).
