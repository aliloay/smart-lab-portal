# Thesis corrections, ready to paste (prepared 19 Nov 2026)

For `C:\Users\dell\OneDrive\Desktop\Bsc\thesis_overleaf\revised\appendix.tex`. **The thesis files were not edited.**
Each block replaces the one named. Sources were checked on 19 Nov against the deployed firmware and the door wiring record.

## 1. Table `tab:pins_consumable`
Source: `firmware/SmartLab_Consumable_Bin/SmartLab_Consumable_Bin.ino` lines 53-55 (`HX_DT_PIN = 32`, `HX_SCK_PIN = 33`, `I2C_SDA = 21, I2C_SCL = 22`).
Replace the two body rows with:
```latex
        HX711 load-cell amplifier & DT GPIO32, SCK GPIO33 & One load cell under the bin (same wiring as the reusable bin) \\
        I2C LCD & SDA GPIO21, SCL GPIO22 & Shows count and status \\
```

## 2. Table `tab:pins_reusable`
Source: `firmware/SmartLab_Reusable_Bin_Modular/src/config.h` lines 38-46 and 76 (`PIN_HX711_DT 32`, `PIN_HX711_SCK 33`,
LCD on `21/22` = I2C bus 0, PN532 on its own bus `Wire1` `SDA 18 / SCL 19`, address `0x24`, `PIN_SERVO 25`, `PIN_REED 27`).
Replace the five body rows with:
```latex
        PN532 NFC reader & SDA GPIO18, SCL GPIO19 & Own I2C bus (Wire1), address 0x24 \\
        16$\times$2 I2C LCD & SDA GPIO21, SCL GPIO22 & I2C bus 0, separate from the PN532 \\
        MG90S servo (lid button) & GPIO25 & Signal only; powered from the 5~V branch rail \\
        Reed switch (lid closed) & GPIO27 & Switch to GND, internal pull-up \\
        HX711 load-cell amplifier & DT GPIO32, SCK GPIO33 & Weighs before and after each lid cycle \\
```
(The old values GPIO25/26 for the HX711, GPIO13 for the servo and a shared PN532/LCD bus came from the retired bench sketch.)

## 3. Evidence tracker (`tab:evidence`): two rows out of date
Door relay row. Source: `docs/hardware/DOOR_MASTER_WIRING.md`, section "Relay drive as rebuilt on 2026-11-08".
```latex
    Fail-secure lock and relay drive & NO contact; since 8 Nov an NPN stage, relay on 5~V; GPIO26 3.18--3.2~V when locked & \texttt{DOOR\_\allowbreak{}MASTER\_\allowbreak{}WIRING.md} & Verified on the bench (trial count not recorded) \\ \hline
```
Backend tests row. Source: full suite on 19 Nov 2026 (`tools/ops/test_backend_fast.ps1`, commit `333b128`).
```latex
    Backend automated tests & 856 passed, 3 skipped & Final test run, 19 Nov 2026 & Verified in software \\ \hline
```

## 4. Door chapter text (Chapter 3 / Results), wherever the BC557 stage or the 12 V relay supply is described
Suggested sentence:
> On 8 November 2026 the relay drive was rebuilt: the relay module now runs from 5 V and GPIO26 drives its input through
> a base resistor and an NPN transistor, replacing the earlier BC557 PNP stage. A pull-up from GPIO26 to 3.3 V holds the
> locked level while the ESP32 resets; the pin measures 3.18--3.2 V when locked. The lock remains on the relay's normally
> open contact, so it stays locked when the controller loses power.

Values not yet recorded (do not invent them): the transistor part number and the resistor values; the number of trials.

## 5. Still open for the thesis (need measurements first)
Door scan-to-unlock time, cold start, power-cut recovery, per-node power draw, 30-minute offline run, priced bill of
materials. Steps in `HARDWARE_TEST_PLAN.md`.
