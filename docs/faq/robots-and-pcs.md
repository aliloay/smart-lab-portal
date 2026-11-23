# FAQ: robots, digital twins and lab PCs

## Q: Can the portal move the robots?
Also asked: robot control, home the robot, start the UR5e from the portal
**A:** No. Robot control is off: every control adapter reports UNAVAILABLE until the owner signs off a commissioning step. The portal only reads telemetry.
Source: `backend/app/services/robot_control.py`, `docs/ROBOT_CONTROL.md`

## Q: Which robots does the lab have?
Also asked: robots in the lab, UR5e and FANUC
**A:** A Universal Robots UR5e and a FANUC (LR Mate family). Both appear as read-only digital twins in the portal.
Source: `devices` table (UR5E_01, FANUC_01), `docs/FANUC_LIVE_TWIN.md`

## Q: Is the UR5e online?
Also asked: UR5e status, is the robot connected
**A:** Live: the portal assistant answers from the robot collector's last report ("Is the UR5e online?"). The robots are at GIU, so away from the lab they show offline with their last report time.
Source: `devices` UR5E_01 (live), `tools/robot_monitor/robot_collector.py`

## Q: What IP addresses do the robots use?
Also asked: UR5e IP, FANUC IP, robot controller address
**A:** UR5e 192.168.1.102 (static, set on the pendant); FANUC 192.168.1.100 (read-only web page). Power the robots on before Hemaly's PC, so the PC does not take one of these addresses.
Source: `docs/LAB_TEST_2026-10-15.md`, `docs/FANUC_LIVE_TWIN.md`, `tools/robot_monitor/start_fanuc_monitor.bat`

## Q: How does the digital twin get its data?
Also asked: twin telemetry, RTDE, OPC UA
**A:** The UR5e collector reads joints and state over UR RTDE, and the FANUC collector reads its controller's web page. Both send the data to the portal, which also publishes it on a local OPC UA server (port 4840). Everything is read-only.
Source: `tools/robot_monitor/`, `tools/opcua/opcua_server.py`

## Q: What does "simulation" mean on a robot?
Also asked: UR5E_SIM, simulated robot, preview mode
**A:** UR5E_SIM and FANUC_SIM are simulated twins used for testing without the real robots. They are labelled SIMULATION and are kept out of the robot alerts.
Source: `devices` (component_state.source = SIMULATION), `backend/app/services/devices.py`

## Q: Which lab PCs are online?
Also asked: PC status, which PCs are free, computers online
**A:** Live: the portal assistant lists the PCs as free, in use or offline ("Which PCs are free?"). The PCs are at GIU; away from the lab they show their last report.
Source: `backend/app/services/agent.py` (pcs_status)

## Q: Which PC is Hemaly's?
Also asked: engineer PC, PC_ENG, S2PC136
**A:** PC_ENG, "HEMALY - ENGINEER PC", hostname S2PC136. It also runs the relay that lets GIU lab PCs reach the portal.
Source: `devices` (PC_ENG), `tools/relay/`

## Q: What can the portal do with the lab PCs?
Also asked: PC agent features, screen wall, message all
**A:** Through the PC agent: a screen wall, screen sharing, a message to all PCs, maintenance with a shutdown countdown, and exam mode.
Source: `tools/pc_agent/`, `backend/app/api/routes/equipment.py`

## Q: How many lab PCs are registered?
Also asked: number of PCs, how many computers
**A:** Historical (21 Nov 2026, not live): there were 14 PC rows: 9 GIU lab PCs, Hemaly's PC, the admin laptop and 3 retired TEST cards. PC-10 still ran agent 0.9; the others ran 1.0.
Source: `devices` table (live), checked 21 Nov 2026
