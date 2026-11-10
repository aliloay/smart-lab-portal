---
type: "source-mirror"
source_kind: "documentation"
source_path: "firmware/SmartLab_Robot_Stop/README.md"
source_hash: "5f6530f4592082386c3d92e7c9c35230cf8f59e7922aea796f0c39a49c6203f9"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `firmware/SmartLab_Robot_Stop/README.md` - edit the original in the repository, not this note.

Systems: [[Robots (read-only)]]

## Related
- [[docs_ROBOT_CONTROL.md]] - mentioned by docs

# UR5e stop relay (ESP32) - portal STOP that works in LOCAL mode

Status 2026-10-26: firmware written and **compiled** (arduino-cli, esp32 core 3.3.12, 71 % flash); backend tested with
mocks (`backend/tests/test_stop_relay.py`). **Not wired, not run on hardware.** Wiring into the robot's safety
inputs needs the approval of whoever is responsible for the UR5e cell, and a qualified person.

## What it does
In Local mode the UR controller ignores every stop command from the network. It always obeys its own **Safeguard
Stop** input. This ESP32 holds two relay contacts closed in that input's two channels while the portal says RUN.
A portal STOP (Global STOP, Stop in the twin) opens them, and the controller performs a safeguard stop. Programs,
pendant jogging, Freedrive, and another person's PC all halt, and the pendant shows "Safeguard Stop".

| Event | Relays | Robot |
|---|---|---|
| Portal STOP latched | open | safeguard stop within ~0.2-0.4 s (poll 200 ms + relay) |
| Administrator recovery (only after the program was stopped on the pendant) | closed | may run again, nothing restarts by itself |
| ESP32 unplugged / relay coil fails | open | stops (fail-safe direction) |
| Wi-Fi or portal down | keep last state | keeps working; the twin shows the relay OFFLINE |
| Reboot | last commanded state (saved in flash); first boot ever = STOP until the portal answers | |

**Not** a safety-rated emergency stop (hobby relays, Wi-Fi). The pendant E-stop stays the emergency stop.

## Parts
* ESP32 Dev Module (WROOM-32), USB 5 V supply.
* **2-channel** 5 V relay module with opto-isolated inputs (IN1, IN2, VCC, GND, contacts COM/NO/NC each).
  Two separate contacts keep the controller's two channels independent. A single contact feeding both inputs
  would still stop the robot, but it removes the channel redundancy, so it isn't recommended.
* 4 short wires (0.5 mm2) to the control box safety terminal.

## Wiring
ESP32 -> relay module: GPIO26 -> IN1, GPIO27 -> IN2, 5V (VIN) -> VCC, GND -> GND. Remove the JD-VCC jumper only if
the module documents it. Status LED: GPIO2 (on = RUN, blinking = STOP, off = no portal answer yet).

Relay contacts -> UR control box (e-Series), **robot powered off, by a qualified person**:
1. Find the **Safeguard Stop** inputs on the control box's safety I/O terminal (labelled SI0 and SI1). Each has a
   factory jumper to **24V**. Compare this with the label in your control box and the UR user manual (Safety I/O)
   before touching anything.
2. Replace the 24V-SI0 jumper with relay 1: **24V -> COM1, NO1 -> SI0**.
3. Replace the 24V-SI1 jumper with relay 2: **24V -> COM2, NO2 -> SI1**.
   NO (normally open) = closed only while the ESP32 energises the coil, so losing power stops the robot.
4. Keep the removed jumpers in the control box (taped), so the original state can be restored in 1 minute.

## Bring-up (one verified step at a time)
1. Copy `secrets.example.h` -> `secrets.h`; on the portal, **Devices -> add** `UR5E_STOP_RELAY` (type OTHER, lab of
   the robot) and issue its key -> `DEVICE_KEY`. Backend `.env`: `ROBOT_STOP_RELAY_UID=UR5E_STOP_RELAY`
   (`ROBOT_STOP_RELAY_ROBOT=UR5E_01` default) -> rebuild/restart backend (owner OK).
2. Flash (Arduino IDE, board "ESP32 Dev Module"). Serial 115200: `[DIAG] relays=... portal=ok`.
3. **Bench test, not wired to the robot:** a multimeter on COM1-NO1. Portal STOP -> open, recovery -> closed; check
   `RELAY_ACTIVE_LOW` if it is inverted. Unplug the ESP32 -> open. The twin's relay line shows the latency.
4. Wire to the robot (above). Robot on; pendant: no "Safeguard stop" while RUN.
5. Supervised test, hand on the E-stop: jog slowly on the pendant -> portal STOP -> the arm stops, and the pendant
   shows Safeguard Stop. Press Stop on the pendant, then portal recovery (refused before that, by design) -> the robot
   can be used again.
6. Recommended on the controller (owner's decision): Safety -> I/O -> configure a **Safeguard Reset** input with a
   push button at the robot, so even after a release nothing carries on without someone at the cell.

