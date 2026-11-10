# Door access system

The door system is the Master Node ([master-node.md](master-node.md)) plus the door ESP32-CAM, the face server on the engineer PC, the 12 V solenoid lock and the portal's access records. Deeper documents: [DOOR_SYSTEM.md](../DOOR_SYSTEM.md), [ACCESS_FLOW.md](../ACCESS_FLOW.md), [DOOR_MASTER_WIRING.md](DOOR_MASTER_WIRING.md), [DOOR_ENCLOSURE.md](DOOR_ENCLOSURE.md).

## What a door entry produces

| Record | Where |
|---|---|
| Credential check (QR booking window, card) | `/api/access/validate-qr`, access events |
| Both factors and their identities, result, reason | access events (audit page "Access & audit") |
| Access session (entry; an exit only when one is observed) | sessions table, booking trace |
| Door open / closed / held open / forced | door events |

## Supported methods

QR code (time-bound, one lab, inside the booking window) or NFC card as factor 1; fingerprint or face as factor 2. Personal QR codes and RFID cards are managed in the portal (enrolment pages).

## Known limitations

- The camera-based presence cross-check depends on the security-vision service running (see [access-camera-integration.md](../computer-vision/access-camera-integration.md)).
- An exit is recorded only when it is observed; a person who leaves while the door is propped open is detected only through the camera.
- The new relay stage's NPN part number and resistor values are not yet recorded; the maximum lock-energised time is an open owner decision.
