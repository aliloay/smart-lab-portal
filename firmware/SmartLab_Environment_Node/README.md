# Environment node (Robotics Lab, System 1) — bench bring-up

Firmware: `SmartLab_Environment_Node.ino` — compiled, **not yet run on
hardware**. Design: `docs/ROBOTICS_LAB_ARCHITECTURE.md` §I. Indicators only;
not a certified fire, gas or safety system.

## Before connecting anything to the ESP32

1. **Buck converter**: set to 5.00 V with no load; measure and note it.
2. **MQ-2**: power at 5 V, wait for warm-up, then measure **DO** with a
   multimeter in clean air and when triggered (lighter gas, briefly, safely).
   - If DO high ≈ 5 V → put a divider in the DO line (e.g. 10 kΩ top,
     20 kΩ bottom ≈ 3.3 V) before GPIO34.
   - Note which level means "detected" → `MQ2_ACTIVE`.
   - Measure how long DO takes to settle after power-up → `MQ2_WARMUP_MS`.
3. **Flame and leak modules**: power at **3.3 V**; check DO level when
   triggered → `FLAME_ACTIVE`, `LEAK_ACTIVE`.
4. **HC-SR501**: power at 5 V; measure OUT high level (expect ≈ 3.3 V; if
   not, divide it) → `PIR_ACTIVE`.
5. **Emergency input**: only through an optocoupler from the existing
   safety signal, with the lab's approval; set `HAS_EMERGENCY = true` after.

## Wiring (ESP32 #1)

| Signal | GPIO | Supply |
|---|---|---|
| DHT22 data | 4 | 3.3 V (check whether the module has its pull-up) |
| MQ-2 DO | 34 (input-only) | 5 V, DO via divider if needed |
| Flame DO | 32 | 3.3 V |
| Water-leak DO | 33 | 3.3 V |
| PIR OUT | 27 | 5 V |
| Emergency (optocoupler out) | 26 | pulled up |

All grounds common. No 12 V on the breadboard.

## Flash and check

1. Copy `secrets.example.h` → `secrets.h` (Wi-Fi `Smart_Lab`, device key).
2. Board **ESP32 Dev Module**, core **3.3.11**. Upload.
3. Serial 115200: expect `[WIFI] Connected: 192.168.1.152`, the initial state
   of each input, and DHT readings.
4. Portal → Laboratories → LAB_01 → Environment: states appear with
   quality *VALID*; trigger each sensor and watch it change (and the live
   monitor tile turn red for smoke / flame / leak / emergency).

## Measurements to record (thesis, §X)

DHT22 vs a reference thermometer/hygrometer, repeatability, update
interval; MQ-2 warm-up and response; detection and false triggers of
flame, leak, PIR; sensor→database latency; behaviour when Wi-Fi or the
laptop drops and comes back. Record what is measured — nothing estimated.
