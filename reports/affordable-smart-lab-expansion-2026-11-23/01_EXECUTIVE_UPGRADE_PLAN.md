# Executive upgrade plan
Date 24 Nov 2026. Defense 31 Jan 2027, exhibition 2 Feb 2027. Branch `upgrade/affordable-expansion-2026-11-23`, worktree
`C:/Projects/smart-lab-expansion`. **Not committed, not merged, not deployed, nothing flashed, nothing bought.**

## Decision
1. Spend nothing on the laptop. RAM is at its maximum and the fast disk is healthy.
2. Review and merge the software below: it costs nothing and gives the lab a health page, sensor history and an honest assistant.
3. If money is available, buy in this order: light + leak + probe + DC meter (540 EGP, shipping not included), then CO2 (1,549 EGP).
4. Do not buy a UPS, workstation, 64 GB RAM, managed switch, mains meter or PM2.5 sensor now.

## Built and tested (isolated)
| Item | Result |
|---|---|
| Metric registry, history, coverage, diagnosis, timeline (read only, staff) | done, tested |
| Grouped sidebar: 6 groups, collapsible, compact, role aware | done, tested |
| Health Center `/admin/health` | done, tested |
| Sensor analytics `/admin/sensors` with CSV | done, tested |
| Exhibition screen `/exhibit`, LIVE / HISTORICAL / SIMULATED | done, tested |
| 153 assistant questions answered from records; 46 near-misses declined | done, tested |
| ENV firmware source 0.2.0 (Wi-Fi signal, uptime, memory; CO2 and light prepared, off) | compiles, NOT flashed |
| Index prototype with rollback | measured on a demo database, NOT applied |
| Vibration, power, occupancy history, passport additions, calibration manager | design only |

## Cost levels
| Level | Content | EGP (parts, no shipping) |
|---|---|---|
| 0 | software, firmware source, inventory, documents | 0 |
| 1 | BH1750, leak probe, DS18B20, INA219 | 540 |
| 2 | level 1 + SCD41 | 2,089 |
| 2+ | + GY-521 vibration trial and INMP441 noise trial | 2,484 |

Prices are search snapshots; confirm on the shop page. Wires, connectors and delivery are not included.
