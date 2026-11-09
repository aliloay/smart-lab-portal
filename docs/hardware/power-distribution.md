# Power distribution

Source records: [DOOR_MASTER_WIRING.md](DOOR_MASTER_WIRING.md) (door branch), [BRINGUP_LOG.md](../BRINGUP_LOG.md) Phase 1 (distribution checks) and the node READMEs. Only recorded values appear here.

## Design (as recorded)

```text
12 V / 10 A PSU ─► master DC switch ─► WAGO 2-in/8-out distribution ─► fused branch per node (fuse on + only)
                                                                       ├─ Environment: XL4016 buck → 5.00 V
                                                                       ├─ Consumables: XL4016 buck → 5.00 V
                                                                       ├─ Reusables:   XL4016 buck → 5.00 V (servo on the 5 V branch rail)
                                                                       └─ Door: 12 V to the relay COM and lock; its own buck → 5 V for the ESP32
All grounds common. 470 µF / 25 V bulk capacitor across +12 V at the door relay.
```

| Rule | Why |
|---|---|
| Never feed a buck's 5 V into the ESP32 5V/VIN pin while USB is connected | Back-feeding the USB port |
| Set each XL4016 to 5.00 V with no load before connecting a node | Over-voltage protection for the ESP32 and modules |
| Fuse values are chosen from measured branch current, not from the PSU rating | P1.4 / P1.9 in BRINGUP_LOG |
| Lock on the relay's NO contact | Fail-secure: a power loss leaves the door locked |

## Measured values

| Point | Value | Source |
|---|---|---|
| 12 V rail at the door during an unlock | 12.03 → 11.95 V | DOOR_MASTER_WIRING.md |
| Environment 5 V supply for the PIRs and MQ-2 | 5 V from its XL4016 (4.97 V measured on the door 5 V supply on 5 Oct) | BRINGUP_LOG |
| GPIO 26 (relay drive) | 3.18-3.2 V locked; about 2.9 V dip at reset; 0.7 V with USB unplugged (before the 8 Nov fix) | owner multimeter, 8 Nov 2026 |

## Not yet measured

The distribution tables in BRINGUP_LOG Phase 1 (continuity, fuse labels, 12 V per branch, buck outputs under load) are still blank, and so are the lock current, the door buck part and its set voltage. They are listed in [hardware-validation.md](hardware-validation.md).
