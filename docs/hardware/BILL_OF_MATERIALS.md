# Bill of materials - Smart Research Laboratory (draft, 21 Nov 2026)

Quantities and part types are taken from the repository's own hardware records (sources in the last column).
**Prices are deliberately empty**: no price list exists in the repository (docs/defense/DEFENSE_BRIEF.md says so), and
no number is quoted until it comes from a receipt or a dated shop page. Fill `Unit price (EGP)` and `Source of price`,
then the totals follow. Existing equipment (laptop, router, cameras, lab PCs, robots) is listed separately and not
counted as project cost.

## 1. Door access (Master node)
| # | Part | Qty | Used for | Unit price (EGP) | Source of price | Record |
|---|---|---|---|---|---|---|
| 1 | ESP32 dev board (classic ESP32) | 1 | door controller (MASTER_LAB01) | | | DOOR_MASTER_WIRING.md |
| 2 | PN532 V3 NFC module (HW-147, I2C) | 1 | card / tag reader (step 1) | | | DOOR_MASTER_WIRING.md |
| 3 | Optical fingerprint module (AS608 protocol, R307-type) | 1 | fingerprint (step 2) | | | DOOR_MASTER_WIRING.md |
| 4 | 1.8" TFT ST7735 160x128 | 1 | door screen | | | DOOR_MASTER_WIRING.md |
| 5 | 12 V solenoid lock | 1 | lock | | | DOOR_MASTER_WIRING.md |
| 6 | 12 V relay module (high-triggered) | 1 | switches the lock | | | DOOR_MASTER_WIRING.md |
| 7 | BC557 PNP + 3.3 kOhm + 15 kOhm resistors | 1 set | relay driver from 3.3 V | | | DOOR_MASTER_WIRING.md |
| 8 | 470 uF 25 V electrolytic capacitor | 1 | 12 V bulk at the relay | | | DOOR_MASTER_WIRING.md |
| 9 | MC-38 magnetic reed switch | 1 | door open/closed | | | DOOR_MASTER_WIRING.md |
| 10 | Buzzer + red/green LEDs + NPN stage + resistors | 1 set | denial / grant signal (buzzer to be replaced) | | | DOOR_MASTER_WIRING.md |
| 11 | ESP32-CAM (AI Thinker) + ESP32-CAM-MB programmer | 1 | face / QR camera at the door (CAM_LAB01) | | | DOOR_MASTER_WIRING.md |
| 12 | NFC cards / tags | as issued | user credentials | | | hardware inventory |

## 2. Environment node
| # | Part | Qty | Used for | Unit price (EGP) | Source of price | Record |
|---|---|---|---|---|---|---|
| 13 | ESP32 dev board | 1 | ENV_LAB01 | | | environment-node.md |
| 14 | DHT22 | 1 | temperature / humidity | | | hardware inventory |
| 15 | MQ-2 gas sensor | 1 | smoke / gas | | | hardware inventory |
| 16 | 5-channel flame sensor | 1 | flame | | | hardware inventory |
| 17 | HC-SR501 PIR | 2 | motion | | | hardware inventory |

## 3. Consumables bin
| # | Part | Qty | Used for | Unit price (EGP) | Source of price | Record |
|---|---|---|---|---|---|---|
| 18 | ESP32 dev board | 1 | BIN_NODE_1 | | | consumables-node.md |
| 19 | 1 kg straight-bar load cell + HX711 | 1 | weighing | | | hardware inventory |
| 20 | 16x2 I2C LCD | 1 | count / guided calibration | | | hardware inventory |
| 21 | Acrylic platform + 3D-printed holder + glass box | 1 | container seat | | | owner, 21 Nov |

## 4. Reusables bin
| # | Part | Qty | Used for | Unit price (EGP) | Source of price | Record |
|---|---|---|---|---|---|---|
| 22 | ESP32 dev board | 1 | REUSE_BIN_1 | | | reusables-node.md |
| 23 | 5 kg load cell + HX711 | 1 | weighing | | | hardware inventory (owner: 5 kg) |
| 24 | PN532 NFC module | 1 | item tags | | | reusables-node.md |
| 25 | 16x2 I2C LCD | 1 | display | | | hardware inventory |
| 26 | MG90S servo | 1 | lid lock | | | hardware inventory |
| 27 | NTAG213 stickers | as used | tags on reusable items | | | hardware inventory |

## 5. Power and enclosures
| # | Part | Qty | Used for | Unit price (EGP) | Source of price | Record |
|---|---|---|---|---|---|---|
| 28 | 12 V / 10 A power supply | 1 | all nodes | | | power-distribution.md |
| 29 | XL4016 buck converter (set 5.00 V) | 3 (+ door path) | node supplies | | | power-distribution.md |
| 30 | WAGO 2-in/8-out distribution, inline fuse holders, master DC switch, 5.5x2.1 DC jacks | 1 set | distribution | | | power-distribution.md |
| 31 | 3D-printed enclosures (door, environment, consumables, reusables dock) | 4 | housings | | filament grams x price/kg | DOOR_ENCLOSURE.md, tools/cad |
| 32 | Wires, headers, breadboards, screws | 1 set | assembly | | | - |

## 6. Existing equipment (not project cost)
| Item | Note |
|---|---|
| Laptop (Dell G3 3590) | runs the portal, database, AI and cameras; RAM upgraded to 32 GB by the owner (state separately if counted) |
| Smart_Lab router (Huawei/Vodafone) + TP-Link switch | lab network |
| 2 IP security cameras | AI security cameras |
| Lab PCs, UR5e, FANUC | GIU lab equipment |

## Totals
| Section | Total (EGP) |
|---|---|
| 1 Door | |
| 2 Environment | |
| 3 Consumables | |
| 4 Reusables | |
| 5 Power + enclosures | |
| **Project hardware total** | |

Software cost: 0 (open-source only: FastAPI, React, PostgreSQL, Ollama/Qwen, YOLO, n8n self-hosted, Obsidian).
