# Optimisation phase: what remains (10 November 2026)

No new features. Everything below is a measurement, a calibration, a configuration step or a record. Items are ordered by how much they strengthen the defense.

## 1. Nodes: calibration and code constants

| Node | State | What remains | Where |
|---|---|---|---|
| **Door (Master)** | Working in the lab; relay boot fault repaired 8 Nov 2026 | No calibration. Three records: part number and resistor values of the rebuilt NPN stage; a decision on the maximum lock-energised time (firmware limit, needs owner approval); re-test of the portal evacuation command on the current build | `docs/hardware/DOOR_MASTER_WIRING.md` |
| **Environment** | Sensors bench-verified, deployed | Four constants in `env_config.h` are still marked `VERIFY`: PIR output level and warm-up time, flame output level, MQ digital output level. Confirm each with a meter once and remove the mark. The flame threshold (160 mV) and gas thresholds should be recorded against a real test | `firmware/SmartLab_Environment_Node/env_config.h` |
| **Consumables** | In daily use | **The largest open measurement.** Calibration factor against known masses, noise with `avg 100`, drift over one hour, repeatability of the same mass ten times. The filter constants (median 5, average 20, deadband 0.04 g, stable band 0.08 g) are design values not yet confirmed on the real bin | `SmartLab_Consumable_Bin.ino`, BRINGUP_LOG Phase 3 |
| **Reusables** | Prototype, partial bench run (NFC and lid flow on 9 Oct) | Servo angles (home 0°, press 60°), reed polarity, lid timeouts and the load-cell bands are all `VERIFY`. Needs one complete bench bring-up, including servo current on the 5 V rail | `SmartLab_Reusable_Bin.ino`, `SmartLab_Reusable_Bin_Modular/config.h` |
| **Power** | In use | Continuity, fuse, branch voltages and buck converters under load were never written down | BRINGUP_LOG Phase 1 |

The enclosures are reported printed in PETG. If heat resistance is claimed, quote the filament's rated temperature from its datasheet, since no temperature test was run.

## 2. Integration gaps

| Gap | Effect | Step |
|---|---|---|
| Names cross between the cameras only while both see the person and can place them | Both cameras have floor maps (live-verified 19 Oct, refit 21 Oct 2026). A name does not cross when the feet are hidden in either view or the person has already left the other view, so the second camera can show "Unknown" for a person the first one confirmed | Measure the look-based handoff (`fix/crosscam-handoff`, simulation-tested) in a two-person walk test before relying on it |
| Formal offline run not done | "100% local" is verified in code only | Unplug the internet for 30 minutes and run `tools/offline/offline_check.py`; keep the report |
| AR not measured on a real phone | Latency figure missing | Time scan-to-record on one phone, ten scans |
| FANUC twin verified in one session only | Read-only twin followed the pendant on 14 Oct 2026 (about 3 samples/s); the J2/J3 coupling was not confirmed against known poses, and the 3D meshes are those of the LR Mate 200iD | Compare two or three poses with the pendant values; repeat the run once and keep the record |
| Reusables node only partially integrated | The scan and complete routes exist; the full borrow-and-return loop on hardware is not recorded | Covered by the bring-up above |
| Seed passwords are public | Security question at the defense | Change every live account still using one |

## 3. Numbers the thesis still needs

These turn the five claims into results.

| Number | How to obtain it | Have it? |
|---|---|---|
| End-to-end door latency (scan to unlock) | Timestamp on the node and in the access event, 20 entries | No recorded measurement found |
| Camera pipeline latency | `docs/LATENCY.md` | Yes |
| Detection speed and accuracy | `docs/CV_BENCHMARK_2026-10-26.md` | Yes |
| RAM and CPU of the whole stack | `docs/SMART_LAB_RESOURCE_BUDGET.md` (3 Nov) | Yes; repeat once in the final configuration with the model on the GPU |
| Assistant answer time | `docs/AGENT_SPEED_REPORT_2026-10-27.md`; A/B of 19 Oct (68 s → 3 s) | Yes |
| Cold start: power-on to portal ready | Stopwatch from `launch.bat` to health 200; node boot to first heartbeat | No |
| Recovery after a power cut | Cut power to a node and to the router; time to reconnect | No |
| Load-cell accuracy | Section 1 | No |
| Cost | Price list of every part, with the laptop stated separately as existing equipment | No |
| Power draw per node | USB or bench meter, idle and active | No |

## 4. Software optimisation that is still reasonable

| Item | Benefit | Risk |
|---|---|---|
| Split the 3D twin and chart bundles (Vite chunk warning) | Faster first load on phones | Low; frontend only |
| Repeat the resource measurement and write it into the thesis | Supports "lightweight" with a current figure | None |
| Update the stale firmware and vision READMEs listed in the project inventory | Consistent documentation | None |

Per-container memory limits were considered and rejected: usage is far below any sensible limit, and a limit would only add out-of-memory risk.

## 5. Suggested order for the next lab session

1. Consumables calibration and repeatability (about 45 min).
2. Environment `VERIFY` constants with a meter (20 min).
3. Two-person walk test of the cross-camera handoff: feet hidden, seated, leaving one view for the other (30 min).
4. Offline run and cold-start timing together (40 min).
5. Phone AR timing (10 min).
6. Door records and evacuation re-test (20 min).
7. Reusables bench bring-up, if time allows; otherwise it is presented as a prototype.
