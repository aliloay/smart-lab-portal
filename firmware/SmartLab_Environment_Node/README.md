# Environment node (Robotics Lab, System 2) — ENVIRONMENT_NODE 0.1.0

Monitors only: it senses and reports, it never switches anything. Not a
certified fire or gas detector — the MQ-2 and the flame board are indicators.

| | |
|---|---|
| Board | ESP32-WROOM-32 DevKit (ESP32-D0WD-V3 rev 3.1, 4 MB flash, no PSRAM), USB CH340 |
| Build | Arduino CLI, FQBN `esp32:esp32:esp32`, esp32 core 3.3.11 |
| Libraries | Adafruit **DHT sensor library** 1.4.7 + **Adafruit Unified Sensor** 1.1.15 |
| Identity | device `ENV_LAB01` (its own portal key in `secrets.h`), lab `BENCH`, IP 192.168.1.152 |
| Serial | 115200 baud, line ending "Newline" — type `help` |

Files: `env_config.h` (every pin, interval, threshold), `env_events.h`,
`env_sensors.h`, `env_network.h` (Wi-Fi + portal on their own task),
`env_console.h` (diagnostics, self-test, commands). The `env_` prefix is
needed: the ESP32 core has its own `Network.h`, and Windows ignores case.

## Sensors and wiring

Power while bench-testing: ESP32 on USB. 3.3 V from the ESP32 **3V3** pin;
5 V from the environment XL4016 buck (set to 5.00 V with no load first).
**All grounds common** (buck GND = ESP32 GND). Never connect the buck 5 V to
the ESP32 5V/VIN pin while USB is plugged in.

| Component | Pin | To | Volts | Before connecting |
|---|---|---|---|---|
| DHT22 module (`− out +`) | `+` / `out` / `−` | 3V3 / **GPIO 4** / GND | 3.3 | — (pull-up: Ω `out`↔`+` power off, ~10 kΩ = fitted) |
| PIR 1 (zone 1) | VCC / OUT / GND | 5 V / **GPIO 27** / GND | 5 (OUT ≈3.3) | read labels under the dome; measure OUT ≈3.3 V on motion |
| PIR 2 (zone 2) | VCC / OUT / GND | 5 V / **GPIO 26** / GND | 5 (OUT ≈3.3) | same |
| 5-ch flame board | VCC / GND | 3V3 / GND | 3.3 | outputs ≤ VCC by construction |
| | D1A1 / D2A2 / D3A3 / D4A4 / D5A5 | **GPIO 13 / 32 / 33 / 35 / 36** | ≤3.3 | MEASURED: D1A1 digital (LOW = flame), D2A2–D5A5 analog (IR raises the voltage) |
| MQ-2 module | VCC / GND | 5 V / GND | 5 (heater) | photo of the module; 5 V measured |
| | AO | **10 kΩ → GPIO 39 ("VN")**, **15 kΩ GPIO 39 → GND** | ≤3.0 | never direct: AO can reach ~5 V (moved from GPIO 34 on the bench) |
| | DO | **not connected** (would carry 5 V) | — | optional later, needs its own divider |

Not used: the small "MH / MQ Sensor" carrier board (an MQ gas carrier with its
element on the back — kept as a spare).

GPIO choices: no strapping pins (0, 2, 5, 12, 15), no flash pins (6–11), not
1/3 (USB serial), not 14 (PWM at boot). Analog only on ADC1 (32–39): ADC2 is
unusable while Wi-Fi is on. Free for later: 16, 17, 18, 19, 21, 22 (I2C), 23, 25, 34.

## Bring-up: one sensor at a time, no re-flash

Everything starts disabled. After wiring one sensor: `fit dht on` (or `pir1`,
`pir2`, `mq`, `flame`, `flame3` …), then its live view (`dht`, `pir`, `mq`,
`flame`; `stop` to end). The choice is kept in flash. `pins` shows the raw
level of every assigned pin (wiring checks); `status` shows everything.

| Sensor | Behaviour (designed, to be measured) |
|---|---|
| DHT22 | read every 2.5 s; range-checked; 3 failures in a row → `SENSOR_FAILURE`; last valid value kept with its age, never replaced by 0 |
| PIR | 60 s warm-up; 100 ms debounce; motion held 5 s after the module's own delay; one event per change |
| Flame | sampled every 10 ms; confirmed when ≥40 % of the last 300 ms saw IR (a flame flickers); cleared after 3 s with none |
| MQ-2 | 3 min **prototype** warm-up (the datasheet asks for a long pre-heat before first use — not modelled), 30 s clean-air baseline, 1 s moving average; WARNING ≥1.5× baseline, CRITICAL ≥2.0× (or near full scale at once); ~0 V at the pin for 5 s → `FAULT`. No ppm: there is no calibration. |

Events (one per change): MOTION_STARTED/STOPPED, FLAME_DETECTED/CLEARED,
GAS_WARNING/CRITICAL/NORMAL, TEMPERATURE_HIGH/NORMAL, HUMIDITY_HIGH/NORMAL,
SENSOR_READY/FAILURE/RECOVERED, WIFI_CONNECTED/DISCONNECTED.

## Portal (bring-up phase 9)

`LOCAL_TEST_MODE = true` sends nothing. Set false to report through the
portal's existing endpoints (`/api/access/heartbeat`, `/api/access/telemetry`):
temperature, humidity, smoke (gas ≥ WARNING), flame (any channel), motion
(either PIR). Per-channel flame, PIR zones and MQ raw values need a portal
change first.
