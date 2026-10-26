# Robot control (Home / approved routines / software stop)

Status 2026-10-14: **ownership, checks, audit and UI are implemented and tested with mocked adapters.
Every real adapter answers UNAVAILABLE. Nothing can reach a robot controller from the portal.**
Update 2026-10-18: the UR5e adapter has Home + STOP behind `ROBOT_CONTROL=dry_run` (nothing is sent until the owner
signs off; see the 2026-10-17 and 2026-10-18 sections). FANUC is still monitoring only (UNAVAILABLE).

| | UR5e (192.168.1.102) | FANUC ER-4iA (192.168.1.100, R-30iB Mate Plus, HandlingTool V9.30) |
|---|---|---|
| Today | RTDE **receive** (monitoring) | HTTP GET `/MD/CURPOS.DG` (monitoring) |
| Commands | UNAVAILABLE | UNAVAILABLE |
| Controller mode read | not yet (reported UNKNOWN, blocks all) | not yet (UNKNOWN, blocks all) |

## What the server enforces (`backend/app/services/robot_control.py`, `/api/robots/{id}/control*`)

- Staff only. One portal owner per robot; 5 min expiry; explicit release; only an admin can force a release.
  Ownership lives in memory, so a backend restart clears it (never a stale owner).
- Commands: `home`, `routine` (allowlist per robot, empty today), `stop`. Movements need `confirmed: true`.
- Each needs: ownership, telemetry < 2 s old, controller mode `REMOTE_READY` read from the controller.
- `command_id` de-duplication: a repeated id is answered `DUPLICATE`, never executed twice.
- Every request is audited (`ROBOT_CONTROL_REQUEST/RELEASE`, `ROBOT_COMMAND` with result).
- Result states: `REJECTED`, `UNAVAILABLE`, `REQUESTED`, `DUPLICATE`. `REQUESTED` never means "moved" or
  "stopped": only measured telemetry shows that. The twin is driven by telemetry only.
- The portal lock does **not** stop the teach pendant. The software stop is **not** an emergency stop.

## Commissioning (authorized robotics operator, robot in a safe state, one step at a time)

### UR5e
1. On the pendant decide whether Remote Control is allowed in this lab (Settings > System > Remote Control).
   The portal never switches the mode.
2. Write and validate on the pendant, at reduced speed, the programs: `home.urp` and each approved routine.
   Positions and speeds come from the operator, never from the portal.
3. Implement `URAdapter` with the Dashboard Server (port 29999): read `is in remote control`, `robotmode`,
   `safetymode` -> `controller_mode()`; `load home.urp` + `play` for Home; `stop`/`pause` for the software stop.
4. Test with the robot in Local mode first (must be refused), then Remote with the operator at the pendant.

### FANUC
1. Confirm which licensed remote option the controller has (e.g. PC/remote program start, Socket Messaging,
   or UOP/PNS signals). Do not use undocumented web endpoints. The `/MD/CURPOS.DG` collector stays read-only.
2. Write and validate TP programs (`HOME`, approved routines) on the pendant at reduced speed.
3. Implement `FanucAdapter` on that verified interface: read TP enable / remote / ready -> `controller_mode()`.
4. Same staged tests as the UR5e. J2/J3 coupling stays twin-only (`Collector.twin_q`).

Until each step is signed off, leave the adapter returning UNAVAILABLE.

## 2026-10-17 - UR5e master controls (Home pose + global STOP), DRY RUN until signed off

**Verified UR5e Home position (Home pose)** (read off the teach pendant, owner's photo 2026-10-17). The UR5e home position is J1 Base -15.00, J2 Shoulder -126.00, J3 Elbow 117.03, J4 Wrist 1 -80.00, J5 Wrist 2 91.00, J6 Wrist 3 95.27 degrees; Home counts as reached only when every measured joint is within 0.5 degrees of it:

| Base J1 | Shoulder J2 | Elbow J3 | Wrist 1 J4 | Wrist 2 J5 | Wrist 3 J6 |
|---|---|---|---|---|---|
| -15.00 | -126.00 | 117.03 | -80.00 | 91.00 | 95.27 |

Tool at that pose (pendant): X -265.39 mm, Y 66.00 mm, Z -264.64 mm, RX 3.117, RY 0.269, RZ -0.026 rad.
Constant `UR_HOME_Q_DEG` in `backend/app/services/robot_control.py`; the twin uses the same pose.

What is implemented (backend, tested with mocks; `ROBOT_CONTROL=dry_run` = nothing is sent):
- **Home** (`POST /api/robots/{id}/control/command {action:"home"}`): owner + confirmation + fresh telemetry +
  controller `REMOTE_READY` (Dashboard: remote control, safety NORMAL, robot RUNNING, no program playing).
  Live mode (changed 2026-10-18, see below) loads and plays the pendant's validated program `home.urp` through
  the Dashboard Server. Only with `UR5E_HOME_METHOD=movej` does it send ONE URScript `movej` to the Home pose
  (a=0.8 rad/s^2, v=0.35 rad/s) via the secondary client interface (`app/services/ur_script.py`, which can build
  only this move and `stopj`).
- **State from feedback only**: `READY / HOMING / HOME_REACHED / BLOCKED / FAILED` (`master` in
  `GET /api/robots/{id}/control`). Home reached = every joint within 0.5 deg and the arm still; 60 s timeout = FAILED;
  telemetry lost during homing = FAILED. Never from a command reply.
- **Global STOP** (`POST /api/robots/{id}/control/stop`): any staff member, no ownership needed, whoever started the
  motion. The latch is set first (no Home can start after it), Home tracking is cancelled, then Dashboard `stop` +
  URScript `stopj(2.0)` are sent (live). Audited `ROBOT_GLOBAL_STOP`.
- **Recovery** (`POST /api/robots/{id}/control/recover`): administrator only, arm reported still; restarts nothing.
- **Not an emergency stop.** The software STOP is not safety-rated. The pendant E-stop / cell hardware E-stop stay
  the only emergency stops; a remote safety-rated E-stop would need safety I/O hardware (not present).
- FANUC keeps its own adapter (UNAVAILABLE) - no UR commands or poses are reused for it.

### Commissioning checklist for the lab (in order; stop at the first failure)
1. Cable + IP: UR5e on Smart_Lab at 192.168.1.102; the laptop pings it; UR5e monitor shows ONLINE in the portal.
2. Twin check: jog each joint on the pendant; the twin follows; "Driven from" shows Teach pendant.
3. Home pose check: put the robot at Home with the pendant's own Home; the portal shows **Home reached** (feedback).
4. Clearance: with the operator, confirm the joint-space path from typical poses to Home is clear (ceiling mount!)
   - move a few poses by pendant, watch the twin preview.
5. Pendant: Settings > System > Remote Control enabled; switch to **Remote** only when the operator agrees.
6. Owner signs off -> set `ROBOT_CONTROL=live` in `.env`, rebuild/restart the backend only.
7. First live test at the pendant, hand on the E-stop: Local mode -> Home must be **refused**; Remote -> STOP first
   (latch + recover), then Home from a nearby pose; watch HOMING -> HOME_REACHED.
8. Switch back to `ROBOT_CONTROL=dry_run` at the end of the session unless the owner keeps live on.
(Superseded by the 10-step checklist below.)

## 2026-10-18 - Home + STOP real-world test readiness (both robots)

| | UR5e | FANUC ER-4iA |
|---|---|---|
| Software | SOFTWARE VERIFIED (mock + dry-run tests, `tests/test_robot_control.py`, `tests/test_robots.py`) | SOFTWARE VERIFIED for "refuses every command" (same tests) |
| Physical | READY FOR SUPERVISED PHYSICAL TEST once steps 1-6 below pass in the lab; **today BLOCKED** (robot not on the network: no telemetry) | **BLOCKED**: no remote interface configured, no validated HOME TP program, no tested stop |
| Mode | `ROBOT_CONTROL=dry_run` (nothing is sent) | adapter UNAVAILABLE |

### UR5e - what Home does now
- **Default `UR5E_HOME_METHOD=program`**: Dashboard Server `load home.urp` (name from `UR5E_HOME_PROGRAM`) then `play`.
  Why: Home must reproduce the pendant's validated Home, not just six joint targets. The operator's program holds
  the path, any clearance waypoints, speed/acceleration and the TCP/payload; a portal-chosen joint move would take
  its own path. The replies are checked (`Loading program: ...`, `Starting program`); anything else (for example
  `File not found`) is REJECTED and nothing is started.
- `UR5E_HOME_METHOD=movej` (one URScript movej, a=0.8, v=0.35) only with the operator's approval.
- Completion only from joint feedback: every joint within 0.5 deg of -15.00, -126.00, 117.03, -80.00, 91.00, 95.27
  and the arm still; 60 s without reaching it = FAILED; telemetry lost while homing = FAILED.
- A second Home while one is in progress is refused ("Home is already in progress").
- **STOP** (any staff member, always enabled): latch first, Home tracking cancelled, then Dashboard `stop` +
  `stopj(2.0)` in live mode. State `STOP REQUESTED` until fresh feedback shows the arm still and no program playing,
  then `STOPPED`. Home stays refused until an administrator recovers; recovery restarts nothing.
- UI states (panel under each twin and in Lab Equipment): `DRY RUN` chip, readiness `READY FOR SUPERVISED PHYSICAL
  TEST` / `Ready (live)` / `Blocked`, phases `Homing`, `Home reached`, `Stop requested`, `Stopped`, `Blocked`, `Failed`.
- Readiness checks, all read from the controller: fresh telemetry, joint feedback, safety mode NORMAL/REDUCED,
  robot mode RUNNING, Remote Control on, no program playing, no STOP latched, owner sign-off (`ROBOT_CONTROL=live`).
  In dry run the best possible result is READY FOR SUPERVISED PHYSICAL TEST (only sign-off missing).
- The portal STOP is a **software stop, not a safety-rated emergency stop**. The pendant E-stop and the cell E-stop
  are the emergency stops.

### UR5e - 10-step supervised commissioning (stop at the first failure)
Qualified operator at the pendant for every step; owner present; hand on the E-stop whenever the arm can move.
1. **Network, no motion**: cable on Smart_Lab, laptop pings 192.168.1.102, UR5e monitor ONLINE in the portal.
2. **Twin check, no portal motion**: operator jogs each joint; twin follows within 0.1 deg; "Driven from: Teach pendant".
3. **E-stops**: operator checks the pendant E-stop and the cell E-stop by the robot's own procedure.
4. **Home program**: operator writes or confirms `home.urp` on the pendant: a MoveJ to the Home pose above at
   reduced speed, plus clearance waypoints if the ceiling mount needs them. Run it from the pendant (Local mode);
   the portal must show **Home reached** from feedback.
5. **Clearance**: from 3-5 typical working poses run `home.urp` from the pendant at reduced speed; the operator
   confirms every path is clear. Write the poses down.
6. **Dry run in the portal**: Remote Control on (operator's decision) -> readiness **READY FOR SUPERVISED PHYSICAL
   TEST** with only "Owner sign-off" open. Press Home: "would send: Dashboard 'load home.urp' + 'play' ... (nothing
   sent)". Pendant to Local -> readiness Blocked (Remote control) and Home refused.
7. **Sign-off**: owner and operator agree; set `ROBOT_CONTROL=live` in `.env`; rebuild/restart the backend only.
8. **First live Home** from a pose close to Home, in Remote mode: phase HOMING -> HOME REACHED; audit row present.
9. **STOP test**: start Home from a pose further away and press STOP ROBOT mid-way: the arm stops, STOP REQUESTED ->
   STOPPED, a new Home is refused while latched; administrator recovery; nothing restarts by itself.
10. **Close**: set `ROBOT_CONTROL=dry_run` again (unless the owner decides otherwise), rebuild the backend, record
   times, joint errors and audit rows in the evidence log.

**Rollback (any failure or doubt):** E-stop if the motion is unsafe -> pendant to Local mode -> `ROBOT_CONTROL=dry_run`
and rebuild/restart the backend -> write down what happened. In dry run nothing in the portal can move the arm.

### FANUC ER-4iA - verified identity (read-only evidence)
From the controller's own page `/MD/SUMMARY.DG` (plain HTTP GET, 2026-10-14 18:21, saved locally in
`tools/robot_monitor/fanuc_probe_out/`, parsed with `py tools/robot_monitor/fanuc_summary.py <file>`):
- LR HandlingTool, Software Edition V9.30P/12, root V9.30107 (media 11/17/2020); robot ER-4iA; "Mate controller"
  option (R-30iB Mate Plus family by the V9.30 version - not printed on the page); DCS V4.2.14; servo V09.00;
  stop pattern D (recorded as printed, not interpreted).
- 220 installed options; the DEMO (time-limited) option list is **empty**.
- Remote-interface options installed: User Socket Msg R648, Socket Messaging R636, PC Interface R641, KAREL R632
  (+ Run-Time Env J539), HMI Device (SNPX) R553, Prog Num Selection J515, Robot Service Request, OPC-UA, Ethernet/IP
  I/O Adapter R538, ROS Ethernet Packets R603, Remote Conn Standard.
- Stop/safety options installed: All Smooth Stop J651, Smooth Stop Upgrade J548, Collision Guard R534, DCS Pos./Speed
  check J567, Mode Switch, Password Protection J541.
- **Installed is not configured.** Nothing on the controller is set up for remote program start, and the portal
  has no FANUC command path. Serial numbers on the page are left out of the repository.

### FANUC - 10-step plan (motion stays disabled until step 10 is signed off)
1. Identity - **done from evidence** (above); re-confirm on the pendant: MENU > STATUS > Version ID.
2. Installed options - **done from evidence** (above; DEMO list empty).
3. Monitoring: cable + 192.168.1.100; the CURPOS.DG collector ONLINE; twin within 0.1 deg of the pendant (POSN).
4. Interface decision with the qualified operator - ONE of: (a) a HOME TP program started by Robot Service Request /
   Prog Num Selection (UOP inputs, driven over Ethernet/IP R538 or SNPX R553), or (b) a KAREL server on User Socket
   Msg R648 that can only start HOME and abort it. No undocumented web endpoints; no UR commands or poses.
5. Controller configuration for that interface done by the operator (AUTO mode, remote start, UOP or the KAREL
   server) - never by the portal.
6. HOME TP program written and validated on the pendant at reduced speed (T1); its own joint values recorded.
7. Normal stop for that interface identified and tested from the controller side (for example UOP *HOLD / cycle
   stop, or a program abort). The cell E-stop stays the emergency stop.
8. `FanucAdapter` written for that one interface with mocked tests and guard tests (no UR code paths).
9. Supervised dry run in the lab: readiness checks pass except sign-off; Home answers DRY RUN; T1/T2 or Local -> refused.
10. Sign-off and the first live test exactly like UR5e steps 7-10; back to dry run afterwards.

**Rollback:** cell/pendant E-stop if unsafe -> disable remote start on the controller (operator) -> adapter back to
UNAVAILABLE / `ROBOT_CONTROL=dry_run` -> record the failure.

## 2026-10-26 - UR5e Home + STOP while the robot STAYS IN LOCAL MODE

**What Universal Robots allows (official Dashboard Server reference, e-Series SW 5.x, "Only Remote Control"):**
`load`, `play`, `stop`, `pause`, `power on/off`, `brake release`, `unlock protective stop`, `close safety popup` are
refused in Local mode; read queries (`robotmode`, `safetystatus`, `programState`, `get loaded program`,
`is in remote control` - 5.6.0+) work in both. So the 2026-10-18 path (Dashboard load/play/stop + script on port
30002) **cannot** work in Local mode. The supported Local-mode route is a program **started with Play on the
teach pendant** that hands control to a computer: the **External Control URCap** (UR ROS 2 driver "teach pendant
mode"; ur_rtde `FLAG_USE_EXT_UR_CAP`, port 50002 - present in the installed ur_rtde 1.6.5). The URCap is already
installed on our UR5e (pendant photo 2026-10-12; its host is set to 192.168.1.101, an old ROS laptop).

**Built (software verified with mocks; DRY RUN by default; nothing has ever been sent to the robot):**
- `tools/ur5e_control/ur_local_control.py` - native agent (Python 3.12 + ur_rtde), 127.0.0.1:5310, key
  `UR_AGENT_KEY` (robot.env, git-ignored). Read-only Dashboard queries + RTDE receive; the External Control link is
  opened only with `UR_CONTROL_MODE=live`. Tests: `tools/ur5e_control/test_ur_local_control.py` (14).
- Backend `UR5E_CONTROL_PATH=local_agent` (default; `dashboard` = the Remote-mode path): `app/services/ur_agent.py`
  (fixed endpoint allowlist), `robot_control.py` routes Home / STOP to the agent; **backend ROBOT_CONTROL and agent
  UR_CONTROL_MODE must agree** (two sign-offs). Tests: `backend/tests/test_robot_control_local.py` (6).
- Twin panel (`RobotControlPanel.tsx`): actual control mode (Local / Remote, read from the controller), who drives
  the arm (portal program / another program / pendant jog / idle), the agent's checks, and the Local-mode limits.

| In Local mode | Works? | Why |
|---|---|---|
| Home | **Only while the portal program plays on the pendant** (operator pressed Play) and every check passes: operator confirmation, fresh joints, safety NORMAL/REDUCED, robot RUNNING, arm still, STOP not latched, start pose within 10 deg of Home or of an operator-verified approach pose (`UR_APPROACH_FILE`, recorded at commissioning; empty = only from near Home). One moveJ (v 0.35 rad/s, a 0.8 rad/s^2) to the verified pose; completion only from joint feedback. | The controller runs external motion only inside a pendant-started program |
| Stop (software) | **Only for motion the portal program commands**: stopJ(2.0 rad/s^2), confirmed from feedback | Same link |
| Stop of pendant jogging / Freedrive | **No** - reported as such | Only the person at the pendant or the E-stop |
| Stop of another pendant program | **No** in Local mode (Remote mode: Dashboard stop) | Dashboard `stop` is Remote-only |
| Someone else uses the robot | Home refused ("another program is playing" / "moved from the pendant"); the pendant always wins | Portal ownership never locks the pendant |
| Emergency stop | **Never** from the portal | The pendant E-stop / cell E-stop are the only emergency stops |

**Pendant program needed (operator, at the pendant, reduced speed first):** `portal_control.urp` = Robot Program ->
(optional MoveJ to a safe start) -> **External Control** node with host = this laptop (192.168.1.200), port 50002.
The installation's External Control host must be changed from .101 to .200 (a program setting, not a safety setting).

**Commissioning (supervised, stop at the first failure; the owner signs off each step):**
1. Agent in dry run: `py -3.12 tools/ur5e_control/ur_local_control.py`; the twin shows "Local mode" + "no program".
2. Operator presses Play on `portal_control.urp`; twin shows "portal program playing"; Home answers DRY RUN.
3. Jog away 5 deg; Home DRY RUN passes; jog 30 deg away; Home refused (approach zone).
4. Record the verified approach poses (operator walks the joint-space path to Home and confirms clearance).
5. `UR_CONTROL_MODE=live` (agent) + `ROBOT_CONTROL=live` (backend); hand on the E-stop; STOP first while still;
   then Home from 5 deg; watch HOMING -> HOME_REACHED; press STOP during a slow Home -> STOPPED from feedback.
6. Back to dry run at the end of the session unless the owner keeps live on.

**Independent safety-rated E-stop (proposal only, nothing changed):** a category-0/1 E-stop must act on the UR
controller's safety inputs - e.g. a second Emergency Stop button (IEC 60947-5-5, positive-opening, two NC channels)
wired to the control box's configurable **safety input** pair set to "Emergency stop" in the Safety configuration
(password-protected; changes the safety checksum), or a safety relay / safety PLC feeding that pair from several
stations. Requires a qualified person, the UR safety configuration change and a validation test - not a software task.
The browser STOP and any ROS / RTDE command are **not** safety-rated and are never described as an E-stop.
