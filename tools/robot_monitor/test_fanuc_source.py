"""FANUC read-only source (2026-10-14). MOCKED - no controller involved: these prove the software
path and the read-only restriction, NOT a physical connection. The CURPOS text below is an ASSUMED
layout; the real page must be checked with fanuc_probe.py before the twin is trusted."""
import inspect
import math
import sys
import types

import pytest

sys.modules.setdefault("rtde_receive", types.SimpleNamespace(RTDEReceiveInterface=None))
import robot_collector as rc  # noqa: E402

ASSUMED_PAGE = """Current position
 Group 1
 Joint  Tool: 1
  J1 =    10.500  J2 =   -20.000  J3 =    30.250
  J4 =     0.000  J5 =   -90.000  J6 =   180.000
 World  Frame: 0
  X =   400.000  Y =  -50.000  Z =  300.000
  W =   180.000  P =    0.000  R =   90.000
"""


# The REAL layout of the lab's controller (R-30iB Mate Plus, LR HandlingTool V9.30, /MD/CURPOS.DG read
# 2026-10-14 18:21 with fanuc_probe.py) - numbers only, the rest of the page left out.
REAL_PAGE = """CURRENT ROBOT POSITION::
Group #:  1
CURRENT JOINT POSITION:
Joint   1:     -2.86
Joint   2:    -18.09
Joint   3:    -11.55
Joint   4:      3.02
Joint   5:    -74.02
Joint   6:     -1.62
Frame #:   1  Tool #:   1
CURRENT USER FRAME POSITION:
CFG: N U T, 0, 0, 0
X:     -7.87
Y:    300.07
Z:   2509.29
W:    178.25
P:     -3.89
R:   -136.33
Tool #:   1
CURRENT WORLD POSITION:
CFG: N U T, 0, 0, 0
X:    220.19
Y:   -234.41
Z:  -1511.56
W:     -3.11
P:      4.31
R:     83.66
"""


def test_real_controller_page_gives_the_joints_and_the_world_frame_not_the_user_frame():
    j, tcp = rc.parse_curpos(REAL_PAGE)
    assert j == [-2.86, -18.09, -11.55, 3.02, -74.02, -1.62]
    assert tcp == [220.19, -234.41, -1511.56, -3.11, 4.31, 83.66]


def test_parser_reads_all_six_joints_and_the_world_tcp():
    j, tcp = rc.parse_curpos(ASSUMED_PAGE)
    assert j == [10.5, -20.0, 30.25, 0.0, -90.0, 180.0]
    assert tcp == [400.0, -50.0, 300.0, 180.0, 0.0, 90.0]


@pytest.mark.parametrize("page", [
    "",                                                        # empty
    "Joint\n J1 = 1 J2 = 2 J3 = 3 J4 = 4 J5 = 5\n",            # J6 missing
    "Joint\n J1 = 1 J2 = 2 J3 = 3 J4 = 4 J5 = 5 J6 = 9999\n",  # not an angle
    "<html>Not Found</html>",
])
def test_parser_refuses_anything_but_a_complete_joint_set(page):
    assert rc.parse_curpos(page) == (None, None)


class FakeSession:
    def __init__(self, text, status=200):
        self.text, self.status, self.calls = text, status, []

    def get(self, url, timeout=None):
        self.calls.append(("GET", url))
        return types.SimpleNamespace(text=self.text, status_code=self.status,
                                     raise_for_status=lambda: None if self.status < 400 else (_ for _ in ()).throw(RuntimeError("http")))

    def close(self): pass

    def __getattr__(self, name):                               # post/put/delete/... would land here
        raise AssertionError(f"FANUC source tried requests.{name} - read-only violation")


def source(page):
    s = rc.FanucWebSource("192.0.2.10", 4.0)
    s.http = FakeSession(page)
    return s


def test_sample_is_in_radians_with_the_j2_j3_coupling_and_only_one_get():
    s = source(ASSUMED_PAGE)
    smp = s.read()
    assert s.http.calls == [("GET", "http://192.0.2.10/MD/CURPOS.DG")]
    assert smp.q[0] == pytest.approx(math.radians(10.5))
    assert smp.q[2] == pytest.approx(math.radians(30.25))                # robot's own convention
    c = rc.Collector.__new__(rc.Collector)
    c.args = types.SimpleNamespace(source="fanuc")
    assert c.twin_q(smp.q)[2] == pytest.approx(math.radians(30.25 - 20.0))   # twin: J3 + J2 (to confirm)
    assert smp.tcp[:3] == pytest.approx([0.4, -0.05, 0.3])              # mm -> m, once
    assert smp.extra["joints_deg"][5] == 180.0


def test_an_unconfirmed_page_raises_instead_of_reporting_a_pose():
    with pytest.raises(ValueError):
        source("<html>login</html>").read()


def test_the_fanuc_source_has_no_write_path():
    """No HTTP verb but GET, no socket writes, no FANUC write vocabulary in the source class."""
    import ast, textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(rc.FanucWebSource)))
    cls = tree.body[0]
    cls.body = [b for b in cls.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
    code = ast.unparse(tree)                                    # the code, without its description
    for bad in (".post(", ".put(", ".patch(", ".delete(", ".request(", "socket", "KAREL", "SET_", "WRITE",
                "/KCL", "/COMET", "SETREG", "SETVAR", "RUN", "ABORT", "RESET"):
        assert bad not in code.upper() if bad.isupper() else bad not in code, bad



def test_a_j2_only_move_is_reported_as_j2_only():
    """Live 2026-10-14: J2 moved 33 deg and the log also said 'J3 moved 32 deg' (coupling applied
    before motion detection)."""
    from robot_state import RobotMotion, Sample
    m = RobotMotion()
    q0 = [math.radians(v) for v in (-2.86, -18.09, -11.55, 3.02, -74.02, -1.62)]
    events = []
    for k in range(40):                                   # J2 moves 33 deg over 2 s, then rests
        q = list(q0)
        q[1] += math.radians(33.0) * min(1.0, k / 20)
        events += m.update(Sample(t=k * 0.1, q=q), arrival=k * 0.1)
    moved = {e.joint for e in events if e.kind == "JOINT_MOVED"}
    assert moved == {1}
