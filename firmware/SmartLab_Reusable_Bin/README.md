# Reusable bin node (Robotics Lab, System 3) — bring-up

Firmware `SmartLab_Reusable_Bin.ino` — compiled, **not yet run on hardware**.
Design: `docs/ROBOTICS_LAB_ARCHITECTURE.md` §K–L.

## Wiring (ESP32 #3)

| Part | ESP32 | Notes |
|---|---|---|
| PN532 (I2C, S1 ON / S2 OFF) | SDA 21, SCL 22 | address 0x24; 1 s settle after power-up |
| 16×2 LCD (I2C) | same bus | found by I2C scan; check its pull-ups / supply first |
| MG90S servo signal | GPIO13 | power from the **5 V branch rail**, not the ESP32; bulk capacitor near the servo; measure sag |
| Reed switch (NO, 2×14 mm) | GPIO27 → GND | pulled up; magnet at the reed = lid closed (VERIFY) |

## Set on the actual bin (VERIFY constants)

`PRESS_ANGLE` (just enough to press the push-to-open button), `OPEN_HOLD_MS`
(time the lid stays open for an item), `HOME_ANGLE`, `REED_LID_CLOSED_LEVEL`.
The servo must only press the button: it never carries the bin and never
touches a weighing path.

## Portal setup

1. The node registers itself by heartbeat (`REUSE_BIN_1`, components
   `reusable_bin: true`).
2. Inventory → Reusable items → for each item: hold its NTAG213 at the
   reader (LCD shows UNKNOWN TAG) → **Assign tag → Use last scanned**.

## Flows to test

- **Return:** item checked out → scan it → LCD `RETURNING...` → lid opens,
  item in, lid closes → `RETURN RECORDED`; item AVAILABLE in the portal.
- **Checkout:** person inside the lab → Lab page → Smart bin → **Take** →
  bin opens (LCD `TAKE <item>`) → take it and scan it → `CHECKED OUT`.
  A different item's tag shows `WRONG ITEM` and changes nothing.

## Measurements (§X)

NFC read success, distance, orientation, duplicate-scan suppression, lid
open/close time and success rate over N cycles, servo current and supply
sag, checkout/return success, end-to-end latency (portal → lid).
