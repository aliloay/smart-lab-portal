# Tracking and presence

Five different things, never used interchangeably:

| Concept | Meaning in this system | Produced by |
|---|---|---|
| **Detection** | "There is a person in this box in this frame" | YOLO26s |
| **Tracking** | "This box is the same person as track 7 a moment ago" (temporary id, per camera) | `Tracker` (motion prediction + appearance) |
| **Identity association** | "Track 7 is USER2", only from evidence: their own door entry, a clear face match, a stored look, or the last unnamed person when one name is left | `identity.py` (evidence ledger with confidence and decay) |
| **Access authentication** | "USER2 passed both factors at the door at 10:02" | Master Node + API |
| **Presence estimate** | "These people are inside now", combining sessions and what the cameras see | API `occupants()` + security events |

A person the evidence does not name stays **Unknown**. Names are never guessed from position or order. A named person appears as "not entered" until the door confirms their entry.

## Presence states shown in the portal

- **Occupants**: people with an open access session (door) and camera tracks matched to them.
- **"Person in the lab with no door entry"** (critical): a person is seen while nobody has entered.
- **"More people seen than entered at the door"** (warning): seen > entered for 8 s, e.g. tailgating.
- **"Face does not match the door entry"** (critical): possible card sharing.

## Two cameras

Each camera tracks on its own. With a floor calibration (≥ 4 points per camera in `anchors/<DEVICE>_floor.json`), `crosscam.py` lets one camera borrow a **confirmed** name for the same person only when the floor positions agree, the observation is fresh, the one-to-one matching is stable for several passes and nothing conflicts. Without calibration nothing is shared. This was simulation-tested; real accuracy needs both cameras mounted and calibrated.
