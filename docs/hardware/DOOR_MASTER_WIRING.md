# Door node (MASTER_LAB01) - complete wiring as recorded

Compiled 2026-10-20 from: `firmware/SmartLab_Master_Portal/SmartLab_Master_Portal.ino` (pin constants and the
"WIRING THIS FIRMWARE EXPECTS" header), `door_audio.h`, `docs/BRINGUP_LOG.md` (door entries 2026-10-04/05) and
the hardware inventory the owner gave on 2026-10-03. Nothing here was re-measured today.
**Every value marked "not recorded" must be measured or read off the part before it is used** - no value was
guessed. The pin table in `docs/DOOR_SYSTEM.md` ("RFID SS 5 / RST 22, SPI", "solenoid on NC") is OUT OF DATE:
the MFRC522 was retired and the lock moved to NO on 2026-10-04.

## 1. Parts

| Part | What is recorded | Not recorded (measure / read) |
|---|---|---|
| Controller | ESP32 dev board (classic ESP32), firmware SmartLab_Master_Portal, ESP32 core 3.3.11 | board variant / USB chip; supply path at the door (bench: laptop USB) |
| NFC reader | PN532 V3 module "HW-147", **I2C**, address 0x24, DIP switches **S1 ON, S2 OFF**, firmware 1.6; IRQ and RESET not wired | supply pin used (3.3 V or 5 V) |
| Screen ("LCD") | 1.8" TFT **ST7735**, 160 x 128, `INITR_BLACKTAB`, own SPI bus (write-only, no MISO) | VCC and backlight (LED) pin supply; backlight resistor if any |
| Fingerprint | AS608-protocol optical module (firmware: `Adafruit_Fingerprint`, up to 127 slots), UART 57600 8N1 | exact model (R307 / AS608 / ...), supply voltage (3.3 V or 5 V), touch-sense wire |
| Door contact | MC-38 magnetic reed switch | - |
| Lock | 12 V solenoid lock | current draw |
| Relay | 12 V relay module, high-triggered, VCC and COM on 12 V | module part number, coil current |
| Relay driver | **BC557** PNP, **3.3 kΩ** base resistor, **15 kΩ** base-emitter | BC557 orientation photo ("to be added") |
| Bulk capacitor | **470 µF 25 V** electrolytic across +12 V / GND at the relay module | - |
| Red LED + buzzer | one NPN transistor stage on GPIO21 drives both | transistor part, base resistor, LED resistor, buzzer type (active / passive) |
| Green LED | GPIO14 | series resistor |
| Red LED (own) | GPIO15 via **220 Ω** to the anode (firmware wiring note) | whether it was moved off the NPN collector as described |
| Audio | **removed** - owner, 2026-10-20: "No speaker, I removed it as we did the tablet screen" (the tablet page plays the sounds). History: PAM8403 + 3 W / 8 ohm speaker on GPIO22 (3.3 kOhm + 100 nF filter). The enclosure has no speaker opening | whether the GPIO22 filter parts are still on the breadboard (harmless if left) |
| Power | 12 V / 10 A PSU -> master DC switch -> WAGO 2-in/8-out distribution -> fused branch (fuse on + only) -> buck converter -> 5.00 V; the door has "its own existing buck path"; bench: "12 V adapter (label not recorded)" | which buck module feeds the door node (inventory lists 3 x XL4016 for the other nodes), its set voltage, fuse value |
| Face camera | ESP32-CAM (AI Thinker) - separate board, talks to the laptop face server over Wi-Fi, no wire to the master | its supply |
| Tablet | the master serves the tablet page itself (Wi-Fi) - no wire | - |

## 2. ESP32 pin map (from the firmware constants)

| GPIO | Connected to | Direction / mode | Notes |
|---|---|---|---|
| 19 | PN532 **SDA** | I2C data | `Wire.begin(19, 18)` |
| 18 | PN532 **SCL** | I2C clock | address 0x24 |
| 13 | ST7735 **SCK** | SPI clock | own bus `tftSPI`, separated from the RFID |
| 2 | ST7735 **SDA/MOSI** | SPI data | "NOT GPIO4 (fingerprint wiring uses it)"; GPIO2 is a boot strapping pin - must not be pulled high at boot by the screen |
| 25 | ST7735 **CS** | output | |
| 32 | ST7735 **DC / A0** | output | |
| 33 | ST7735 **RST** | output | |
| 16 | fingerprint **TX** (sensor -> ESP32) | UART2 RX | 57600 baud |
| 17 | fingerprint **RX** (ESP32 -> sensor) | UART2 TX | |
| 27 | MC-38 reed switch, other lead to **GND** | `INPUT_PULLUP` | LOW = closed, HIGH = open |
| 26 | BC557 base via **3.3 kΩ** | output | HIGH = LOCKED (PNP off, coil off), LOW = UNLOCKED |
| 14 | green LED (via resistor, not recorded) | output | on at ACCESS GRANTED |
| 21 | base of the NPN stage driving red LED + buzzer | output | denial beep 600 ms (`DENY_BEEP_MS`), forced-entry / evacuation pulses |
| 15 | red LED via **220 Ω** -> LED -> GND | output | denial feedback without the buzzer's current |
| 22 | audio (amplifier + speaker removed 2026-10-20; was 3.3 kΩ -> PAM8403 L-in, 100 nF to GND) | sigma-delta output, 16 kHz samples | PAM8403 R-in tied to its input ground |
| 3V3 | BC557 **emitter**; 15 kΩ to the base | supply | |
| GND | common ground: ESP32, relay module, sensors, 12 V return via the buck | | |

Free / not used by this firmware: GPIO4 (reserved in a note for the fingerprint wiring), GPIO5, GPIO23 (the old
MFRC522 SPI pins). The record does not say whether anything is still connected to them - check before reuse.

## 3. Circuits

**Lock (fail-secure, validated on the bench 2026-10-05):**
```
+12 V ──┬── relay VCC                          relay COM ── +12 V
        └── 470 µF 25 V (+) ── (-) GND          relay NO  ── solenoid (+);  solenoid (-) ── GND
3V3 ── BC557 E;   BC557 C ── relay IN;   BC557 B ── 3.3 kΩ ── GPIO26;   15 kΩ between BC557 B and E
```
GPIO26 HIGH -> base at 3V3 -> BC557 off -> IN floats low -> coil off -> NO open -> **locked**.
GPIO26 LOW -> ~1 mA base current -> BC557 on -> IN at ~3V3 -> coil on -> NO closed -> **unlocked**.
During reset, flashing or boot the 15 kΩ holds the BC557 off -> locked. Measured: COM-GND 12.1 V at rest,
12.03 -> 11.95 V during an unlock. Driving IN straight from GPIO26 lit the relay LED but did not close NO.

**Door contact:** GPIO27 ── reed switch ── GND (internal pull-up). Magnet on the door leaf.

**Denial alert:** GPIO21 -> (base resistor, not recorded) -> NPN -> collector to the buzzer and the red LED,
their other ends to the supply (not recorded which rail). History: before the lock moved to NO the buzzer's
current dip dropped the relay and opened the door; with NO + the 470 µF it is back on (600 ms).

**Audio (removed 2026-10-20):** the PAM8403 and the speaker are no longer fitted (owner). The firmware's
GPIO22 sound output stays in the code; with nothing on the pin it does nothing.

**Supply:** +12 V branch -> buck -> 5 V -> ESP32 (5V/VIN pin) and the 5 V loads; the ESP32's own regulator
gives 3V3 for the logic. The voltage on each module's VCC pin (PN532, ST7735, fingerprint) is **not recorded**.

## 4. Open items to measure at the lab (owner)
1. Photo of the BC557 as fitted (orientation) and of the NPN stage on GPIO21; read the NPN part number and
   all resistor colour codes (base, LEDs).
2. VCC of PN532, ST7735 (and its LED pin), fingerprint module: 3.3 V or 5 V, measured on the pin.
3. The door's buck module: part, input / output voltage with the door idle and during an unlock.
4. The fuse value in the door branch and the lock's current.
5. ~~Whether the PAM8403 + speaker are fitted~~ - answered 2026-10-20: removed.
6. Whether GPIO4 / 5 / 23 still have wires on them.

## Relay drive as rebuilt on 2026-11-08 (owner's change; supersedes the BC557 stage above)

- Relay module VCC ("VR") on **5 V**, its voltage jumper on 5 V (was 12 V). Lock side unchanged: COM to 12 V +, NO to lock +, lock - to 12 V -, capacitor across the 12 V rail. All grounds common.
- GPIO26 drives the relay IN through a **base resistor and an NPN transistor** (replaces the BC557 PNP stage). Part number and resistor values: not yet recorded.
- **Resistors from GPIO26 to 3.3 V** (pull-up; owner: "between 26 and 3.3") hold the pin at the locked level while the ESP32 resets or boots. Do NOT fit a base-to-GND resistor: it pulls towards unlocked on this wiring.
- Measured: GPIO26 = 3.18-3.2 V when booted and locked, so **HIGH = LOCKED, LOW = UNLOCKED** (firmware constants unchanged).
- Firmware (flashed 2026-11-08): `setup()` writes the locked level with `gpio_set_level()` before `pinMode(OUTPUT)`; `setRelay()` no longer calls `pinMode`.
- Owner's checks after the change: no lock movement on resets or USB replugs; stays closed with the ESP32 unpowered and 12 V on; no longer sticks open or heats; green LED on grant, red LED on denial (LEDs replaced). Trial counts not recorded.
- Still to do: record the transistor part and resistor values; consider a flyback diode across the solenoid; lock-power time limit (needs approval).
