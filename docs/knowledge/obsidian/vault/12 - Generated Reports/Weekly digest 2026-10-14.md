---
type: "report"
generated: true
updated: "2026-10-14T00:46:34+03:00"
period: "2026-10-07 to 2026-10-14"
sources: ["git log --all", "registry.json", "Documentation health", "Workflow drift"]
---

# Weekly digest 2026-10-14

> Generated 2026-10-14T00:46:34+03:00 from local evidence only (no AI). Period: 2026-10-07 → 2026-10-14.

## Commits (83) — verified historical
- `a39ac3a` 2026-10-14 Local agent: lookup/answer/investigate routes, compact evidence + streaming (first word 6.8 s vs full answer 24-68 s), fixed read-only tool
- `1f4f59d` 2026-10-13 Knowledge history: local importers (git, Claude Code transcripts, ChatGPT export/share), secrets from .env/camera.env redacted, owner-revie
- `4087c29` 2026-10-13 Knowledge platform: live n8n state (read-only export, n8n defaults normalised), system hub notes, doc wikilinks, inactive n8n drafts, next-
- `1b4e268` 2026-10-13 Knowledge platform (local): source registry with secret redaction, Obsidian vault generator, n8n workflow catalogue + drift, BM25 search, l
- `9471fdb` 2026-10-13 Re-ID pre-rollout audit: 7 more tests (correspondence, crowd changes, one failure, batch 1, GPU start-up failure), old-vs-new regression ev
- `a2ae4cd` 2026-10-13 Lab checklist: re-ID check
- `8b48ae1` 2026-10-13 Re-ID: fix cv2.dnn batch bug (embeddings wrong once the number of people changed) - one crop at a time; run on the GTX 1650 via DirectML, O
- `d83c168` 2026-10-13 Lab test checklist for 2026-10-14 and robot.env example (UR5e IP, read-only)
- `7d0d5b5` 2026-10-13 SecurityCam engine audit: isolated per-device benchmark, DirectML placement check, real-frame parity and per-stage replay tools; 7 engine-s
- `457a3ff` 2026-10-13 Security camera start: set up the DirectML (graphics card) and OpenVINO engines automatically when missing
- `ed56b8d` 2026-10-13 Security camera: YOLO26 on the graphics card via DirectML (GTX 1650: 33 ms/frame end-to-end vs ~160 ms CPU, same people on 23 lab frames); 
- `68cf304` 2026-10-13 Reusables staff tabs: lists refresh every 4 s, on live events and after an error (a stale list offered an already-returned item)
- `6d83475` 2026-10-13 Security camera: YOLO26 on OpenVINO (CPU) - 105 ms/frame vs ~160 ms with ONNX Runtime, same people found on 23 lab frames; falls back to ON
- `6dc509a` 2026-10-13 Reusables: staff take several items in one lid opening; the weight decides how many left (k of n recorded)
- `ff8658f` 2026-10-13 Reusables: staff tabs 'Take an item' (bin opens for a chosen person, weight confirms) and 'Return an item' (recorded staff return with note
- `07d0375` 2026-10-13 Consumables: count by change (container stays on the scale), container zero follows creep between changes; recalibration restarts from the 
- `c3a7c80` 2026-10-13 Consumables: zero from a lift counts only when two empty-platform readings agree
- `56e38b3` 2026-10-13 Consumable bin: report every 1 s so the portal confirms a change within ~1 s
- `b141fe2` 2026-10-13 Consumables: count from the zero seen at the last lift (load-cell drift no longer leaves a count between two numbers and stuck)
- `7ed95b5` 2026-10-13 Consumables: book whole pieces only when a reading sits cleanly on a count (drift/settling between counts ignored); notification '2 pcs tak
- `4367a69` 2026-10-13 gitignore: n8n.cloud export backup (duplicates automation/n8n/json)
- `833da46` 2026-10-13 Consumables: book NET, confirmed changes - lifting the container books nothing until it is back, a value must repeat before it counts, quan
- `d2effa8` 2026-10-12 Consumable bin: fix crash on 'show' (float printed as %ld shifted the varargs; strlen on garbage)
- `ef7f544` 2026-10-12 RFID: several cards per person (up to 5 on the door), remove one chosen card or all; revoked rows kept
- `506ea57` 2026-10-12 nginx: gzip text responses (JS bundles 3-4x smaller, event lists ~15x)
- `118759f` 2026-10-12 Robotics Lab gallery: owner's own photos of the UR5e, FANUC ER-4iA and lab PCs (cropped, no people, metadata stripped)
- `b8b8b88` 2026-10-12 Lab page: equipment gallery directly under the lab title card
- `0ff23a5` 2026-10-12 Equipment gallery: fixed 4:3 photo frames so a tall photo no longer stretches the row
- `6918880` 2026-10-12 System Devices: Screens card - door tablet link (Master ESP32), IoT wall in this tab or new tab, lab-network and this-computer addresses
- `fe97267` 2026-10-12 Operation Center: titled X/Y axes on every chart, refresh at most every 15 s, no re-animation; Access & Audit debounced filtered reload; e2
- `b555b72` 2026-10-12 Labs: equipment gallery first on every lab page; per-lab items from the owner's list (UR5e, FANUC, 8x S7-1200, Proteus PCs, Power lab tanks
- `5b3f7cc` 2026-10-12 Labs: equipment gallery with free-licence model photos (credited, not our lab); Devices hides demo robots, shows Not configured addresses
- `f57ecb2` 2026-10-12 IoT Dashboard: wall in this tab or (on click) a new tab
- `5178ee0` 2026-10-12 Labs: names/locations per owner, CAD lab retired (data kept), experiments inside each lab, door parts not lab equipment; usage charts with 
- `fceaf8d` 2026-10-12 Face enrolment quality gate: one face, size, sharpness, no repeats; reason shown in the portal
- `a47604a` 2026-10-12 Audit: ESP32-CAM state probed directly, health pill names offline controllers, face archive git-ignored
- `f265146` 2026-10-12 Face server: enrolment before security-camera identify (no queue), YuNet face finding for enrolment, timing logged
- `73b1710` 2026-10-12 Robots: grab any part, whole arm follows (IK, preview only); robots no longer listed twice
- `b8b2402` 2026-10-12 Robots: hold a link and drag (preview), J7 gripper, full view, 11 lab PCs from the camera; Robots menu entry only for students
- `0397aed` 2026-10-12 UR5e: always-on read-only RTDE monitor (robot.env UR5E_IP), started by launch.bat; auto-reconnect
- `b2a8b09` 2026-10-12 Robots in Equipment: live twin + joint bars; offline PREVIEW posed with the bars (drawing only); FANUC ER-4iA label, approximate pneumatic 
- `c589f7f` 2026-10-12 Camera: a lost name comes back only with that person's own face match (owner's rule)
- `3ae3275` 2026-10-12 FANUC: label the confirmed ER-4iA / R-30iB Mate Plus; 3D shape marked as unverified stand-in
- `eb72f92` 2026-10-12 Camera: detector conf 0.35 (seated people), stricter look reacquire 0.18
- `23773a3` 2026-10-12 Face ID: remove-photos button on the closed card too
- `e5904e4` 2026-10-12 Users: Remove user (disabled, credentials revoked, history kept), show-removed toggle
- `c12a970` 2026-10-12 Camera identity: faces cut from the detection frame (skip touching people, drop stale), look frozen while touching, place hand-back narrowe
- `ffaa684` 2026-10-12 Face ID: remove saved face photos (archived, not deleted) and capture again
- `7a1930c` 2026-10-12 Camera: a name is never on two people at once
- `3896870` 2026-10-12 Camera names: best-match reacquire with rivals, face min 0.50; bench QR+face entry bridge
- `c946c94` 2026-10-12 Camera: YOLO26s on ONNX Runtime at 640, 8 threads, fast box loop, in-use/passing rules, whole-picture flicker filter, robot work area, HOME
- `4c425c4` 2026-10-09 Codex prompt in its own file (docs/CODEX_PROMPT.md); handoff prompt updated
- `6ba6c0f` 2026-10-09 Handoff 2026-10-09: booking equipment, smart bin in normal mode, personal door QR, device states
- `6052b3a` 2026-10-08 Reusable bin: 1 kg load cell capacity, OVERLOAD warning on log and LCD
- `5a4437e` 2026-10-08 UR5e twin ceiling-mounted under a gantry plate, as in the lab
- `41673b8` 2026-10-08 Robots: Robotiq 2F-85 on the UR5e twin, movement replay, tool trail, wall mode, staleness fixes
- `beb6924` 2026-10-08 Robot twins from the manufacturers' real models: UR5e and FANUC LR Mate 200iD
- `c7b5fa8` 2026-10-08 Command Center: live lab floor plan, clock, counters, robots in the top panel; robot page: live per-joint traces, twin fills its card, reac
- `7f3b99f` 2026-10-08 React Router 7.18 (clears the 2 moderate advisories; npm audit: 0)
- `6512ee3` 2026-10-08 Docs: Monday lab checklist, security, latency (measured at home), robots; CPU reading fix

## Knowledge base
- Sources indexed: 162
- Broken links: 0 · stale notes: 0 · removed sources: 0

## n8n workflow drift (repo files vs live export)
- New: none · deleted: none

## Still open
- See [[Pending-Approvals]] and [[Known-Bugs-and-Risks]] (curated, not regenerated here).
