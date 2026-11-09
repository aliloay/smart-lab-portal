# Hardware validation status

Only recorded tests count. Source: [BRINGUP_LOG.md](../BRINGUP_LOG.md), node READMEs, [DOOR_MASTER_WIRING.md](DOOR_MASTER_WIRING.md).

| Node / part | Test | Result | Date |
|---|---|---|---|
| Master: NFC, QR, fingerprint, TFT, LEDs, buzzer | Bench behaviour | PASS | 5 Oct 2026 |
| Master: relay on NO (fail-secure) | Reset / flash / power loss leaves the door locked | PASS | 5 Oct 2026 |
| Master: relay boot glitch | No unlock on reset or replug, lock closed with the ESP32 unpowered | PASS (owner) | 8 Nov 2026 |
| Environment: DHT22 | Readings, breath test, failure and recovery | PASS | 5 Oct 2026 |
| Environment: PIR 1 / PIR 2 | Detection, independent zones | PASS; range and angle not measured | 5 Oct 2026 |
| Environment: flame board | Detection, clearing, channel mapping | PASS; distance not measured | 5 Oct 2026 |
| Environment: MQ-2 | Bench test with thresholds | Bench tested | 5 Oct 2026 |
| Consumables: load cell | Calibration, accuracy, noise, drift | **Not measured** (table empty) | - |
| Reusables: NFC + lid flow | Bench run | Partial | 9 Oct 2026 |
| Power distribution | Continuity, fuses, branch voltages, bucks under load | **Not measured** (tables empty) | - |
| Door ESP32-CAM + face server | Enrolment and identify | Earlier lab runs; quality gate in place | Oct 2026 |

Open items for the next lab session: fill BRINGUP_LOG Phase 1 and Phase 3, record the NPN stage parts, measure lock current, and run the evacuation command from the portal on the current door build.
