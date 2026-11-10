---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/SCAN_THE_LAB.md"
source_hash: "76984c4bfc67b2d856f3242865583d393831a42474dde01345b483178695c990"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/SCAN_THE_LAB.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_FINAL_IMPLEMENTATION_AUDIT_2026-10-26.md]] - mentioned by docs
- [[docs_PROGRESS_CHECKPOINT.md]] - mentioned by docs
- [[docs_SECURITY.md]] - mentioned by docs

# Scan the lab - the phone camera in the AI assistant (2026-10-26)

Open: AI bubble (bottom right) or the sidebar AI button -> **Scan the lab** (staff), or `/scan`.
The launcher also offers Ask the lab, Ask the project and Talk.

## How it works - three layers, never mixed

| Layer | What | Where | Rule |
|---|---|---|---|
| 1. Detection | people boxes (generic class "person" + score) | the lab's camera service, `POST /detect` (YOLO26s 416), via `POST /api/scan/people` | optional; a box never carries a name; one phone frame at a time (busy = 429 -> the phone sends its next frame, nothing queues) |
| 2. Identification | printed QR marker `SLAB:D:<device_uid>` / `SLAB:B:<bin code>` / `SLAB:A:<asset tag>` | decoded **on the phone** (native BarcodeDetector, else jsQR in a Web Worker) | the marker text is the record's own key; no marker = "unidentified" - the camera never names equipment from its look |
| 3. Live data | the card of that exact record | `GET /api/scan/asset?code=` (app/services/scan.py) | heartbeat age, readings (newest per metric, LIVE <= 5 min else STALE; none in 24 h = said so), bin estimate only when calibrated, robot / PC state as reported, open alerts / issues |

Markers: `/scan/markers` prints one marker per asset in the registry (41 in the current data: devices, consumables
bins, equipment, reusable-bin items; a networked item's equipment record resolves to its device). Stick each on a
flat visible face, >= 4 cm wide - the four enclosure designs are not changed.

## Phone (HTTPS)
`/phone-setup`: secure-context self-check, the Smart Lab CA download (`/smartlab-ca.crt`, public certificate only) with
the Android / iPhone trust steps, and a QR to open `https://<laptop>/scan` on the phone. The CA private key moved
out of the nginx-mounted folder (`deploy/tls-ca/`, docs/SECURITY.md).

## Measured (2026-10-26, headless Chrome at phone size with a fake camera; NOT a real phone yet)
| | Result |
|---|---|
| Marker -> live card | 226-255 ms warm, 1.2-2.4 s on the first start (camera + worker start) |
| Marker decode (jsQR worker, desktop CPU) | 12-55 ms per check, ~8 checks/s |
| People boxes (real lab footage, live camera service running its own analysis) | 7 answered frames/s, round trip p50 55 ms / p95 136 ms, detector 27 ms, 0 busy skips, 0 errors |
| Fixed camera meanwhile | 9.8 analyses/s, pass p95 120 ms, frame age p95 77 ms |
| Stop | 5/5 cycles: camera track ended, 0 scan requests after Stop; hidden tab releases the camera |

Tests: backend `tests/test_scan.py` (13), camera `test_phone_detect.py` (3), browser `e2e/scan_lab.mjs`,
`e2e/scan_people.mjs` (fake camera).

## Not done / still to verify
* A real phone (Android Chrome + iPhone Safari) on the Smart_Lab Wi-Fi, after trusting the CA: permissions, back/front
  switch, overlay alignment, battery, network drop.
* Markers printed and placed in the lab.
* WebXR AR is not used: the standard video + overlay works on every browser with a camera; AR would add nothing the
  marker overlay does not already show.
* Person identity from the phone view is deliberately NOT inferred (no cross-view association from the phone).

