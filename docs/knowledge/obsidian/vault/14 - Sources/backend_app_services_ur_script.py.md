---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/ur_script.py"
source_hash: "b1a43180af181cccbc34d47407b58b2a94ae8f70054791346872b180ab05c7f0"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/ur_script.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_services_robot_control.py]] - imports
- [[docs_ROBOT_CONTROL.md]] - mentioned by docs

```py
"""
UR5e URScript sender (secondary client interface, TCP 30002) - used ONLY when ROBOT_CONTROL=live,
which stays off until the owner signs off the commissioning step (docs/ROBOT_CONTROL.md).

Exactly two scripts can be built here and nothing else is ever sent:
  * home_script(q) - one joint-space move (movej) to the verified Home pose, gentle speed
  * STOP_SCRIPT    - stopj: decelerate and stop the arm
The controller itself refuses scripts in Local mode (pendant), when protective/safety stopped or
not powered; the caller checks that first through the Dashboard Server and reports BLOCKED.
"""
from __future__ import annotations

import math
import socket

HOME_A = 0.8        # rad/s^2
HOME_V = 0.35       # rad/s
STOP_DECEL = 2.0    # rad/s^2 for stopj


def home_script(q_deg: list[float]) -> str:
    if len(q_deg) != 6:
        raise ValueError("home pose needs 6 joints")
    q = ", ".join(f"{math.radians(v):.5f}" for v in q_deg)
    return f"def smartlab_home():\n  movej([{q}], a={HOME_A}, v={HOME_V})\nend\n"


STOP_SCRIPT = f"def smartlab_stop():\n  stopj({STOP_DECEL})\nend\n"


def allowed(script: str) -> bool:
    return script == STOP_SCRIPT or (script.startswith("def smartlab_home():\n  movej([")
                                     and script.count("\n") == 3)


def send(host: str, script: str, timeout: float = 2.0) -> None:
    if not allowed(script):
        raise ValueError("refused: only the Home move and stopj may be sent")
    with socket.create_connection((host, 30002), timeout=timeout) as s:
        s.sendall(script.encode())

```
