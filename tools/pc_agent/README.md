# Lab PC agent (Robotics Lab, Phase 7)

`pc_agent.py` — visible console program on PC-01 / PC-02 (wired to the lab
LAN). Every 30 s: CPU, RAM, disk, network, whether someone is signed in
(`POST /api/equipment/state`). The portal replies with the mode staff set
on the Equipment page: NORMAL, EXAM or MAINTENANCE.

**Exam mode:** compares running **program names** with the prohibited list
(`EXAM_PROHIBITED_PROCESSES` in the portal's `.env`) and reports each
program once per exam (`POST /api/equipment/violations`). Staff are
notified; nothing is decided automatically.

**Never collected:** screenshots, keystrokes, browser history, file
contents, camera, microphone. Websites cannot be seen from a program list —
blocking them needs a managed / kiosk exam browser (lab policy).

```
pip install psutil requests
set DEVICE_KEY=<this PC's key>          (Devices -> Issue own key, after its first report)
py pc_agent.py --device PC_01 --asset PC-01 --portal http://192.168.1.200:8000/api
```

**Tested 2026-10-03** on the development laptop against a test backend:
registered as a PC, state RUNNING with the signed-in account, five
metrics every cycle; in EXAM mode with `python.exe` prohibited it reported
the running program with the account name.
