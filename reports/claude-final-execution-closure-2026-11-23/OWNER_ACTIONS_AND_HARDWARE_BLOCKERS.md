# Owner actions and hardware blockers - 23 Nov 2026

These need you in person, at GIU, with a hardware part, or as a decision only you can make. None was done or faked by Claude.

| # | Action | Where | Why it can't be done by software | Ready-made procedure |
|---|---|---|---|---|
| 1 | **Reconnect the Smart_Lab network at home** | home | All five ESP32 boards have been offline since 22 Nov 16:28. The laptop's Ethernet holds 192.168.1.200, but the link is down (cable or router power) | Plug the cable in or power the Smart_Lab router, then check Devices: CAM/MASTER/ENV/BIN/REUSE show online within 1 min |
| 2 | Camera validation with both cameras | GIU | Streams unreachable from home | `CAMERA_OFFLINE_VALIDATION_AND_GIU_TEST_PLAN.md` (11 steps, about 30 min) |
| 3 | Review and push to GitHub | laptop | Pushing is the owner's call | `GITHUB_AND_DEPLOYMENT_STATUS.md` |
| 4 | Approve or decline the account `ahmed` | portal → Users | Approving a real person is the owner's decision | Users → Pending → Approve/Reject |
| 5 | UR5e commissioning sign-off | GIU | Robot control stays UNAVAILABLE until the owner signs off (`docs/ROBOT_CONTROL.md`) | `docs/ROBOT_CONTROL.md` step list |
| 6 | F-02 / F-03 network decision | home + GIU | Both routers use 192.168.1.1; Vodafone Wi-Fi and Smart_Lab share 192.168.1.0/24 | Option A: move Smart_Lab to 192.168.50.0/24 (update the 5 board configs and the portal URLs). Option B: keep it, with the interface-metric workaround |
| 7 | F-21 face re-enrolment | door camera | Needs the real person | Profile → Face ID, or staff upload |
| 8 | **F-24 fit the 1N4007 flyback diode** | master box | Hardware | Procedure below |
| 9 | PC-10 agent update 0.9 → 1.0 | GIU PC-10 | Remote update not authorised | Run `SmartLab_PC_agent_UPDATE.zip` (in `tools/pc_agent`) on PC-10 as in `tools/pc_agent/README.md` |
| 10 | Room 224 checks | GIU | Physical | Confirm room number and seat map on the Laboratories page |
| 11 | Slot 2-4 times | - | Not recorded anywhere | Send them; the FAQ entry is updated in 1 minute |
| 12 | B-01 visibility | - | Owner kept it on 22 Nov | No action |
| 13 | n8n "Smart Lab 00 - Error handler" | n8n UI | Inactive and not attached; agents may not edit live workflows | Activate it; in each workflow's Settings set Error workflow = "Smart Lab 00" |

## F-24: 1N4007 and the 20-relock test
**Fit (power off):**
- Put the 1N4007 across the lock coil terminals (the 12 V solenoid or maglock, not the ESP32 side):
  - **cathode (band) to +12 V**
  - **anode to the switched (relay or MOSFET) side**
- Keep the leads short. Insulate them with heat-shrink.

**Test (owner at the door; the Master ESP32 opens the door as normal):**
1. Power on. Wait for the TFT ready screen and check Devices → MASTER_LAB01 online.
2. Repeat 20 times: badge a valid RFID card → second factor → door opens → wait for the relock click → immediately badge again.
3. **Pass:** the RFID reader answers on all 20 relocks, with no freeze and no reboot. Check the TFT does not go blank, and the portal Access log shows 20 grants.
4. **Fail:** note the attempt number. If the reader froze, power-cycle it, and note whether the diode was warm and whether the 12 V rail dipped (use a multimeter on the 12 V rail during relock if available).
5. Record the result with the date in `docs/hardware/hardware-validation.md` (door section).

Until this passes, the RFID relock fault stays **open**. The showcase video must not call it fixed.
