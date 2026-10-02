# Lab PC agent (Robotics Lab, System 2)

`pc_agent.py` is a visible console program on PC-01 / PC-02 (on the lab LAN,
wired or Wi-Fi). It does two things:

- **Every 30 s**: CPU, RAM, disk, network, and whether someone is signed in
  (`POST /api/equipment/state`). The portal replies with the mode staff set
  on the Equipment page: NORMAL, EXAM, MAINTENANCE or LOCKED.
- **Every 2 s**: asks the portal for staff actions from the admin's master PC
  (`GET /api/equipment/pc/poll`).

## Admin master PC actions (Equipment → 2 · Robots & PCs)

| Action in the portal | What the agent does |
|---|---|
| Remove access (or Lock all PCs) | locks the PC (same as Win+L) and locks it again within ~2 s whenever someone unlocks it |
| Give access (or Unlock all) | stops re-locking and shows "Lab staff gave this PC access again." |
| View screen | shows "Lab staff are viewing this screen" and sends ~2 frames/s, only while the viewer is open; stops ~6 s after it closes |
| Message | shows the text in a pop-up |

Every action is audited in the portal (`PC_ACCESS_REMOVED`, `PC_ACCESS_GIVEN`,
`PC_SCREEN_VIEWED`, `PC_MESSAGE_SENT`). Frames are kept only in the portal's
memory, as the latest frame per PC, and are never written to disk or the
database.

Screen view is **view only**. For remote control use Windows RDP shadowing
(`mstsc /shadow:<session id> /v:<pc ip> /control`, needs Windows Pro on the
lab PC) or a VNC server.

## Exam mode

The agent compares running **program names** with the prohibited list
(`EXAM_PROHIBITED_PROCESSES` in the portal's `.env`) and reports each program
once per exam (`POST /api/equipment/violations`). Staff are notified;
nothing is decided automatically.

**Never collected:** keystrokes, browser history, file contents, camera,
microphone, or the screen while nobody is viewing. Websites cannot be seen
from a program list; blocking them needs a managed / kiosk exam browser,
which is a lab policy decision.

## Install

```
pip install psutil requests pillow
set DEVICE_KEY=<this PC's key>          (Devices -> Issue own key, after its first report)
py pc_agent.py --device PC_01 --asset PC-01 --portal http://192.168.1.200:8000/api
```

It must run **in the signed-in user's session**, not as a Windows service,
or it cannot lock the PC or see the screen. Start it at every log-on with
Task Scheduler: *Create Task → Triggers: At log on (any user) → Action:
`pyw.exe pc_agent.py ...`*. `pyw` runs it without a console window.

## Tested

**2026-10-03**, on the development laptop against a test backend:

- registered as a PC, state RUNNING with the signed-in account, five
  metrics every cycle;
- in EXAM mode with `python.exe` prohibited, it reported the running
  program with the account name;
- lock and pop-ups stubbed: lock was applied every 2 s while LOCKED and
  stopped after NORMAL; the message was delivered once; the screen view ran
  at ~1.5 frames/s (~64 KB each) and stopped when the viewer closed.

Not yet run on the real lab PCs.
