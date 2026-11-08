"""
UR5e morning check - READ-ONLY. RTDE receive interface only (ur_rtde's
RTDEReceiveInterface): nothing is sent to the robot, nothing is posted to the portal.

    py -3.12 tools\\robot_monitor\\rtde_check.py <UR5e IP>

Prints 5 samples one second apart: controller timestamp (must advance), robot/safety
mode, and J1-J6 in degrees - compare them with the pendant's Move tab.
"""
import math
import sys
import time

if len(sys.argv) != 2:
    sys.exit(__doc__)
ip = sys.argv[1]
try:
    from rtde_receive import RTDEReceiveInterface
except ImportError:
    sys.exit("ur_rtde is not installed for this Python (use py -3.12)")

t0 = time.time()
try:
    rx = RTDEReceiveInterface(ip, 50.0)
except Exception as e:                       # refused / timeout: RTDE service off, wrong IP, no route
    sys.exit(f"FAIL connect to {ip}:30004 after {time.time() - t0:.1f} s: {e.__class__.__name__}: {e}")
print(f"connected in {time.time() - t0:.1f} s")
last = None
ok = True
for i in range(5):
    ts, q = rx.getTimestamp(), rx.getActualQ()
    deg = " ".join(f"J{j + 1} {math.degrees(v):8.2f}" for j, v in enumerate(q))
    fresh = last is None or ts > last
    ok &= fresh and len(q) == 6 and all(math.isfinite(v) for v in q)
    print(f"t_ctrl {ts:10.3f}  {'fresh' if fresh else 'NOT ADVANCING'}  robot_mode {rx.getRobotMode()}"
          f"  safety_mode {rx.getSafetyMode()}  connected {rx.isConnected()}\n  {deg}")
    last = ts
    time.sleep(1.0)
rx.disconnect()
print("PASS: live joint data" if ok else "FAIL: see lines above")
sys.exit(0 if ok else 1)
