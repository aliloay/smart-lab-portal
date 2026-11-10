# FANUC ER-4iA live digital twin - read-only

Status: **LIVE-VERIFIED READ-ONLY** on 2026-10-14 (evening) at 192.168.1.100: the twin moved with the pendant at about 3 samples/s; probe pages in `tools/robot_monitor/fanuc_probe_out/`. Still to confirm: J2/J3 coupling by pose; controller battery DIAG-009. The text below was written the same morning, before the connection, and is kept as the design record.

## Confirmed hardware (owner's photos 2026-10-14)
Robot: FANUC **ER-4iA** (label on the arm). Controller: **R-30iB Mate Plus**, 2021-03 (label "LR20D" -
LR Mate 200iD family). Tool: **SCHUNK EGP 40-N-N-B** electric parallel gripper (24 V, 1 A, 140 N).
A blue Ethernet cable is already plugged into the controller - where it goes and the controller IP: UNKNOWN.
3D model: ROS-Industrial LR Mate 200iD meshes. The ER-4iA is the education version of the short LR Mate
(200iD/4S): link lengths may differ from these meshes (angles map correctly; proportions to be checked).
Replacing the meshes needs a download = owner approval.

## Interface (chosen for safety)
The controller's built-in web server: **HTTP GET `/MD/CURPOS.DG`** (current position page) - no option, no
login, no write. `FanucWebSource` (tools/robot_monitor/robot_collector.py) makes only that GET; a test
(`test_fanuc_source.py::test_the_fanuc_source_has_no_write_path`) fails if any other HTTP verb, socket,
KAREL, register/variable/program/reset vocabulary appears in it. Never used: Stream Motion (J519, can move
the robot), PCDK/FOCAS (options), KAREL/COMET, UOP.
* Rate: 4 polls/s (to be measured on the controller); 1 s timeout; 2 s back-off when unreachable.
* No controller timestamp: sample time = laptop receive time (labelled). Stale after 2 s without a good
  read -> TELEMETRY_STALE, never "stationary" (same motion/stale logic as the UR5e).
* Units: degrees from the page -> radians once (`fanuc_joints.fanuc_to_urdf`, J3 += J2 coupling, TO BE
  CONFIRMED by comparing 2-3 poses); TCP mm -> m once.
* Parser (`parse_curpos`) refuses anything but a complete J1-J6 set: an unknown page format shows
  TELEMETRY UNAVAILABLE, never a guessed pose. The page format is ASSUMED until the probe shows the real one.
* Everything else (twin, joint panel, movement events, HOME comparison, replay, Command Center, camera
  fusion) is the existing UR5e pipeline - same device API, source tag `FANUC_WEB`, device `FANUC_01`.

## Hardware checklist (operator confirms first: movement authorised, workspace clear, E-stop in reach)
A. Discovery - pendant MENU > SETUP > Host Comm > TCP/IP: photograph port 1 / port 2 IP, subnet, gateway.
   Note where the blue cable goes. Do not change anything.
B. If the IP is on 192.168.1.x and free: `ping -n 4 -S 192.168.1.200 <IP>`;
   `py tools\robot_monitor\fanuc_probe.py --robot <IP>` (read-only: port checks + saves the status pages).
   Send Claude the output and `tools\robot_monitor\fanuc_probe_out\*CURPOS*` - the parser is confirmed
   or adjusted to the REAL page, with a test from it.
C. `FANUC_IP=<IP>` in tools\robot_monitor\robot.env -> `start_fanuc_monitor.bat` (or launch.bat).
   Portal -> Robots: FANUC panel LIVE; compare J1-J6 with the pendant (POSN key) within 0.1 deg.
D. Operator jogs ONE joint at a time (T1, low speed): the same twin joint moves the same direction;
   J2/J3 coupling checked at 2-3 poses.
E. Unplug the controller's Ethernet briefly: panel leaves LIVE within ~2-3 s; plug back: LIVE again.
F. Record poll rate, sample age, any parse failures - Claude reads them from the portal's robot events.
