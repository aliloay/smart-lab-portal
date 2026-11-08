---
type: "source-mirror"
source_kind: "documentation"
source_path: "firmware/SmartLab_Consumable_Bin/README.md"
source_hash: "6948ef5eeaf32f27f87bcd21a4933c5b55ed2b94bab2e88e0a532effa0c8b3b6"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `firmware/SmartLab_Consumable_Bin/README.md` - edit the original in the repository, not this note.

Systems: [[Consumables bin]]

## Related
- [[docs_ROBOTICS_LAB_ARCHITECTURE.md]] - mentioned by docs

# Consumable bin node (Robotics Lab, System 3) — bring-up and calibration

Firmware `SmartLab_Consumable_Bin.ino` — compiled, **not yet run on
hardware**. Design: `docs/ROBOTICS_LAB_ARCHITECTURE.md` §J.

## Mechanics first

Removable bin → weighing plate → 1 kg straight-bar load cell (one end bolted
to the fixed base, the load end carries the plate, as its arrow shows) →
fixed base. Nothing else may touch the plate or the bin: walls, screws,
cables, a lid. Check by pressing the base around the plate — the reading
must not move.

## Wiring (ESP32 #2)

| Part | ESP32 |
|---|---|
| HX711 DT / SCK | GPIO25 / GPIO26 |
| HX711 VCC | 3.3 V (or 5 V — then check DT level) |
| LCD SDA / SCL | GPIO21 / GPIO22 |
| LCD VCC | per the backpack: **measure** whether SDA/SCL are pulled up to 5 V before connecting; if so, a level shifter is needed |

At boot the node **scans the I2C bus** and prints every address; it uses
the backpack it finds (0x20–0x27 or 0x38–0x3F), never an assumed one.

## Load-cell calibration (Serial Monitor, 115200, Newline)

1. Platform empty: `tare`
2. Put a **known reference mass** (weighed on a trusted scale) on it:
   `cal 200` (its mass in grams). Saved in flash.
3. `show` prints raw counts, scale and mass.

## Bin calibration (portal → Inventory → the bin)

1. Create the bin with the same code as `BIN_CODE` (default `BIN-R10K`).
2. Empty bin on the platform → its mass is **m₀** (empty bin mass).
3. Weigh e.g. 100 counted parts → **u** = (m − m₀) / 100 (mass per item).
4. Noise test: leave it 10 min, note the spread → **noise**.
5. Enter m₀, u, noise; the quantity estimate and ± band appear.
6. Use **Physical count** to record real counts next to the estimate —
   that is the estimation-error data for the thesis.

## Tests to record (§X)

Calibration points (reference vs reading, error %), repeatability, noise,
drift over hours, step response and settling time, minimum detectable
change, estimate vs real count per component type and fill level.

