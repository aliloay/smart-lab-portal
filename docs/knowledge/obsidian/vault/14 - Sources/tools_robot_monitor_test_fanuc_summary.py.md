---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/robot_monitor/test_fanuc_summary.py"
source_hash: "44238b2de80d4cd24d3bb81f6864c6bdfd96092cd359b6abcea25d7a6e40449b"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/robot_monitor/test_fanuc_summary.py` - edit the original in the repository, not this note.

Systems: [[Robots (read-only)]]

## Related
- [[tools_robot_monitor_fanuc_summary.py]] - tests

```py
"""fanuc_summary.py reads a saved SUMMARY.DG page: identity, installed vs DEMO options. No robot contact."""
import os
import glob

import pytest

import fanuc_summary as fs

# Same layout as the real page (fixed-width option table); serial numbers replaced by placeholders.
PAGE = """VERSION INFORMATION::
SOFTWARE:              ID:
LR HandlingTool       7DF3/12
S/W Serial No.      : 00000
Controller ID       : 0000000
Robot No.           : E000000
Manufacturing ID    : XX00000
Default Personality (from FD)
ER-4iA                V9.30P/12
Servo Code          : V09.00
DCS                 : V4.2.14
Stop pattern        : D
Software Edition No.: V9.30P/12
Root Version        : V9.30107
Media from FRL        11/17/2020

CONFIG::
FEATURE:              ORD NO:
LR HandlingTool       H551
Dual Check Safety UIF DCSU
Mate controller       MATE
All Smooth Stop       J651
KAREL                 R632
PC Interface          R641
User Socket Msg       R648
Prog Num Selection    J515

CONFIG2::
DEMO. FEATURE:        ORD NO:
HMI Device (SNPX)     R553

MOTOR::
    GR: AX:     MOTOR ID AND INFO:
"""


def test_identity_without_serial_numbers():
    r = fs.parse(PAGE)
    idn = r["identity"]
    assert idn["Application"] == "LR HandlingTool" and idn["Robot"] == "ER-4iA"
    assert idn["Robot software"] == "V9.30P/12" and idn["DCS"] == "V4.2.14" and idn["Stop pattern"] == "D"
    assert idn["Media from FRL"] == "11/17/2020"
    assert not {"S/W Serial No.", "Controller ID", "Robot No.", "Manufacturing ID"} & set(idn)
    assert r["mate_controller"] is True


def test_fixed_width_table_and_demo_options_are_kept_apart():
    r = fs.parse(PAGE)
    assert {"name": "Dual Check Safety UIF", "order": "DCSU"} in r["features"]     # one space before DCSU
    assert r["interfaces_installed"] == ["User Socket Msg R648", "PC Interface R641", "KAREL R632",
                                         "Prog Num Selection J515"]
    assert r["interfaces_demo"] == ["HMI Device (SNPX) R553"]                       # time-limited, not installed
    assert r["demo_lists"] == 1 and r["stop_options_installed"] == ["All Smooth Stop J651"]


def test_cli_prints_a_summary(tmp_path, capsys):
    p = tmp_path / "SUMMARY.DG.txt"
    p.write_text(PAGE, encoding="utf-8")
    assert fs.main([str(p)]) == 0
    out = capsys.readouterr().out
    assert "ER-4iA V9.30P/12 - Mate controller" in out and "only as DEMO" in out and "E000000" not in out


REAL = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "fanuc_probe_out", "*_MD_SUMMARY.DG.txt")))


@pytest.mark.skipif(not REAL, reason="no saved SUMMARY.DG (fanuc_probe_out/ is local only)")
def test_the_real_saved_page_from_the_lab_controller():
    with open(REAL[-1], encoding="utf-8", errors="replace") as f:
        r = fs.parse(f.read())
    assert r["identity"]["Robot"] == "ER-4iA" and r["identity"]["Application"] == "LR HandlingTool"
    assert len(r["features"]) == 220 and r["demo_lists"] == 1 and r["demo_features"] == []   # DEMO list empty
    assert "User Socket Msg R648" in r["interfaces_installed"] and "PC Interface R641" in r["interfaces_installed"]

```
