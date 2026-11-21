# Measured results - 21 Nov 2026 (home bench, real hardware)

All numbers come from the master's serial log (millisecond timestamps, `D:\SmartLabData\firmware_backup\master_serial_20261120.log`),
the portal database, and Windows' network event log. Laptop: Dell G3 3590, 32 GB RAM. Master firmware portal-1.1 (tests A-C),
portal-1.2 (test D and later).

## A. Door decision speed (17 attempts, 17 granted, 0 false denials)
| Step | n | Median | Range |
|---|---|---|---|
| Card read -> identity found (checked inside the master) | 12 | 5 ms | 4-5 ms |
| QR -> booking confirmed by the portal (Wi-Fi round trip) | 5 | 161 ms | 155-182 ms |
| Fingerprint match -> lock released | 11 | 8 ms | 7-8 ms |
| Face match -> lock released | 6 | 5 ms | 5-6 ms |
| Lock released -> grant screen on the TFT | 17 | 230 ms | 229-232 ms |
| Unlock -> automatic relock (configured hold) | 17 | 5.02 s | 5.016-5.017 s |
| (human) card/QR -> finger or face presented | 17 | 3.2 s | 2.4-6.5 s |

Once the second factor matches, the door unlocks in under 10 ms; a QR adds ~160 ms for the portal check. The total time is
dominated by the person.

## B. Master cold start (USB + 12 V off 10 s, then on)
| From power-on | Time |
|---|---|
| Firmware starts | 0.45 s |
| Lock driven LOCKED (first instruction of setup) | 0.47 s |
| RFID reader ready | 1.45 s |
| Fingerprint sensor ready (4 templates) | 2.45 s |
| Wi-Fi connected | 2.82 s |
| SYSTEM READY (accepting access) | 2.89 s |
| Portal shows it reporting again | ~4.2 s (+-1 s sampling) |

The door is locked from the first instruction, so a power cut never leaves it open; the 4 portal cards are reloaded from flash.

## C. Smart_Lab router power cut (off 33 s, then on)
| Event | Time |
|---|---|
| Router back on | 13:21:42.4 |
| Router network stable (own boot) | 13:22:08.0 (26 s) |
| Reusable bin reporting | +0.7 s |
| Master + ESP32-CAM reporting | +2.4 s |
| Environment node reporting | +3.9 s |
| Consumables bin reporting | +5.4 s |

All 5 nodes reconnect by themselves within 5.4 s of the router being ready (~31 s from power restored, 26 s of it the router's
boot). No false inventory bookings, master kept card + fingerprint available throughout.

## D. Laptop unreachable (Ethernet out, 30 min)
| Check | Result |
|---|---|
| Card + fingerprint | works (identity and fingerprint are checked inside the master) |
| QR, Face ID | refused - by design, both need the laptop (bookings / face server) |
| Door events while offline | portal-1.1: dropped (audit gap). portal-1.2: kept (40-event RAM buffer) and all 6 delivered within 1 s of reconnecting, logged at the real time |
| Limit | the buffer is RAM: a power cut of the master while offline loses what is waiting |

## E. Findings
- **PN532 freezes at the relock** - 4 times on 21 Nov, each at the relock (solenoid switch-off spike, no flyback diode). Only a
  power cycle cleared it. portal-1.2 relock guard (PN532 PowerDown before the relock, re-init 250 ms after): reader survived
  4/4 relocks in the first test. Real fix: 1N4007 across the lock (owner will fit it with the new buzzer).
- **ESP32-CAM Wi-Fi idle throttle** (core 3.2.1 build): with the camera idle, 0 % ping loss to all four other nodes
  (30/30 each, 8-11 ms); before, 10-50 % loss while it streamed nonstop.
- **Consumables scale**: a 3D-printed holder fixed to the platform (15.78 g, included in the zero) made the container position
  repeatable; with 0.199 g resistors -3, +1+1+1, -6 were all booked exactly. A 0.15 g disturbance can still book one piece
  (single resistors weigh 0.15-0.22 g) - the 1 kg cell's practical limit for parts this light.

## Not measured
- Node power draw (needs a USB power meter).
- Assistant answer times with both cameras running (at GIU).
- Priced BOM: parts and quantities in docs/hardware/BILL_OF_MATERIALS.md; prices to come from receipts.
