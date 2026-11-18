# ESP32 firmware audit: each node

**Nothing was flashed.** Physical deployment of every change below is `NOT RUN` until flashed by the owner on site.

## How the builds were made
- **Evidence class:** STATIC INSPECTION + COMPILE.
- **Tool:** arduino-cli 1.5.1 (bundled with Arduino IDE), esp32 core 3.3.12 (`D:\MovedFromC\AppData_Local_Arduino15`), sketchbook libraries in OneDrive\Documents\Arduino.
- **Secrets:** each sketch was built from a scratch copy using its committed `secrets.example.h` as `secrets.h`. The real secrets files are git-ignored and were never copied or read. The binaries are compile proofs, not flashable images (placeholder Wi-Fi and keys).
- Raw results: `firmware_compile_results.jsonl`.

## Results
| Project | Identity (from source) | FQBN | Result | Flash / RAM |
|---|---|---|---|---|
| SmartLab_Master_Portal (door) | MASTER_LAB01 / LAB_01 | esp32:esp32:esp32:PartitionScheme=huge_app | OK, 168 s | 54 % / - |
| SmartLab_Environment_Node | ENV_LAB01 / LAB_01, fw 0.1.1 | esp32:esp32:esp32 | OK, 108 s | 73 % / 14 % |
| SmartLab_Consumable_Bin | BIN_NODE_1 / LAB_01 | esp32:esp32:esp32 | OK, 98 s | 74 % / 15 % |
| SmartLab_Reusable_Bin_Modular (current) | REUSE_BIN_1 / LAB_01, reuse-mod-0.5 | esp32:esp32:esp32 | OK, 154 s | 79 % / 15 % |
| SmartLab_Reusable_Bin (legacy) | REUSE_BIN_1 / **BENCH** | esp32:esp32:esp32 | OK, 136 s | 75 % |
| SmartLab_Robot_Stop | - | esp32:esp32:esp32 | OK, 82 s | 71 % |
| ESP32CAM_Vision_FAST | - | esp32:esp32:esp32cam | OK, 73 s (compile check only) | 37 % |

## Argon source fixes: compile-verified, NOT flashed
- **Consumables:** a failed HTTP send waits 5 s before the next try, so network errors no longer starve HX711 sampling.
- **ESP32-CAM:** non-blocking Wi-Fi reconnect; setup no longer aborts before the web server and task start. **Build the flashable image with core 3.2.1 only:** core 3.3.12 builds fail camera init on this board (17 Nov lab). Core 3.2.1 is not installed any more. Installing it needs the owner's OK, or flash the known-good backups/esp32cam-20261018 image.
- **Modular reusable bin:** `WiFi.setSleep(false)` re-applied after a reconnect.

## Findings (STATIC INSPECTION)
| # | Finding | Priority | Action |
|---|---|---|---|
| 1 | The legacy SmartLab_Reusable_Bin uses the same device id REUSE_BIN_1 with LAB_ID "BENCH" (a lab the portal does not have). Flashing it by mistake would mis-file the bin. | P2 | Owner: never flash; mark the folder legacy. The Modular project is current. |
| 2 | No sketch uses the ESP task watchdog (`esp_task_wdt`): a hung loop would not reset the board. | P3 | Proposal for the next firmware round (door firmware is the owner's decision) |
| 3 | `delay()` calls per project: Master 18, Modular bin 10, legacy bin 8, consumables 3, ESP-CAM 3, environment 2, robot stop 2. Argon removed the blocking ones on network paths. | P3 | Review per call when next flashing |
| 4 | All current nodes turn Wi-Fi modem sleep off (setSleep(false)), except the legacy bin. | info | - |
| 5 | Units: environment DHT22 C / %RH; MQ-2 is a 0/1 state, not ppm; HX711 in grams; the item count is a backend estimate (docs/hardware/NODE_LCD_AND_UNIT_MAPPING.md agrees with the code). | info | - |

## Flash procedure (next lab visit, owner present, one board at a time)
1. Plug in the board and note the COM port (Device Manager).
2. Back up the current image: `esptool --chip esp32 --port COMx read-flash 0 ALL backups/<node>-<date>.bin`
3. Build with the real secrets.h in the owner's checkout (the ESP32-CAM with core 3.2.1), then upload.
4. Watch the serial boot log ("Camera OK" for the ESP32-CAM; Wi-Fi joined; the first heartbeat 200).
5. Check the portal: the device online, its readings and units.
6. Roll back if needed: `esptool write-flash 0x0 <backup>`.
