# Wiring and pinouts

Every pin below is read from the firmware constants (9 Nov 2026). Wiring photos, voltages and part numbers are in the per-node READMEs and [DOOR_MASTER_WIRING.md](DOOR_MASTER_WIRING.md).

| Node | Function | GPIO | Source constant |
|---|---|---|---|
| Master | PN532 NFC (I²C SDA / SCL) | 19 / 18 | `RFID_SDA_PIN`, `RFID_SCL_PIN` |
| Master | Fingerprint UART RX / TX | 16 / 17 | `FP_RX_PIN`, `FP_TX_PIN` |
| Master | TFT SCK / MOSI / CS / DC / RST | 13 / 2 / 25 / 32 / 33 | `TFT_*_PIN` |
| Master | Relay (lock) | 26 | `RELAY_PIN` |
| Master | Door contact | 27 | `DOOR_PIN` |
| Master | Green LED / red LED / red LED + buzzer | 14 / 15 / 21 | `GREEN_LED_PIN`, `RED_LED_SOLO_PIN`, `RED_LED_BUZZER_PIN` |
| Master | Audio | 22 | `AUDIO_PIN` |
| Environment | DHT22 | 4 | `PIN_DHT` |
| Environment | PIR 1 / PIR 2 | 27 / 26 | `PIN_PIR1`, `PIN_PIR2` |
| Environment | MQ-2 analog / digital | 39 / 25 | `PIN_MQ_AO`, `PIN_MQ_DO` |
| Environment | Flame board channels 1-5 | 13, 32, 33, 35, 36 | `PIN_FLAME[5]` |
| Consumables | HX711 DT / SCK | 32 / 33 | `HX_DT_PIN`, `HX_SCK_PIN` |
| Consumables | LCD I²C SDA / SCL | 21 / 22 | `I2C_SDA`, `I2C_SCL` |
| Reusables | PN532 + LCD I²C SDA / SCL | 21 / 22 | `I2C_SDA`, `I2C_SCL` |
| Reusables | Servo / lid reed | 13 / 27 | `SERVO_PIN`, `REED_PIN` |
| Reusables | HX711 DT / SCK | 25 / 26 | `HX_DT_PIN`, `HX_SCK_PIN` |

Secrets (`WIFI_SSID`, `WIFI_PASS`, `DEVICE_KEY`) are in each node's git-ignored `secrets.h`; copy `secrets.example.h` and fill it in before building.

## Building and flashing

Arduino CLI with the ESP32 core (FQBN `esp32:esp32:esp32`; core 3.3.x as recorded in the READMEs). Install the libraries named at the top of each `.ino` (Adafruit PN532, Adafruit ST7735/GFX, Adafruit Fingerprint, DHT sensor library, HX711, LiquidCrystal_I2C, ESP32Servo), then:

```powershell
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/SmartLab_Environment_Node
arduino-cli upload  --fqbn esp32:esp32:esp32 -p COM7 firmware/SmartLab_Environment_Node
```

Flash the door node only with the owner present: it drives a physical lock.
