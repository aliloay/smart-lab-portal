# Known issues and open items

| Area | Issue | Type | Next step |
|---|---|---|---|
| Door | NPN part number and resistor values of the rebuilt relay stage not recorded | Hardware record | Photograph and note at the next lab session |
| Door | Maximum lock-energised time not decided | Owner decision | Decide and set the firmware limit (needs approval) |
| Door | Evacuation command from the portal not re-tested on the current door build | Hardware test | Run at the next lab session |
| Power | Distribution checks (continuity, fuses, branch voltages, bucks under load) not measured | Hardware test | Fill BRINGUP_LOG Phase 1 |
| Consumables | Load-cell calibration accuracy, noise and drift not measured | Hardware test | Fill BRINGUP_LOG Phase 3 |
| Reusables | Bring-up incomplete; servo current and `VERIFY` values unmeasured | Hardware | Finish bench bring-up |
| FANUC | Controller IP and page format not inspected; twin unverified | Hardware | Inspect with the owner |
| Cameras | Two-camera name sharing needs both cameras floor-calibrated | Configuration | Calibrate camera 2 |
| AR | Not measured on a real phone | Test | Measure latency on a phone |
| Offline | Formal offline run (internet disconnected, 30 min) not done | Test | Run `tools/offline/offline_check.py` |
| Database | Migration `f1a7c3d9e250` (PC keys) | Done | Applied live on 9 Nov 2026 |
| Accounts | Seed demo passwords are public in the repository | Security | Change every live account that still uses one |
| Frontend | Chunk-size warning for the 3D twin and charts | Performance | Optional further code splitting |
| Licence | No licence file chosen | Owner decision | Choose a licence |
