# PC fleet and Hemaly relay audit

- **Source:** `devices` table, read-only, at 19:11 local.
- **Location:** the PCs are at GIU, so all their telemetry is **HISTORICAL** unless stated otherwise.

## Registered PC rows (14)

| Device UID | Portal name | Hostname | IPs (last report) | Agent | Last seen (UTC) | Online |
|---|---|---|---|---|---|---|
| PC_ADMIN_LAPTOP | ADMIN-LAPTOP (master PC) | (owner laptop) | 192.168.1.200, 192.168.1.8 | 1.0 | live (20 s) | ✔ live |
| PC_ENG | **HEMALY - ENGINEER PC** | **S2PC136** | **192.168.1.100**, 10.30.11.136 | 1.0 | 11-18 17:28 | ✘ |
| PC_GIULAB20-PC4 | PC-02 | GIULAB20-PC4 | 10.40.20.4 | 1.0 | 11-18 17:27 | ✘ |
| PC_GIULAB20-PC8 | PC-06 | GIULAB20-PC8 | 10.40.20.8 | 1.0 | 11-18 17:28 | ✘ |
| PC_GIULAB20-PC11 | PC-08 | GIULAB20-PC11 | 10.40.20.11 | 1.0 | 11-18 17:27 | ✘ |
| PC_GIULAB20-PC12 | PC-09 | GIULAB20-PC12 | 10.40.20.12 | 1.0 | 11-18 17:27 | ✘ |
| PC_GIULAB20-PC13 | **PC-10** | GIULAB20-PC13 | 10.40.20.13 | **0.9** | 11-18 17:27 | ✘ |
| PC_GIULAB20-PC14 | **PC-11** | GIULAB20-PC14 | 10.40.20.14 | 1.0 | 11-18 17:27 | ✘ |
| PC_GIULAB20-PC17 | PC-13 | GIULAB20-PC17 | 10.40.20.17 | 1.0 | 11-18 17:28 | ✘ |
| PC_GIULAB20-PC18 | PC-14 | GIULAB20-PC18 | 10.40.20.18 | 1.0 | 11-18 17:27 | ✘ |
| PC_GIULAB20-PC19 | PC-15 | GIULAB20-PC19 | 10.40.20.19 | 1.0 | 11-18 17:28 | ✘ |
| PC_01 | TEST - old HP test PC (10-21) | HP-PC | 192.168.1.101 | 0.9 | 10-21 | ✘ (retired) |
| PC_06 | TEST - old PC-6 card (11-03) | GIULAB20-PC8 | 10.40.20.8 | 0.9 | 11-03 | ✘ (retired) |
| 10.30.11.136 | TEST - old PC-6 duplicate (11-03) | GIULAB20-PC8 | 10.40.20.8 | 0.9 | 11-03 | ✘ (retired) |

## Assessment

- **"14 lab PCs"** is really: 9 GIU lab PCs, Hemaly's engineer PC, the admin laptop, and 3 retired TEST cards (two are duplicates of GIULAB20-PC8). The thesis should say **10 GIU machines + the admin laptop**.
- **PC-10 agent update 0.9 → 1.0:** still pending (confirmed in the DB).
- **PC-11 mapping:** device `PC_GIULAB20-PC14` is named PC-11. It was renamed on 19 Nov from "GIULAB20-PC14". The physical sticker is UNVERIFIED.
- **Duplicates:** the 3 TEST rows are labelled "TEST -" and are excluded from alerts (B-07). They keep `component_state.state = RUNNING`, but the UI uses `is_online` / `device_out`, so they show offline. This is a cosmetic leftover.
- **Hemaly's PC network:**
  - It has two NICs: 192.168.1.100 (Smart_Lab side) and 10.30.11.136 (GIU network).
  - **.100 collides with the FANUC controller** (F-03).
  - Its MAC `00-e0-4c-...` looks like a USB Ethernet adapter, plausibly the relay link.
- **Relay (`tools/relay/relay.py`):**
  - Tests pass: `py -3.14 -m pytest -q tools/relay` gave 6 passed.
  - It is not running here, by design: it runs on Hemaly's PC at GIU. Its connectivity is UNVERIFIED today.
- **PC agent:**
  - 40 tests pass (`tools/pc_agent`).
  - `AGENT_VERSION = "1.0"` (`pc_agent.py:62`).
  - A signed bundle update path exists (`/pc/agent-bundle`, `make_bundle.py`).
  - Exam lockdown is in `exam_lockdown.py` (tested).
- **Screen sharing, broadcast and viewer timeouts (`backend/app/services/pc_control.py`):**

| Constant | Value |
|---|---|
| `VIEWER_TIMEOUT_S` | 6 |
| `FRAME_MAX_AGE_S` | 5 |
| `BROADCAST_FRAME_MAX_AGE_S` | 6 |
| `PRESENTER_GONE_S` | 90 |
| `SHARE_REQUEST_TTL_S` | 300 |

  - The watch-link token is in memory with an expiry (`equipment.py:1150-1170`). Broadcasts to the "staff" audience are hidden from student watch links. VERIFIED FROM CODE.
- **Message all, maintenance, shutdown countdown, exam mode:** implemented and covered by backend and pc-agent tests. **No message was sent and no shutdown was triggered.** Live behaviour is UNVERIFIED today.
- **Offline indicators:** PC state comes from agent heartbeats, plus `lan_presence` ping (agent wins, per 17 Nov opt branch).
- **Workflow `20-pc-offline`** reports "Findings: 10" every 15 min. That matches the 10 GIU machines being offline.

## Required at GIU

1. Update PC-10 to agent 1.0.
2. Confirm the PC-11 sticker matches `GIULAB20-PC14`.
3. Give Hemaly's Smart_Lab NIC a static IP outside .100–.103.
4. Start the relay and confirm all 10 heartbeats are fresh.
5. Run one screen-share and broadcast session with a staff viewer, then confirm auto-close after the presenter leaves (90 s).
