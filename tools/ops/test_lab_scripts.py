"""Static guards for the two lab-day PowerShell scripts (2026-11-17). They never execute the scripts.

Run: py -m pytest -q tools/ops/test_lab_scripts.py
Both scripts must stay READ-ONLY (they run at the lab next to door, robots and cameras), cover all four ESP32 nodes,
signal failure through the exit code (preflight) and write NA - never a fabricated 0 - for sources they cannot read (snapshot).
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PRE = ROOT / "scripts" / "lab_preflight.ps1"
SNAP = ROOT / "scripts" / "lab_snapshot.ps1"
pre_text = PRE.read_text(encoding="utf-8")
snap_text = SNAP.read_text(encoding="utf-8")

# anything that could change the network, firewall, processes, containers, or write to a device/API
STATE_CHANGING = re.compile(
    r"(Set-NetIPAddress|New-NetIPAddress|Remove-Net\w+|Set-NetFirewall\w*|New-NetFirewall\w*|Set-NetRoute|route\s+add|netsh|"
    r"Stop-Process|Stop-Service|Restart-\w+|Start-Process|taskkill|"
    r"docker\s+(run|rm|stop|kill|restart|start|exec\s+-i\s+\S+\s+sh\s+-c\s+'[^']*(insert|update|delete|drop|truncate))|"
    r"docker\s+compose\s+(up|down|restart|stop|start|rm)|"
    r"-Method\s+(Post|Put|Patch|Delete)|Set-Content\s+(?!-Encoding\s+utf8\s+\$out)|Remove-Item)", re.I)


@pytest.mark.skipif(shutil.which("powershell") is None, reason="Windows PowerShell not available")
@pytest.mark.parametrize("script", [PRE, SNAP], ids=["preflight", "snapshot"])
def test_script_parses_without_syntax_errors(script):
    cmd = ("$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile("
           f"'{script}',[ref]$t,[ref]$e); if ($e.Count) {{ $e | ForEach-Object {{ $_.Message }}; exit 1 }}")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout[-300:]


@pytest.mark.parametrize("name,text", [("preflight", pre_text), ("snapshot", snap_text)])
def test_scripts_contain_no_state_changing_command(name, text):
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    bad = STATE_CHANGING.findall(code)
    assert not bad, f"{name} contains state-changing commands: {bad}"


def test_preflight_covers_all_four_esp32_nodes_with_the_firmware_addresses():
    for ip in ("192.168.1.151", "192.168.1.152", "192.168.1.153", "192.168.1.154"):     # Master, Environment, Consumables, Reusable
        assert f"ip = '{ip}'" in pre_text, ip
    assert "192.168.1.150" in pre_text                                                    # ESP32-CAM


def test_preflight_signals_failure_in_its_exit_code_and_does_not_blame_firmware_for_silence():
    assert re.search(r"exit \$\(if \(\$f\) \{ 1 \} else \{ 0 \}\)", pre_text)
    assert "not a verdict on its firmware" in pre_text


def test_preflight_never_prints_the_knowledge_key():
    assert "$kbKey" in pre_text
    assert not re.search(r"Write-Host[^\n]*\$kbKey", pre_text) and not re.search(r"Add\s[^\n]*\$kbKey", pre_text)


def test_snapshot_reads_the_database_only_with_select_and_writes_only_its_csv():
    assert "select device_uid" in snap_text and not re.search(r"\b(insert|update|delete|drop|truncate|alter)\b\s", snap_text, re.I)
    assert snap_text.count("Export-Csv") == 1 and "-Append" in snap_text


def test_snapshot_writes_na_for_unreadable_sources_and_never_overwrites_a_log():
    assert "$NA = 'NA'" in snap_text
    for token in ("docker_up", "ollama_models = $olN", "gpu_mem_mb = $(if ($gOk)", "'unregistered'"):
        assert token in snap_text, token
    assert "$olN = $NA; $olV = $NA" in snap_text            # Ollama unreachable -> NA, not 0 models
    assert "-f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'), $PID" in snap_text


def test_snapshot_supports_the_protected_data_folder_and_does_not_print_secrets():
    assert "[string]$OutDir" in snap_text
    for bad in ("X-KB-Key", "service_key", "DEVICE_API_KEY", "password", "rtsp://"):
        assert bad.lower() not in snap_text.lower(), bad
