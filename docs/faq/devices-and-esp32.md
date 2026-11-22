# FAQ: the ESP32 boards, bins and environment node

## Q: Which ESP32 boards does the lab have?
Also asked: list of ESP32 nodes, how many ESP32, what boards are there
**A:** Five: the master door controller (MASTER_LAB01), the environment node (ENV_LAB01), the consumables bin (BIN_NODE_1), the reusable bin (REUSE_BIN_1) and the ESP32-CAM door camera (CAM_LAB01).
Source: `devices` table, `firmware/` folders

## Q: Are the ESP32 boards online?
Also asked: ESP32 status, are the nodes up, which boards are online
**A:** Live: the portal assistant answers this from each board's last report ("How many ESP32 boards are online?"). A board counts as offline after 90 s without a report.
Source: `backend/app/services/agent_live.py`, `backend/app/core/config.py` (DEVICE_STALE_SECONDS)

## Q: Which ESP32 handles environment monitoring?
Also asked: what does the environment node do, which board measures temperature, gas sensor node
**A:** ENV_LAB01, the environment node. It reports temperature, humidity, gas and flame to the portal. It only monitors and controls nothing.
Source: `firmware/SmartLab_Environment_Node/`, `docs/hardware/environment-node.md`

## Q: What does the master ESP32 do?
Also asked: door controller function, MASTER_LAB01 role
**A:** It runs the door. It holds the RFID reader (PN532), the fingerprint sensor, the TFT screen, the lock relay and the tablet grant page, and it asks the portal and the face server about QR and face identities.
Source: `firmware/SmartLab_Master_Portal/SmartLab_Master_Portal.ino` (header), `docs/hardware/DOOR_MASTER_WIRING.md`

## Q: What does the ESP32-CAM do?
Also asked: door camera, CAM_LAB01, entry camera
**A:** It is the door's eyes. It reads QR codes and sends frames for face recognition, and the master uses only results younger than 3.5 s. It needs ESP32 Arduino core 3.2.1; newer cores fail with "Camera init failed".
Source: `firmware/ESP32CAM_Vision_FAST/ESP32CAM_Vision_FAST.ino`, master `VISION_FRESH_MS`

## Q: How does the consumables bin count stock?
Also asked: how is stock calculated, how does the scale count resistors
**A:** It weighs the container. Stock = (measured mass − the item's tare) ÷ the mass of one piece of the selected item. Several items can share one scale; the selected item is the one counted.
Source: `backend/app/services/inventory.py`, `inventory_bin_items` table

## Q: How many parts are in the consumables bin?
Also asked: stock level, how many resistors left, how many screws left
**A:** Live: the portal assistant answers from the bin's last measurement ("How many resistors are left?"). When the scale or the node is not reporting, it says so; an unavailable sensor is never counted as zero stock.
Source: `backend/app/services/agent.py` (bins_stock), `backend/app/services/inventory.py`

## Q: How do I calibrate the consumables bin?
Also asked: guided calibration, tare the scale, set up a new item
**A:** In Inventory, start the guided calibration. The bin's LCD then leads you: empty the platform, wait for zero, place the empty container, then add a known number of pieces. Finish in the portal.
Source: `backend/app/services/bin_calibration.py` (CLEAR → ZEROING → CONTAINER → PIECES → DONE)

## Q: What does the reusable bin do?
Also asked: NFC bin, borrow and return items, reusable dock
**A:** It is a dock for items people borrow. Scanning an item's NFC tag opens the lid, and the load cell confirms whether the item was taken or returned.
Source: `docs/hardware/reusables-node.md`, `firmware/SmartLab_Reusable_Bin_Modular/`

## Q: What firmware versions run on the boards?
Also asked: firmware version, which version is the master on
**A:** Live: each board reports its version and the portal assistant shows it ("What firmware is the master running?"). Historical (21 Nov 2026, not live): the versions were master portal-1.2, bin bin-0.6, environment env-0.1.1 and reusable bin reuse-mod-0.5.
Source: `devices.firmware_version` (live), version constants in `firmware/*`

## Q: What happens when the Wi-Fi router restarts?
Also asked: router power cut, do the nodes reconnect, network outage
**A:** All five boards reconnect by themselves. Measured on 21 Nov: all reported again within 5.4 s of the router being ready.
Source: `docs/reports/MEASUREMENTS_2026-11-21.md` (test C)
