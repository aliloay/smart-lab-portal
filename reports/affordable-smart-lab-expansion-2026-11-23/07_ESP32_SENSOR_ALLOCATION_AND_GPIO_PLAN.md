# ESP32 allocation and GPIO plan
Pins come from the source code. "Free" means unused by the code; check the real board before wiring.

| Node | Used | Free by code | New work |
|---|---|---|---|
| CAM_LAB01 | camera | none useful | none (load, core 3.2.1 limit) |
| MASTER_LAB01 | 13,2,25,32,33,19,18,27,26,14,21,15,16,17 | keep | **none**: the door must not be loaded |
| ENV_LAB01 | 4,13,25,26,27,32,33,35,36,39 | 21,22 (I2C), 16,17, 18,19,23, 34 input only | **all environment sensors** |
| BIN_NODE_1 | HX711 32/33, I2C 21/22 and others | few | only Wi-Fi/uptime, after ENV is proven |
| REUSE_BIN_1 | 21,22,13,27,25,26 and others; 16/17 dead on this board | few | only Wi-Fi/uptime |

## ENV_LAB01 plan
| Pin | Use | Rate | Power |
|---|---|---|---|
| 21 SDA, 22 SCL | SCD41 0x62, BH1750 0x23, INA219 0x40 (no address clash) | 60 s sent; SCD41 measures every 5 s | 3V3; pull-ups to 3V3 only |
| 16 | DS18B20 1-Wire + 4.7 k to 3V3 | 60 s | 3V3 |
| 17 | leak plate, digital | 10 s | switched from 18 |
| 18 | leak plate power, on only while reading | | |
| 19, 23, 34 | reserve | | |

The 3V3 regulator budget must be measured: SCD41 peak current is the largest (datasheet, about 0.2 A). Use the 5.00 V buck and
a separate 3.3 V regulator if the board's own one gets hot. Mount SCD41 away from MQ-2 (it is a heater) with vents; BH1750 under a
clear window; leak plate on the floor with a drip loop; INA219 in **one** node branch, never the 10 A main line.

## Contract
Same endpoint as today: `POST /api/access/telemetry`, up to 20 readings, metric `^[a-z][a-z0-9_]{1,47}$`, unit up to 16 characters,
device key header. The portal stamps the time. Missing or untrusted values are not sent.

## Firmware env 0.2.0 (source only)
Adds `wifi_rssi_dbm`, `device_uptime_s`, `free_heap_b` every 60 s with the normal snapshot; a safety change is still sent first and
alone. Optional SCD41/BH1750 drivers are off. Compiled in a scratch copy with esp32 core 3.3.12 and example secrets: 982,448 B (74 %) and
15 % RAM; with both sensors on 983,812 B (75 %). **Not flashed, not run.** The README names core 3.3.11.
Known change: with no trustworthy sensor the node now still sends its health once a minute.
Rollback: flash the saved env-0.1.1 image.
