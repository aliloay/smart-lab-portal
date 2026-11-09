# Mobile camera and augmented reality ("Scan the lab")

Point a phone at lab equipment and see that equipment's live record pinned next to it in the camera picture. Staff open it from the AI bubble → **Scan the lab**, or at `/scan`. Implementation: [`frontend/src/pages/Scan.tsx`](../../frontend/src/pages/Scan.tsx), [`backend/app/api/routes/scan.py`](../../backend/app/api/routes/scan.py), `backend/app/services/scan.py`, `live_target.py`. Full design notes: [SCAN_THE_LAB.md](../SCAN_THE_LAB.md).

Three layers, never mixed:

| Layer | What | Where it comes from |
|---|---|---|
| 1. Detection | People boxes (generic "person" + score) | The lab's camera service via `POST /api/scan/people` (YOLO26s 416) |
| 2. Identification | A printed QR marker `SLAB:D:<device_uid>`, `SLAB:B:<bin code>` or `SLAB:A:<asset tag>` | Decoded **on the phone** (native BarcodeDetector, else jsQR in a Web Worker) |
| 3. Live data | The record of that exact key: heartbeat age, newest readings (LIVE ≤ 5 min, else STALE), robot joints, bin estimate, door, PC | `GET /api/scan/asset?code=` |

A person is named only by a clear face match of their own crop (server-signed, per track); otherwise unidentified. Equipment with no marker in view is labelled "unidentified (scan its marker)". Questions by voice or text go to one target-aware endpoint (`POST /api/scan/ask`). No frame or recording is stored.

See: [mobile-camera.md](mobile-camera.md) · [overlay-and-data-integration.md](overlay-and-data-integration.md) · [device-compatibility.md](device-compatibility.md) · [troubleshooting.md](troubleshooting.md).
