# UR5E_FANUC_DIGITAL_TWIN_OPCUA.md

- **Evidence Class**: `LIVE_SERVICE` + `STATIC_INSPECTION` + `UNIT_TEST` (`28 passed, 4 skipped`).

---

## 1. Read-Only Safety Verification (`STATIC_INSPECTION` + `UNIT_TEST`)

- **`UR5E_01` (`tools/robot_monitor/robot_collector.py --source ur`)**: Connects via `rtde_receive.RTDEReceiveInterface` (or raw TCP `30003` read-only state stream) and optional read-only Dashboard queries (`29999` `robotmode`, `safetymode`, `get loaded program`, `programState`). **Zero** `RTDEControlInterface` or motion/write commands exist anywhere in the codebase.
- **`FANUC_01` (`tools/robot_monitor/robot_collector.py --source fanuc`)**: Polls `GET http://<ip>:80/MD/CURPOS.DG` (`FanucWebSource`). Strictly HTTP `GET` read-only.
- **OPC UA Server (`tools/opcua/opcua_server.py`)**: Every variable node is created with `await node.set_read_only()` (`line 61`), there are zero OPC UA methods, and its sole upstream is `GET /api/opcua/snapshot`.

---

## 2. Critical Live Defect Discovered & Fixed Today: Disconnected Robots Falsely Reported `online: true, state: IDLE` (`P1`)

### 2.1 Live Symptom at GIU (`LIVE_SERVICE` at `16:44–16:54`)
- On-site at GIU today:
  - `UR5E_01` (`192.168.1.102:30003`) was powered off / unplugged from the lab switch (`logs/ur5e_monitor.log` showed continuous `system:10060` connection timeouts).
  - `FANUC_01` (`--robot 192.168.1.100`) timed out on `http://192.168.1.100:80/MD/CURPOS.DG` because `192.168.1.100` was assigned to the Engineer PC (`PC_ENG` USB-Ethernet adapter, MAC `00-e0-4c-18-65-60`) rather than the FANUC controller (`192.168.1.101`).
- **Yet the PostgreSQL `devices` table, the Portal Equipment page, and `GET /api/opcua/snapshot` all showed**:
  - `UR5E_01`: **`is_online = true`**, `last_seen_at = 1.1 s ago`, `values: {"state": "IDLE"}`!
  - `FANUC_01`: **`is_online = true`**, `last_seen_at = 2.5 s ago`, `values: {"state": "IDLE"}`!

### 2.2 Root Cause (`tools/robot_monitor/robot_collector.py:281-295, 324, 356`)
1. When `robot_collector.py` starts up and the robot controller is unreachable (`self.motion.last is None`), `self.motion.snapshot(now)` returns `{"state": "UNKNOWN", "q": None, ...}`.
2. Inside the connection-failure `except Exception:` block (`line 324`) and read-failure loop (`line 356`), `Collector.run()` called `self.report(now)` every 2–3 seconds even when `snap["state"]` was `"UNKNOWN"` or `"TELEMETRY_STALE"`.
3. `Collector.report(now)` (`line 281`) posted `POST /robots/telemetry` (which unconditionally sets `d.last_seen_at, d.is_online = now, True` in `backend/app/api/routes/robots.py:205`) AND at `line 290` checked:
   ```python
   if snap["state"] != "TELEMETRY_STALE":
       self.post("/equipment/state", {..., "state": "IDLE", ...})
   ```
   Because `"UNKNOWN" != "TELEMETRY_STALE"` was `True`, an unreachable robot at startup posted `state = "IDLE"` every 5 seconds and kept `is_online = True` forever!

### 2.3 Fix Implemented (`tools/robot_monitor/robot_collector.py` + `test_collector.py`)
1. In `Collector.report(now)`:
   - If `snap["state"] == "UNKNOWN"` (no sample ever received from the controller), return immediately without posting `/robots/telemetry` or `/equipment/state`.
   - If `snap["state"] == "TELEMETRY_STALE"`, post `/robots/telemetry` **once** on the transition into `TELEMETRY_STALE` (`self._stale_reported = True`) so the portal logs the drop, and then stop posting until a fresh sample arrives so `d.last_seen_at` expires after `OFFLINE_S (30 s)` and the robot accurately transitions to `online: false`.
   - Only post `/equipment/state` (`RUNNING` / `IDLE` / `FAULT`) when `snap["state"] in ("MOVING", "STATIONARY")`.
2. Added regression test `test_unreachable_robot_at_startup_is_not_reported_online_or_idle` in `tools/robot_monitor/test_collector.py` (`28 passed, 4 skipped`).

---

## 3. IP Conflict Note on `192.168.1.100` (`PC_ENG` vs `FANUC_01`)

- Currently `start_fanuc_monitor.bat` / `robot.env` passes `--robot 192.168.1.100`, while `PC_ENG` (`S2PC136`) has its USB-Ethernet adapter configured as `192.168.1.100`.
- When the physical FANUC controller is powered on for live robot testing, ensure the FANUC controller is set to `192.168.1.101` (and `FANUC_IP=192.168.1.101` in `tools/robot_monitor/robot.env`) or set `PC_ENG`'s USB-Ethernet adapter to `192.168.1.210`.
