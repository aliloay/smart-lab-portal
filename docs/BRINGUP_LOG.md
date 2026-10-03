# Hardware bring-up and validation log

The record behind thesis Chapter 4. Rules:

- Only values that were **measured**, with the instrument and conditions. An empty
  cell means "not measured yet" - never fill it from a datasheet or an estimate.
- A step is **HARDWARE VALIDATED** only after its physical test passed here.
  Until then the subsystem is **SOFTWARE VERIFIED, HARDWARE NOT YET VALIDATED**.
- Acceptance criteria below are the test's pass/fail rule, not specifications.
- Raw serial logs: `tools/bringup/logs/` (see `tools/bringup/README.md`).

## Instruments

| Instrument | Make / model | Range / resolution used | Notes |
|---|---|---|---|
| Multimeter | | | |
| Reference scale (for the load cells) | | | |
| Reference thermometer / hygrometer (if any) | | | Without one, DHT22 accuracy cannot be claimed - only repeatability and behaviour |

## Milestone template

```
### <date> - <milestone>
Hardware:          <parts, with labels / models>
Wiring:            <what connects where; photo file names>
Firmware:          <sketch + FIRMWARE string, e.g. env-0.2>
Test conditions:   <supply, ambient, location, duration>
Measurements:      <values + units + instrument>
Result:            PASS / FAIL against <acceptance rule>
Failure:           <what went wrong, if anything>
Fix:               <one change, and why>
Final state:       <what is now validated; what still is not>
```

---

## Phase 1 - Low-voltage power

### P1.1 PSU identification (de-energized)

| Item | From the label / photo |
|---|---|
| Make / model | |
| Input rating (V AC, Hz, A) | |
| Output rating (V DC, A) | |
| 110/230 V selector (if any) and its position | |
| Terminals present (L, N, PE, V+, V-, V.ADJ) | |
| Mains wiring checked (L, N, PE, strain relief, cover) | |

### P1.2 PSU output, no load

Acceptance: positive reading, 11.4-12.6 V (+-5 % of the 12 V label).

| Date | Probe (red / black) | Reading (V DC) | Pass? | Notes |
|---|---|---|---|---|
| | V+ / V- | | | |

### P1.3 WAGO distribution continuity (no power connected)

Acceptance: exactly two isolated groups; no continuity between them.

| From | Terminals with continuity | Resistance (ohm) |
|---|---|---|
| Probes shorted (meter self-check) | - | |
| Input A | | |
| Input B | | |
| Input A to input B | | must be open |

### P1.4 Master switch and fuses (labels)

| Part | Printed rating (V, A, AC/DC) | Fast / slow |
|---|---|---|
| Master DC switch | | - |
| Fuses available | | |

Fuse values per branch are chosen from **measured** branch current (P1.9), not from the PSU rating.

### P1.5 12 V at the distribution and at each branch (no buck load)

| Point | Reading (V DC) | Pass? |
|---|---|---|
| Distribution (+12 V group to GND group) | | |
| Branch 1 Environment, after fuse | | |
| Branch 2 Consumable, after fuse | | |
| Branch 3 Reusable, after fuse | | |
| Branch 4 Door (moved last, after branches 1-3 are validated) | | |

### P1.6 XL4016 set to 5.00 V, no load

Acceptance: 4.95-5.05 V, stable for 1 min, no load connected.

| Buck | Output before adjusting (V) | After adjusting (V) | After 1 min (V) | Warm to the touch? | Pass? |
|---|---|---|---|---|---|
| Environment | | | | | |
| Consumable | | | | | |
| Reusable | | | | | |

### P1.7 Under load (after the node is connected) - later

| Branch | Node current at 5 V (mA) | Input current at 12 V (mA) | 5 V under load (V) | Worst sag during Wi-Fi / servo (V) |
|---|---|---|---|---|
| Environment | | | | |
| Consumable | | | | |
| Reusable | | | | |

---

## Phase 2 - Environment node (ENV_LAB01, lab BENCH)

Sensors are enabled one at a time in the firmware (`HAS_*`), in this order:
DHT22 -> MQ-2 -> flame -> PIR -> leak. Each output level is measured before its GPIO is connected.

| Step | Measured | Result |
|---|---|---|
| DHT22 serial readings (`CSV,dht`) | | |
| Wi-Fi connect, IP, RSSI (`CSV,wifi`) | | |
| Heartbeat + telemetry accepted (`CSV,http` codes, round trip) | | |
| Readings stored in the portal (lab BENCH) | | |
| MQ-2 DO level: clean air / triggered (V) | | |
| Flame module outputs identified + levels (V) | | |
| PIR OUT high level (V) | | |

## Phase 3 - Consumable bin (BIN_NODE_1, bin BIN-R10K, lab BENCH)

| Test | Procedure | Result |
|---|---|---|
| Raw readings, empty platform | `stream`, 60 s | |
| Tare | `tare` | |
| Calibration | known mass, `cal <g>` (mass from the reference scale) | |
| Accuracy / repeatability | per mass: `# ref <g>`, `avg 50`, 3+ repeats -> `loadcell_stats.py accuracy` | |
| Noise | `stream`, empty, 5 min -> `loadcell_stats.py noise` | |
| Drift | `stream` or normal, 1 h -> `loadcell_stats.py drift` | |
| Settling / step response | `stream`, place a mass, keep streaming | |
| Minimum detectable change | smallest added mass reliably seen above noise | |
| Quantity estimate | real count vs `n_hat = round((m - m0) / u)` | |
