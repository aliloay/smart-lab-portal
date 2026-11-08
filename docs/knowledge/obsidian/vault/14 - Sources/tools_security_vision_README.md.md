---
type: "source-mirror"
source_kind: "documentation"
source_path: "tools/security_vision/README.md"
source_hash: "65e400e92c853c1f32fee6e49f84ad84c0716405bb6253f5fd6c1f1de00119f8"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/README.md` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[docs_ROBOTICS_LAB_ARCHITECTURE.md]] - mentioned by docs
- [[tools_security_vision_security_vision.py]] - mentioned by docs

# Security camera service (`security_vision.py`)

A fixed camera in a lab corner (Mercusys MC210, or any RTSP/ONVIF camera),
analysed on the laptop next to the face server. In the portal: **Security
camera** page (live view, boxes, events) and every lab tile on the **Live
monitor** streams its lab live.

What it does, three times a second:

| | How | Shown / sent |
|---|---|---|
| **People** | YOLOX-S person detector (OpenCV, CPU) + a tracker that keeps an id on each person | a box on each person |
| **Names** | from the door, never guessed: a person first seen in the **door area** within 25 s of a door entry gets that person's name; when only one name is left and one person is unnamed, it is them; everyone else is **Unknown** | "Dr. Ramy … (Staff) USER2" / "Unknown" |
| **Too many people** | people seen > people inside per the door for 8 s | event *More people seen than entered* (possible tailgating), or *Person in the lab with no door entry* when nobody entered |
| **Fixed equipment** | each box (PC, robot) is learnt the first time nobody is in it; then compared (normalised correlation, so the lights do not count) | *Equipment moved or missing* after 3 s; *Movement at equipment with nobody there* (can be turned off per box, e.g. a robot that runs programs alone) |

A person in a box makes it **in use** and pauses the comparison. Staff press
**Accept** when an item was moved on purpose, and the camera relearns it.
Each event is sent once per incident, with a snapshot.

Nothing is recorded except event snapshots (deleted 30 days after staff
checked them). The stream is never open on the network: the service listens
on this laptop only (127.0.0.1; `--host 0.0.0.0` only if the portal runs on
another computer) and the portal fetches each frame from it with the device key. It never actuates
anything: a camera can be wrong, and staff decide.

## Setting up the Mercusys MC210

1. In the **Mercusys app** (phone, any Wi-Fi with internet, once): add the
   camera, then *Camera settings → Advanced → Camera Account*: create a
   username and password (6-32 characters). This is the RTSP login.
2. Turn **off** auto-tracking / patrol: the camera must stay still, or the
   equipment boxes no longer match.
3. Put it on **Smart_Lab** and give it a fixed address, e.g. `192.168.1.155`
   (router DHCP reservation, like the other nodes).
4. Mount it high in a corner so it sees the door and the equipment.

## Running it

```
copy camera.env.example camera.env      (then edit SOURCE, LAB, DEVICE)
start_security_vision.bat               (or just launch.bat - it starts it when camera.env exists)
```

`SOURCE` is `rtsp://<camera account>:<password>@192.168.1.155:554/stream2`
(MC210 measured 2026-10-06: stream1 2304x1296 ~21 fps,
stream2 1280x720 ~24 fps - stream2 is enough for detection and keeps the laptop
free; a "@" or ":" in the password is written as %40 / %3A),
or `0` for the laptop webcam while testing. The first start downloads the
detector (36 MB, `models/README.md`) and installs `requirements.txt`.

Then in the portal: **Security camera → Equipment & door boxes** - drag a
box tightly around each PC / robot, and one around the **door** (needed for
names). The camera appears in the portal by itself on its first report.

## Measured (development laptop, 2026-10-03)

- Detector at 416 px: ~160 ms per frame (12 threads); the service uses 4
  threads and 3 detections a second.
- Face server `/analyze` with this service running: median 36.5 ms vs
  35.3 ms without - the door is not slowed.
- End-to-end on a still test image (two people, one door entry): the entrant
  was named, the other stayed Unknown, and *More people seen than entered*
  arrived in the portal with a snapshot.

Not yet run with the real camera in the lab.

## Try the name lock on the laptop webcam

Double-click `demo_webcam.bat` (or `demo_webcam.bat "USER1=Ali,USER2=Sara"`). It opens
http://127.0.0.1:5101/demo - no portal, no lab camera, local only:

1. Everyone out of view.
2. Click **Ali enters**, Ali walks in alone and stands clear for ~2 s (the look locks;
   `locked` on the page counts the samples).
3. Click **Sara enters**, Sara walks in.
4. Walk past each other, bump, swap sides, step out of view and back: the names
   should stay on the right person - or show Unknown, never the other name.

## Limits, stated rather than hidden

- Names are locked to each person's look (clothes and hair colours, body
  re-identification), learnt only while they stand clear of others. After
  people bump into each other the names go back to the right looks, and
  someone hidden for a moment gets their name back on a clear match - else
  Unknown, never someone else. The look is learnt fresh each entry (it
  follows clothes, not the face), and two people dressed alike can still
  be confused: then they stay Unknown rather than swap.
- After this service restarts, people already inside are no longer
  matched to their door entry (more than 25 s ago) and show as Unknown until
  only one name is left.
- A person hidden behind equipment is not counted; a poster or photo of a
  person can be counted as one.
- Robots and PCs are watched as boxes, not recognised: the general detector
  knows "person", "monitor", "laptop", not "UR5e".

`py -m pytest test_vision.py` tests the tracker, the naming rules, the
equipment watcher and the detector (no camera needed).

