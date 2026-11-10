---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/robot_monitor/fanuc_summary.py"
source_hash: "56fdd4e5ff8fc0283b819b43eb3bf4131231681c24659f26a2e630d950998a0b"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/robot_monitor/fanuc_summary.py` - edit the original in the repository, not this note.

Systems: [[Robots (read-only)]]

## Related
- [[tools_robot_monitor_test_fanuc_summary.py]] - tests
- [[backend_app_services_robot_control.py]] - mentioned by docs
- [[docs_ROBOT_CONTROL.md]] - mentioned by docs

```py
"""
FANUC controller identity and installed options - READ-ONLY, from a saved /MD/SUMMARY.DG page.

fanuc_probe.py saves the controller's own summary page (plain HTTP GET). This file reads that saved
text and answers two questions in the controller's own words, without contacting the robot:
  1. which controller / software / robot is it (VERSION INFORMATION), and
  2. which options are installed (CONFIG > FEATURE) and which are only DEMO (time-limited) -
     so a remote HOME/STOP interface is chosen from what is really there, never assumed.

    py fanuc_summary.py fanuc_probe_out/<stamp>_<ip>_MD_SUMMARY.DG.txt [--json]

Serial numbers on the page (S/W serial, controller ID, robot no., manufacturing ID) are left out of the
output on purpose: they are not needed for the interface decision and the repository is public.
"""
from __future__ import annotations

import argparse
import json
import sys

# Options that could carry a remote HOME / STOP request, by FANUC order number.
INTERFACE_OPTIONS = {
    "R648": "User Socket Msg", "R636": "Socket Messaging", "R641": "PC Interface", "R632": "KAREL",
    "R553": "HMI Device (SNPX)", "J515": "Prog Num Selection", "SRSR": "Robot Service Request",
    "OPCU": "OPC-UA", "R538": "Ethernet/IP I/O Adp.", "R603": "ROS Ethernet Packets",
    "RMCN": "Remote Conn Standard",
}
# Stop / safety related options (information only - the portal STOP is never safety-rated).
STOP_OPTIONS = {"J651": "All Smooth Stop", "J548": "Smooth Stop Upgrade", "R534": "Collision Guard",
                "J567": "DCS Pos./Speed check", "MDSW": "Mode Switch", "J541": "Password Protection"}
SERIAL_KEYS = {"S/W Serial No.", "Controller ID", "Robot No.", "Manufacturing ID"}


def _feature_lines(lines: list[str], i: int) -> tuple[list[dict], int]:
    """Read one 'FEATURE: ORD NO:' table starting at its header line i; returns (rows, next index).
    The page is fixed-width: the order number starts in the header's 'ORD NO:' column (a name can
    reach that column with a single space, e.g. 'Dual Check Safety UIF DCSU')."""
    col = lines[i].index("ORD NO:")
    rows, i = [], i + 1
    while i < len(lines) and lines[i].strip() and not lines[i].strip().endswith("::") and "ORD NO:" not in lines[i]:
        line = lines[i].rstrip()
        name, order = line[:col].strip(), line[col:].strip()
        if name:
            rows.append({"name": name, "order": order})
        i += 1
    return rows, i


def parse(text: str) -> dict:
    lines = text.replace("\r", "").split("\n")
    out: dict = {"identity": {}, "features": [], "demo_features": [], "demo_lists": 0}
    section, after_personality, after_software = None, False, False
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.endswith("::"):
            section = s[:-2]
            i += 1
            continue
        if "ORD NO:" in s and s.startswith(("FEATURE:", "DEMO. FEATURE:")):
            rows, i = _feature_lines(lines, i)
            if s.startswith("DEMO"):
                out["demo_lists"] += 1
                out["demo_features"] += rows
            elif section == "CONFIG":
                out["features"] += rows
            continue
        if section == "VERSION INFORMATION" and s:
            ident = out["identity"]
            if s.startswith("SOFTWARE:"):
                after_software = True
            elif s.startswith("Default Personality"):
                after_personality = True
            elif ":" in s:
                k, v = (p.strip() for p in s.split(":", 1))
                if k not in SERIAL_KEYS:
                    ident[k] = v
            else:
                name, _, value = s.rpartition(" ")
                if after_personality:                      # 'ER-4iA                V9.30P/12'
                    ident["Robot"], ident["Robot software"] = name.strip(), value
                    after_personality = False
                elif after_software:                       # 'LR HandlingTool       7DF3/12'
                    ident["Application"], ident["Application ID"] = name.strip(), value
                    after_software = False
                elif s.startswith("Media from FRL"):
                    ident["Media from FRL"] = value
        i += 1
    orders = {f["order"]: f["name"] for f in out["features"]}
    demo = {f["order"]: f["name"] for f in out["demo_features"]}
    out["mate_controller"] = any(f["name"].startswith("Mate controller") for f in out["features"])
    out["interfaces_installed"] = [f"{orders[o]} {o}" for o in INTERFACE_OPTIONS if o in orders]
    out["interfaces_demo"] = [f"{demo[o]} {o}" for o in INTERFACE_OPTIONS if o in demo]
    out["stop_options_installed"] = [f"{orders[o]} {o}" for o in STOP_OPTIONS if o in orders]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read a saved FANUC /MD/SUMMARY.DG page (read-only).")
    ap.add_argument("summary")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    with open(a.summary, encoding="utf-8", errors="replace") as f:
        r = parse(f.read())
    if a.json:
        print(json.dumps(r, indent=2))
        return 0
    idn = r["identity"]
    print(f"Application : {idn.get('Application')} ({idn.get('Software Edition No.')}, root {idn.get('Root Version')})")
    print(f"Robot       : {idn.get('Robot')} {idn.get('Robot software')}"
          f"{' - Mate controller' if r['mate_controller'] else ''}")
    print(f"DCS {idn.get('DCS')} | servo {idn.get('Servo Code')} | stop pattern {idn.get('Stop pattern')}")
    print(f"Installed options: {len(r['features'])}; DEMO lists: {r['demo_lists']} with {len(r['demo_features'])} item(s)")
    print("Remote-interface options installed: " + (", ".join(r["interfaces_installed"]) or "none"))
    if r["interfaces_demo"]:
        print("  ...only as DEMO (time-limited): " + ", ".join(r["interfaces_demo"]))
    print("Stop/safety options installed: " + (", ".join(r["stop_options_installed"]) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

```
