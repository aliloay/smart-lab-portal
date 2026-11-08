---
type: "source-mirror"
source_kind: "documentation"
source_path: "tools/pc_agent/README.md"
source_hash: "7d99b7de32fb75e67bb30f20be78e6af20011959b2d38332a617231240294a90"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/pc_agent/README.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_LAB_GO_NOGO_2026-10-18.md]] - mentioned by docs
- [[docs_OPERATIONS.md]] - mentioned by docs

# Lab PC agent (Robotics Lab, System 1)

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

| Open / Close app (approved list) | starts / politely closes (no force) the program configured for that key in `pc_apps.json` (defaults: notepad, browser, vscode, matlab, proteus, arduino_ide) |
| Lock now | locks the session once |
| Log off (admin, confirmed) | 10 s notice, then `shutdown /l` |
| Restart / Shut down (admin, confirmed) | `shutdown /r` or `/s` with a **60 s on-screen warning** |

Each action shows QUEUED -> EXECUTING -> COMPLETED / FAILED with the agent's own message, or EXPIRED
when the agent did not take it within 60 s (PC unreachable). One action at a time per PC. The portal
sends only an action name and an app *key*; which program a key starts is decided on the PC
(`pc_apps.json` next to `pc_agent.py`, e.g. `{"tia_portal": {"start": ["cmd","/c","start","","Portal.exe"], "image": "Portal.exe"}}`).
Wake-on-LAN is not implemented: it needs BIOS/NIC support and is a lab IT decision.

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

## 2026-10-17: screen wall, monitor choice, sharing to students

- **View screen / View all screens**: the viewer picks *All screens* or one monitor (the agent
  reports its monitors with every usage report and re-reads them on every frame, so a plugged-in
  screen or a resolution change is picked up), and a quality preset: Low (q40, 1 fps), Standard
  (q60, 2 fps) or High (q80, 4 fps). Start and end of every viewing are audited
  (`PC_SCREEN_VIEWED`, `PC_SCREEN_VIEW_ENDED`). The PC still shows "Lab staff are viewing this screen".
- **"Using: …"**: the program in front (process name only, never the window title).
- **Admin -> students**: the admin chooses a screen or window in the browser's own picker, sees a
  local preview, and only then presses *Go live* (to all lab PCs or selected PCs). Chosen PCs get a
  notice and open `http(s)://<portal>/share`; the master PC can be the source instead (no https
  needed). Nothing is recorded.
- **Remote keyboard/mouse control is NOT implemented** in the agent. Use Windows' own, authorised
  tools: `mstsc /shadow:<session> /v:<pc> /control /noConsentPrompt:0` (Windows Pro, the user is
  asked for consent) or a managed remote-support product chosen by IT.

## Installation on a pilot PC (needs IT approval first)

1. IT approval for: running the agent in the student's session, outbound HTTP to the portal
   (192.168.1.200, ports 80 / 8000), screen capture with a visible notice.
2. `py -m pip install psutil requests pillow` (Pillow is required for screen frames).
3. In the portal: Devices -> issue this PC's own device key after its first report; set `DEVICE_KEY`.
4. Task Scheduler: *At log on (any user)* -> `pyw.exe pc_agent.py --device PC_01 --asset PC-01 --portal http://192.168.1.200:8000/api`.
5. Firewall: nothing inbound - the agent only connects out to the portal.
6. Check in the portal: the PC appears under Lab Equipment -> Robots & PCs within 30 s; then View screen,
   Message, Open app -> notepad, Lock now; sharing to that PC only.

