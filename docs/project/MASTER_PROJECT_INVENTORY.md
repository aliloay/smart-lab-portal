# Master project inventory (10 November 2026)

## Source of truth

| Item | Location | Notes |
|---|---|---|
| Git repository | `C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-portal` → https://github.com/aliloay/smart-lab-portal (public, `main` protected by ruleset) | The single source; every component below lives here unless stated |
| Review worktree | `C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-review` (`review/gemini`) | Review notes only |
| Backups | `C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-backups`, local `backup/` and `snapshot/` branches, tags `checkpoint-2026-10-06`, `handoff-2026-10-09` | Historical snapshots, not newer than `main` |
| Obsidian vault (live) | `C:\Users\dell\SmartLabKnowledge\vault` | Copy in `docs/knowledge/obsidian/vault/` (without chat transcripts) |
| Thesis | `C:\Users\dell\OneDrive\Desktop\Bsc\thesis_overleaf`, `thesis_figures_2026-11-04` | Academic documents; not modified by this release |
| Lab captures | `C:\Users\dell\OneDrive\Desktop\Bsc\lab_captures_2026-11-03`, `lab_qr_2026-11-03` | Raw captures (may show people); not published |
| Recordings | `Camera_lab_testt.mp4`, `Recording 2026-10-19 144725.mp4`, `Digital Twin_Ur5e .mp4`, `nourramy entery test.mp4` in `Bsc\` | Kept locally; processed and anonymised frames are in `docs/media/` |
| Training data | `tools/vision_train/raw`, `results`, `colab_object/*_dataset` (about 1.8 GB) | Kept locally; scripts and metrics are published |
| Launch video project | `C:\Users\dell\OneDrive\Desktop\ONECORE_LAUNCH_VIDEO` | Pitch film and its sources; separate from the repository |

## Components

See [PROJECT_COMPONENT_INVENTORY.md](../release/PROJECT_COMPONENT_INVENTORY.md) (location, purpose, status, dependencies, verification for every subsystem).

## Conflicting or outdated documentation found

| Document | Conflict | Resolution |
|---|---|---|
| `firmware/SmartLab_Consumable_Bin/README.md` | Says "not yet run on hardware"; the device is registered and used | Status "implemented, calibration not measured" in the new hardware page |
| `firmware/SmartLab_Reusable_Bin*/README.md` | Says "not yet run"; bench notes of 9 Oct record NFC and the lid flow | Status "prototype, partial bench run" |
| `tools/security_vision/README.md` | Describes YOLOX-S as the detector | YOLO26s is the default since 26 Oct 2026 (models README); documented in docs/computer-vision |
| `docs/hardware/DOOR_MASTER_WIRING.md` (earlier sections) | BC557 PNP relay stage | Superseded by the 8 Nov 2026 NPN stage section in the same file |
| Early proposals (PLC, MQTT, Raspberry Pi) | Not implemented | Marked "proposed" in the feature matrix |

## Missing assets

Real-phone AR recording, n8n editor screenshots (the live editor needs the owner's login), an offline-run report, photographs of the rebuilt relay stage, and calibration data for the load cell.
