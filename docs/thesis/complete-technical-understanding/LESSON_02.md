# Lesson 2: ESP32 nodes, sensors, pins and power

**After this lesson you can** say why each environment sensor is on its pin, how the 12 V reaches it, and what the portal sees when a wire breaks.
Open beside this: `firmware/SmartLab_Environment_Node/env_config.h`, [wiring](../../hardware/wiring-and-pinouts.md), [power](../../hardware/power-distribution.md).

## 1. Simple
An ESP32 is a small computer with Wi-Fi. It reads sensors, checks that the reading can be trusted, and posts it to the laptop. If it cannot trust a reading, it sends nothing.

## 2. The boards
| Name in the portal | Job | Firmware folder |
|---|---|---|
| MASTER_LAB01 | door: card, finger, screen, **owns the lock relay** | SmartLab_Master_Portal |
| ENV_LAB01 | temperature, humidity, gas, flame, motion | SmartLab_Environment_Node |
| BIN_NODE_1 | consumables by weight | SmartLab_Consumable_Bin |
| REUSE_BIN_1 | reusable items by NFC | SmartLab_Reusable_Bin |
| CAM_LAB01 | entrance camera (ESP32-CAM) | ESP32CAM_Vision_FAST |

## 3. Environment node
| Sensor | Principle | Pin | Important |
|---|---|---|---|
| DHT22 | digital temperature and humidity | 4 | read every 2.5 s; not calibrated against a reference |
| PIR 1, 2 | change of infrared | 27, 26 | motion, not a person count |
| MQ-2 | heated metal oxide, resistance falls with gas | AO 39, DO 25 | 5 V part: a 10k/15k divider brings it under 3.3 V; alarm by **rise above baseline** (+400, +700 mV), not ppm |
| Flame board, 5 channels | infrared photodiodes | 13, 32, 33, 35, 36 | channel 1 digital, channels 2 to 5 analog |

**Why these pins?** GPIO 0, 2, 5, 12, 15 decide how the chip boots; 6 to 11 are the flash; 1 and 3 the USB serial. 34 to 39 are inputs without pull-ups. Analog needs ADC1 (32 to 39): ADC2 cannot be read while Wi-Fi is on. The MQ-2 moved from 34 to 39 because 34 was noisy on the bench.

**Firmware version:** the source is 0.2.0 (node health, optional CO2 and light). It is **not flashed**, and those two sensors are not bought. Say "0.1.0 on the board" until that changes.

## 4. From sensing to sending
1. The loop reads every sensor without waiting for the network.
2. A shared struct (`pub`, protected by `pubMux`) hands the values to a separate network task. A slow portal never delays sensing.
3. `sendEnvironmentSnapshot()` adds a value only when it is valid (`dhtValid`, `mqReady`, fitted). No trusted value: no message.
4. `sendHeartbeat()` reports each part as true, false or null. **null = not fitted**, so the portal does not call it broken.
5. `postJson()` uses timeouts and prints the round trip for measurements.

It is plain HTTP on the lab network. The key proves which device speaks, but it is not encrypted on the way: a limitation to state, not to hide.

## 5. Power
230 V → 12 V / 10 A supply → switch → WAGO → one fused branch per node → XL4016 buck set to 5.00 V → board; 3.3 V comes from the ESP32. All grounds common.
- Never connect the buck's 5 V while USB is connected: it feeds back into the laptop.
- Set the buck before connecting the board.
- The lock uses the relay's NO contact: no power, door stays locked.
- Measured: 12.03 to 11.95 V during an unlock. **Not measured:** branch currents, lock current, bucks under load.
- The 1N4007 across the lock coil takes the voltage spike when it switches off. It is **not fitted yet**.

## 6. When something fails
| Failure | Portal shows | Why |
|---|---|---|
| DHT22 wire off | sensor fault; last value old | read fails, valid flag drops |
| Wi-Fi off | node offline after its timeout | no heartbeat |
| MQ-2 just started | no gas value | it warms up first (`mqReady`) |
| Wrong key or lab | request refused | `device_scope`, `device_lab_scope` |

## 7. Common mistakes
"MQ-2 measures CO2" (no) · "PIR counts people" (no) · "certified fire detector" (no) · "ESP32 pins take 5 V" (no).

## 8. Questions
1. Why can the MQ-2 analog output not go to GPIO 4 directly, for two different reasons?
2. What is the difference between `false` and `null` in the heartbeat, and who uses it?
3. Why are sensing and networking two tasks?
4. What happens electrically when the lock relay opens, and what does the diode change?
5. The examiner says "your gas reading is meaningless without ppm". Answer.

**Exercise:** draw the power path from 230 V to the DHT22 with every voltage, and mark which values are measured.
**Paper:** half a page "Environment node": sensors, pins, validity rule, limits.
