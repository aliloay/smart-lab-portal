---
type: project-story
status: "draft - owner review needed"
updated: "2026-10-14"
sources: ["claude:f3ebc4c1", "claude:3b9b3107", "chatgpt:Bsc. Smart Lab (3)", "git log", "memory/project-system-overview.md"]
---
# Smart Lab — from day one

> Draft built only from evidence on this laptop. Each line says where it comes from and how sure it is.
> Message numbers (#n) are in the *History review* notes of [[Claude Code session f3ebc4c1]],
> [[Claude Code session 3b9b3107]] and [[ChatGPT - Bsc. Smart Lab (3)]].
> Sources cover the whole chain: ChatGPT *Bsc. "Smart Lab"* (from 2026-09-13), *(1)*, *(2)*, *(3)* and the Claude
> Code sessions. See [[Missing-History-and-Knowledge-Gaps]] for what is still missing.

## The beginning — 2026-09-13 (ChatGPT *Bsc. "Smart Lab"*, reported)
- 15:51 (#1): the owner introduces himself — Robotics & Automation Engineering student at the **German
  International University (GIU), Cairo, graduating 2027** (signed "Ali Abozeid" there; "Ali Loay" in git) — strongest
  areas industrial automation/PLC, control, robotics, embedded/IoT, AI/vision, ROS2.
- 15:54 (#4): first meeting with the **supervisor, Dr. Ramesh Nouda** (as typed), and the **TA, Shehab**: *"the smart
  lab, it's not about the sensors or the actuators itself, and we will not use PLC as we will not be controlling
  anything … we need the lab itself to be smart. We need to monitor everything. We need the IoT."* Two options were
  discussed (a smaller simulated lab first …).
- 2026-09-14 (ChatGPT *(1)* #3): proposal paragraph; face recognition or an ID to swipe so the system knows who
  enters and leaves; collect 35–50 papers (Scopus, IEEE, 2021–2026).
- 2026-09-14 (*(1)* #7): *"Smart Lab is a huge title"* — a full management system tracking consumables and
  non-consumables across all labs; the Robotics Lab has ~30 PCs, the FANUC robot, the UR5e and a conveyor belt,
  each with states (issue, maintenance, in use, booked).
- 2026-09-14 → 10-02: ChatGPT *(1)* and *(2)* (447 + 750 messages) — proposal, papers, the portal build before the
  first commit, then hardware planning; continued in *(3)* and in Claude Code from 09-24.

## What it is (owner's words, reported)
- A Bachelor's thesis at **GIU**, Robotics & Automation Engineering, by **Ali Loay**: *"Design and Development of an
  Intelligent IoT-Based Smart Research Laboratory Management System"*. Chapters 1–3 written before 2026-10-03; from then:
  hardware bring-up, integration, experiments, Chapter 4 results. — owner explanation 2026-10-03
  (claude:3b9b3107 #28 and #124), saved in `memory/project-system-overview.md`. *Reported.*
- Starting lab: the **Robotics Lab**; other labs later. — same source. *Reported.*

## Before the first commit (2026-09-24, verified historical)
- First repository commit `7ae0b83` 2026-09-24 20:33 "Initial commit: Smart Lab Portal" (git). The portal code
  (backend, frontend, docs) already existed then: the first Claude Code session that day (claude:f3ebc4c1 #1, 17:24)
  starts with *"fix whats here with git … I think I initialized a repo"* — it was built earlier, outside the
  sources available here (probably the missing ChatGPT conversations). *Inference — unverified.*
- The owner wanted the repository public on GitHub — *"very good for my work profile"* (f3ebc4c1 #8). *Reported.*

## 2026-09-24 → 09-30: the portal (verified by git: 2+62+24+1+1 commits)
- "FINAL portal-implementation phase … thesis-defense-quality": frontend, backend, database, authentication,
  booking, QR, access logging, roles, real-time operations (f3ebc4c1 #51, 21:33). *Reported intent.*
- GIU branding: *"The G in logo is black and the bar is Germany flag"* (f3ebc4c1 #140). *Reported.*
- One-click launch with Docker Desktop for development and the **university demo** (f3ebc4c1 #202, 09-25). *Reported;*
  `launch.bat` + `docker-compose.yml` exist today (*verified current*).

## 2026-10-02: the hardware plan (ChatGPT (3), reported)
- *"we have 3 esps now for 3 systems"*: (1) physical environment — humidity, temperature, smoke;
  (2) consumables — load cell + HX711 + LCD for resistors, capacitors, LEDs; (3) a separate ESP on the bin of
  reusable items (Arduino, breadboards …). Power question asked first ("how much voltage do we need").
  — ChatGPT (3), first owner messages, 2026-10-02 18:27–18:34.

## 2026-10-03: the system as the owner explained it (reported)
- Door system with its own ESP32 + ESP32-CAM + face server on the laptop + portal; `launch.bat` opens everything;
  n8n is the automation layer that alerts admins and staff; students sign up, book, get a QR, the door opens after
  two-step verification; the admin has access to everything (claude:3b9b3107 #28, 12:35).
- Thesis numbering: System 1 core robotics/PCs/LAN, 2 environment, 3 consumables, 4 reusables; the door is a
  separate protected subsystem; everything on a **local network without internet** (memory note, same day).
- Lab engineer **Eng. Hemaly** (LAB_STAFF) controls the lab PCs (memory note). *Reported.*

## 2026-10-03 → 10-13: bring-up and integration (verified by git, 135 commits)
Details per day in [[Project-Timeline]]. Highlights with evidence:
- Door, environment node, consumables and reusables bins brought up and tested on hardware (BRINGUP_LOG, memory notes).
- Security camera: YOLOX → YOLO26s (2026-10-12), then GPU (DirectML on the GTX 1650) and the re-ID batch-bug fix
  (2026-10-13) — `docs/benchmarks/` (*tested on recorded frames; live identity test pending*).
- Consumables bin calibrated and counting by change; reusables bin with staff take/return (2026-10-13).
- Local knowledge platform started 2026-10-13 (`tools/knowledge/`).

## Open questions for the owner
1. Is the supervisor's name spelled correctly ("Dr. Ramesh Nouda" in the chat transcript)?
2. Supervisor(s) / university staff to record (only roles you want stored)?
3. Thesis deadlines and the defense date?
