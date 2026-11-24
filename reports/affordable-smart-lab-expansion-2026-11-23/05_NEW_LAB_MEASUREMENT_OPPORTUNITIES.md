# New measurements
| Measurement | Useful for | How | Cost EGP | Status |
|---|---|---|---|---|
| Wi-Fi signal, uptime, free memory per node | explains offline boards | env firmware 0.2.0 | 0 | source ready |
| Data coverage and gaps | evidence for the thesis | portal | 0 | built |
| PC runtime, load, disk | computer utilisation | PC agent (exists) | 0 | built (history) |
| Tool use from the reusable bin | utilisation, passport | existing checkouts | 0 | data exists, view designed |
| Robot state history | runtime | existing read-only collector | 0 | exists |
| Door open / denied counts | reliability, aggregate | existing events | 0 | in timeline |
| CO2 | ventilation indication | SCD41 | 1,549 | firmware prepared, off |
| Light | lamps left on | BH1750 | 250 | firmware prepared, off |
| Water leak | early hint | resistive plate | 50 | design |
| Temperature at the supply | overheating hint | DS18B20 | 65 | design |
| 12 V / 5 V supply | brown-out evidence | INA219, below 26 V and 3.2 A | 175 | design |
| Noise level | comfort; no audio stored | INMP441, level computed on the node | 250 | design, later |
| Vibration RMS | before/after comparison | GY-521 | 145 | design, later |
| PM2.5 | soldering/3D-print dust | PMS5003 | 1,825-1,893 import, before customs | not recommended now |
| Mains energy | equipment energy | certified isolated meter | no verified price | not recommended now |

**Five most valuable:** node Wi-Fi/uptime, data coverage, CO2, supply voltage/current, light.

Limits: none of these is a certified life-safety instrument. Vibration gives a baseline comparison, not predictive maintenance.
Mains work only by an authorised electrician with a rated isolated meter. Noise stores one number per minute, never sound.
