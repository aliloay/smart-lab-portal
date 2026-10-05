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

---

## Door - lock on NO, buzzer, speaker and tablet sound (MASTER_LAB01)

### 2026-10-04/05 - Lock moved to the relay's NO contact
```
Hardware:          12 V solenoid lock; 12 V relay module (high-triggered, VCC + COM on 12 V);
                   BC557 PNP; 3.3 k, 15 k; 470 uF 25 V electrolytic across +12 V / GND at the relay
Wiring:            Lock on NO (was NC). Relay IN fed from 3V3 through the BC557:
                   E -> 3V3, C -> IN, B -> 3.3 k -> GPIO26, 15 k B-E (off during reset/flash).
                   Final BC557 orientation as fitted on the bench - photo to be added.
Firmware:          SmartLab_Master_Portal, GPIO26 HIGH = LOCKED, LOW = UNLOCKED (PNP inverts)
Test conditions:   Bench at home, 12 V adapter (label not yet recorded), ESP32 on laptop USB
Measurements:      Multimeter (model not recorded), DC V:
                   COM-GND 12.1 V at rest; 12.03 -> 11.95 V during an unlock (470 uF fitted).
                   GPIO26 straight to IN: NO-GND showed 12 V for ~1 s, then 0 V; lock did not open.
                   IN tied to 3V3 or 5V by a jumper: lock opened.
                   Via BC557 (first orientation): IN 0 -> 1.23 V during an unlock; lock did not open.
Result:            PASS - locked at idle, on denial and while reflashing; opens on a grant.
Failure:           On NC (old wiring) any reset, flash, boot or 12 V dip (buzzer) unlocked the door.
                   On NO driven straight from GPIO26 the relay lit its LED but did not close NO.
Fix:               Lock to NO + relay levels inverted; relay IN driven from 3V3 via the BC557.
Final state:       HARDWARE VALIDATED on the bench (lock behaviour). Brownout resets seen at
                   11:50 on 2026-10-05 were attributed to plugging/unplugging - watch for repeats.
```

### 2026-10-05 - Buzzer, LEDs and tablet sound
```
Hardware:          Buzzer + red LED on GPIO21 (one NPN stage); green LED GPIO14; red LED GPIO15;
                   PAM8403 + 3 W / 8 ohm speaker (removed after the tablet sound worked; 5 V supply 4.97 V)
Firmware:          DENY_ALERT_ENABLED = true, DENY_BEEP_MS = 600; forced entry and evacuation pulse
                   the buzzer. Tablet page (http://192.168.1.151/) speaks the prompts with the
                   viewing device's own voice after one tap ("Sound - this device"); alarms play on
                   the tablet (words, then siren) AND at the door.
Measurements:      none (behaviour test)
Result:            PASS (owner, bench): denial beeps and stays locked; forced entry pulses until the
                   door closes; tablet speaks prompts and alarms (laptop speakers).
Failure:           Tablet silent at first - laptop audio was going to an HDMI screen without speakers.
Final state:       HARDWARE VALIDATED on the bench. Not yet tested: evacuation from the portal on
                   this build; a dedicated tablet / Bluetooth speaker at the door.
```

### 2026-10-04 - Door-close lag
Camera status polling moved off the door loop into a background task (a slow ESP32-CAM had held the
loop up to ~1.6 s, so a closing door was acted on ~1 s late - log 00:46:51 sensor CLOSED, 00:46:52
relock). Owner confirmed the welcome screen now returns promptly. Not timed with an instrument.
