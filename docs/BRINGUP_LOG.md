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

Firmware ENVIRONMENT_NODE 0.1.0 (rewrite of the env-0.2 draft). Sensors: DHT22, PIR x2, MQ-2 (AO via
10k/15k divider), 5-channel flame board; enabled one at a time at run time (`fit <sensor> on`, kept in
flash). Each output level is measured before its GPIO is connected (wiring: firmware README).

2026-10-05 14:12 - flashed over COM7 (CH340), board ESP32-D0WD-V3 rev 3.1, MAC 20:50:0d:51:24:b4,
4 MB flash, no PSRAM (factory AT firmware before). First boot: banner OK, reset reason power-on, no
brownout / crash / watchdog; self-test reported all sensors NOT FITTED (none enabled yet); Wi-Fi
Smart_Lab joined as 192.168.1.152, RSSI -21 dBm, ~10 s after boot (second attempt).

2026-10-05 15:43-15:47 - DHT22 (3-pin module `- out +`: + -> 3V3, out -> GPIO4, - -> GND), env-0.1.0:
- Idle readings 28.6-28.7 C, 41.4-42.8 %RH, every 2.5 s, 0 failed reads (room, no reference instrument).
- Breath test (owner breathed on the sensor ~20 s, from ~15:44:08): RH 41.5 -> 91.0 % within one
  10 s log step, peak 99.9 %; T 28.7 -> 34.5 C peak. HUMIDITY_HIGH at 15:44:13 (71.9 %),
  HUMIDITY_NORMAL at 15:45:58 (62.3 %, below the 65 % hysteresis), values back to ~51 % by 15:46:43.
- Unplug test: `out` removed -> 3 failed reads (2.5 s apart) -> SENSOR_FAILURE at 15:46:18; failures
  continued while unplugged, last valid values kept (not zeroed); reconnected -> SENSOR_RECOVERED 15:46:28.
- Result: PASS (reading, threshold events with hysteresis, failure detection and recovery).
  Accuracy NOT assessed - needs a reference thermometer/hygrometer.
- Part: DHT22/AM2302 3-pin module, mostelectronic.com SKU ME-19242. SELLER spec (not measured here):
  supply 3.3-5.5 V, ~0.2 mA average, "no external components needed" (pull-up on the module),
  accuracy +/-0.5 C and +/-2 %RH (+/-5 % at extremes), min. sampling 2 s, range -40..80 C, 0-99.9 %RH
  (the listing also says -40..125 C once - the AM2302 datasheet range is -40..80 C).

2026-10-05 18:32-18:36 - PIR 1 + PIR 2 (HC-SR501-type "MH" boards: BISS0001, on-board 3.3 V regulator,
pins VCC/OUT/GND, two 1 MOhm pots, H/L jumper). VCC -> buck 5 V, GND common, OUT -> GPIO27 (PIR1) /
GPIO26 (PIR2). OUT voltage not measured by the owner (output is fed from the on-board 3.3 V regulator).
- Warm-up 60 s, then SENSOR_READY for both (18:34:30). A manual EN reset at 18:33:29 restarted the warm-up.
- PIR1: MOTION_STARTED/STOPPED pairs 18:34:40-49, 18:35:09-16, 18:35:48-55 (motion held 7-9 s after the
  last movement = module delay ~2-4 s + 5 s firmware hold). PIR2: 18:36:03-12. One event per change.
- Zones reported independently; PIR1 also triggered once during the PIR2 test (cover/position).
- Firmware quirk found: motion present at the end of warm-up is taken silently (MOTION_STOPPED pir_2 at
  18:36:02 without a STARTED). Fix pending in the next flash.
- Result: PASS (detection, state changes, independent zones). Range/angle NOT measured yet (lab walk test).

2026-10-05 20:46-21:13 - 5-channel flame board (round, H1..H5 IR receivers, header GND VCC D5A5..D1A1,
one 10 k multi-turn threshold pot "W103"), VCC -> 3V3, GND common.
- First wiring (D1..D5 -> GPIO13/16/17/18/19, digital): CH2-5 read LOW permanently. All channel LEDs were lit
  with no flame -> threshold pot turned until they went off; CH2-5 still LOW.
- Diagnosis (one variable at a time): GPIO16 with its wire removed read HIGH (pin fine, so the board output
  pulled it low); D2A2 measured on GPIO34 (ADC): ~0 V idle, 0.17-0.32 V with a lighter at 30-50 cm, 3.15 V once.
  => D1A1 is a comparator output (3.3 V idle, 0 V on flame); D2A2..D5A5 are ANALOG (IR raises the voltage).
- Fix (env-0.1.0 + per-channel mode): CH1 GPIO13 digital; CH2..CH5 -> GPIO32/33/35/36 (ADC1), detect > 160 mV.
- Idle: CH2-5 at the ADC floor (0.142 V), CH1 clear, no spontaneous detection.
- Lighter test 21:10:18-21:11:06: every channel FLAME_DETECTED once; peaks CH2 3.13 V, CH3 2.92 V, CH4 3.02 V,
  CH5 2.93 V; distant flame 0.17-0.36 V; neighbouring channels pick up 0.2-0.3 V (overlapping cones);
  each FLAME_CLEARED ~3 s after the flame left.
- Mapping test 21:12:20-21:12:37 (lighter H1 -> H5 in turn): strongest channel stepped CH1, CH2, CH3, CH4, CH5
  => Hn = DnAn = flame_n (direction of a fire is known from the channel).
- Result: PASS (detection, clearing, channel mapping). Not yet measured: detection distance per channel,
  false positives over a long idle run (lamps / sunlight), response time with an instrument.

2026-10-05 21:44-22:02 - MQ-2 module (front: MQ gas element "Flying-Fish"; back: "MH MQ Sensor" carrier, LM393,
pins AO DO GND VCC - the earlier "MH" photo was the back of this same module). VCC -> buck 5 V, GND common,
AO -> 10 k -> ADC pin, 15 k pin -> GND (soldered), DO not connected.
- First try (GPIO34): readings jumped 0 V <-> full scale every second, false GAS_CRITICAL events. Cause 1: AO
  was wired to the divider junction (10 k bypassed) - rewired. Still jumping; moved to GPIO39 ("VN") - same,
  and the EMPTY GPIO34 spiked at the same moments => common disturbance (ground/supply), not the pin.
  The owner then reworked the wiring; afterwards GPIO39 read steady 0.22-0.24 V and GPIO34 flat. The exact
  final change was not recorded. MQ was disabled in firmware during the fault, then re-enabled (fresh warm-up).
- Warm-up 21:56:23-21:59:23 (3 min, prototype value): pin 0.242 -> 0.221 V, smooth.
  Baseline 21:59:23-21:59:53: 216 mV at the pin (AO ~0.36 V). Local prototype baseline, not a calibration.
- Hand-sanitizer test (tissue 5-10 cm): rise from 22:01:19, filtered 321 mV = 1.50 x baseline ->
  GAS_WARNING 22:01:43; back below 1.3 x -> GAS_NORMAL 22:01:52. CRITICAL (2 x) not reached.
- Result: PASS (warm-up, baseline, warning and recovery, one event per change). Response modest; the sensor had
  minutes of heating only (datasheets ask for a long pre-heat before first use). No ppm - uncalibrated.
- Firmware improvement noted: the baseline accepted noisy samples during the wiring fault - add a stability
  check (reject a baseline whose samples spread too much).

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

### Why the BC557 was needed (explanation for the thesis)
It was a DRIVE-CURRENT problem at the relay module's input - not a voltage problem, and not the 12 V supply.
1. 12 V side healthy: COM-GND 12.03 -> 11.95 V during an unlock; COM shorted to NO opened the lock.
   The 470 uF capacitor therefore did not cause the fix (it remains useful against short dips, e.g. the buzzer).
2. 3.3 V is enough for the module: IN tied to the ESP32 3V3 pin (a jumper) opened the lock.
3. Too little current reached IN: driven from GPIO26 (and through the BC557 while its outer legs were
   reversed) IN reached only 1.23 V - about the forward voltage of the module's input LED with almost no
   current - enough to light the relay LED, not to keep the relay pulled in (NO showed 12 V ~1 s, then 0 V).
4. Fix: the BC557 (PNP) feeds IN from the 3V3 rail like the jumper did; GPIO26 only switches it through
   3.3 k (~1 mA base current). 15 k base-emitter keeps it OFF whenever the ESP32 is not driving GPIO26
   (reset, flash, boot) -> relay off -> locked. The PNP inverts: GPIO26 HIGH = locked, LOW = unlocked.
Not isolated: WHY GPIO26 alone could not supply the current (pin 26 was never measured under load).
Candidates: a poor contact in that wire, or the module's input needing more than the pin delivered;
the transistor removes both.
NC -> NO: on NC the coil had to stay ON to keep the door locked (any reset / flash / dip opened it -
fail-open); on NO the coil is OFF while locked, so any failure leaves the door locked (fail-secure).

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
