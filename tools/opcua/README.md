# Smart Lab OPC UA server (read-only), 2026-10-26

**What OPC UA is:** the standard "common language" factories use so that machines and software can share live values.
An OPC UA client (UaExpert, a Siemens/SCADA system, Node-RED, a MES) connects to `opc.tcp://...`, browses a tree of
named values and reads or subscribes to them. This server publishes the Smart Lab's equipment state in that form, so
any industrial tool can watch the lab without knowing the portal's API.

```
SmartLab
  SourceTime, FeedOK
  LAB_01
    Robots / UR5E_01 / Online, LastSeen, robot_mode, safety, program_state, J1_deg..J6_deg, ...
    PCs / PC_07 / Online, LastSeen, state, mode
    Cameras / SECCAM_LT1 / Online, people, fps
    Door / MASTER_LAB01 / Online, door_closed
    Environment / temperature / Value, Unit, Quality (VALID / STALE / ...), At
```
* **Read-only:** every variable is read-only and there are no methods (test: a write is refused).
* **No personal data:** no names, no PC accounts, no images.
* Values refresh every second.
* If the portal can't be reached, `FeedOK` = false and the last values stay (they aren't hidden).

## Start
1. `tools/opcua/opcua.env` (git-ignored):
   * `OPCUA_KEY=<long random>`, the same value as `OPCUA_KEY` in the backend's `.env` (compose passes it);
   * optional `OPCUA_PORTAL=http://127.0.0.1:8000/api` (the default).
2. `py -3.12 tools/opcua/opcua_server.py` serves `opc.tcp://127.0.0.1:4840/smartlab/`. On localhost, anonymous read is
   allowed.
3. For other PCs on the lab network: set `OPCUA_HOST=192.168.1.200`, `OPCUA_USER` and `OPCUA_PASSWORD` (12+
   characters). The server then accepts only Basic256Sha256 Sign&Encrypt with that user, using a self-signed
   certificate made on the first start. Anonymous access is refused (test).

Package: `asyncua` 2.1.0 (Python 3.12), installed with the owner's OK on 2026-10-26.

## Verified (2026-10-26)
* `tools/opcua/test_opcua_server.py` (3) and `backend/tests/test_opcua_feed.py` (2).
* Live against the copy backend: 408 variables, browsed by an asyncua client in 1.5 s; camera people count and
  online state read live.
* Not yet opened in UaExpert or another vendor's client.
