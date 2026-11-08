"""The reported analysis rate must drop to 0 when analysis stops (2026-10-14 at the lab:
the analysis thread stopped after 45 passes while /health kept saying 5 fps, 2 people)."""
import time
import types

import security_vision as sv


def _svc(fps, analysed_ago):
    s = types.SimpleNamespace(fps=fps, analysed_at=time.time() - analysed_ago if analysed_ago is not None else 0.0)
    return sv.Service.live_fps(s)


def test_fresh_analysis_reports_its_rate():
    assert _svc(5.0, 0.2) == 5.0


def test_stalled_analysis_reports_zero_not_the_old_rate():
    assert _svc(5.0, 10) == 0.0


def test_never_analysed_reports_zero():
    assert _svc(5.0, None) == 0.0
