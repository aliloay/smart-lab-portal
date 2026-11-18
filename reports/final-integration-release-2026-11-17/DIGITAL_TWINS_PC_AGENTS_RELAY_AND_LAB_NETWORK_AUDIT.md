# Digital twins, PC agents, relay and lab network audit

## Robots and digital twins
| Item | Evidence | Class |
|---|---|---|
| UR5e collector is read-only (ur_rtde receive) | tools/robot_monitor: 42 passed, 1 skipped (Python 3.12) | UNIT TEST |
| UR5e control routes stay UNAVAILABLE | tools/ur5e_control: 20 passed; `ROBOT_CONTROL=off` in docker-compose (owner, 29 Oct); adapters gated by commissioning | UNIT TEST / STATIC INSPECTION |
| OPC UA server | 3 passed (Python 3.12, asyncua); binds 127.0.0.1:4840, anonymous read only on loopback | UNIT TEST |
| FANUC monitor / twin | read-only; no write path found | STATIC INSPECTION |
| Live UR5e / FANUC telemetry, stale-state display | robots not reachable off-site | BLOCKED (on campus) |
| Commands sent to robots during this work | **none** | - |

## Lab PCs, Engineer PC, relay, USB kit
| Item | Evidence | Class |
|---|---|---|
| PC agent | tools/pc_agent: 40 passed | UNIT TEST |
| Relay fallback bind (Argon): if the configured LAN IP is not up yet, bind 0.0.0.0 but keep the subnet allow-list | code review (allow list passed through); tools/relay 6 passed | STATIC INSPECTION / UNIT TEST |
| USB kit manifest LF/CRLF-safe (Argon) | make_kit.py; Argon: 859/859 files verified, secret scan clean | HISTORICAL (Argon run), code reviewed |
| LAN presence | 6 passed | UNIT TEST |
| PC last-seen refresh on poll (Hemaly's PC looked offline) | earlier commit 3587bfb, in the release | UNIT TEST |
| Student PCs PC_01..PC_16 reaching the relay on S2PC136 | Windows Defender Firewall on S2PC136 blocks inbound relay ports | **BLOCKED: GIU IT administrator** |
| Screen preview | view-only by design; no remote-control path | STATIC INSPECTION |

## Hemaly's desk / PC mapping
- `desk_map.json` was not changed. The desk guess is attached to one person only and shown as "Eng. Hemaly?" (a hint, never a confirmed name).
- Argon's change keeps a desk name only for someone the face camera has already named; it never names a second person from the same desk.
- A live check at the desk is BLOCKED (on campus).

## Network
- The laptop runs on the Smart_Lab LAN (192.168.1.x, no gateway) plus a separate internet link.
- GIU Ethernet was disconnected off-site; no public exposure was added. Services stay on loopback or the LAN.
