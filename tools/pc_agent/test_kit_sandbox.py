"""
Runs the PowerShell kit for real on this PC, as this standard user, against a stub portal on loopback (2026-11-07).
Not part of pytest: it installs, starts and removes real processes.    py tools/pc_agent/test_kit_sandbox.py <scratch dir>

Uses its own install folder and HKCU Run name, and removes both at the end. It tests this one Windows account only.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import winreg
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "lab_usb_kit")
SCRATCH = sys.argv[1]
ROOT, COPY, RUN = os.path.join(SCRATCH, "installed"), os.path.join(SCRATCH, "kit"), "SmartLabSandboxTest"
PORT, DEVICE = 18765, "PC_SANDBOX"
AGENT = "pc_agent[.]py"         # the folder is also called pc_agent
SECRET = "sandbox-device-key-not-a-real-one"
seen = {"enroll": [], "polls": 0, "bad_key": 0}
results = []


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, body, code=200):
        data = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); raw = self.rfile.read(n)
        if self.path.endswith("/pc/enroll"):
            seen["enroll"].append(json.loads(raw)); return self._send({"device_uid": DEVICE, "device_key": SECRET})
        self._send({"mode": "NORMAL"})

    def do_GET(self):
        if "/pc/poll" in self.path or "/pc/wait" in self.path:
            if self.headers.get("X-Device-Key") != SECRET:
                seen["bad_key"] += 1; return self._send({"detail": "bad key"}, 401)
            seen["polls"] += 1
            return self._send({"mode": "NORMAL"})
        self._send({})


def serve():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def ps(script, *args):
    r = subprocess.run(["powershell.exe", "-NoProfile", "-File", os.path.join(COPY, script), *args], capture_output=True, text=True, timeout=240)
    return r.stdout + r.stderr


def ps_allowed():
    """Script execution is a machine policy. This test does not override it: if it is off, the scripts stay untested here."""
    return "running scripts is disabled" not in ps("Stop-Agent.ps1", "-InstallRoot", ROOT)


def direct_install():
    """What Install-CurrentUser.ps1 does for the agent, step by step, with PowerShell's own DPAPI call for the code."""
    os.makedirs(ROOT, exist_ok=True)
    for d in ("python", "pc_agent", "relay"):
        shutil.copytree(os.path.join(COPY, d), os.path.join(ROOT, d), dirs_exist_ok=True)
    code = open(os.path.join(COPY, "enroll.key")).read().strip()
    cmd = ("Add-Type -AssemblyName System.Security; $b=[Text.Encoding]::UTF8.GetBytes('" + code + "'); "
           "$p=[Security.Cryptography.ProtectedData]::Protect($b,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser); "
           "[IO.File]::WriteAllText('" + os.path.join(ROOT, "enroll.key") + "','DPAPI1:'+[Convert]::ToBase64String($p))")
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], check=True, capture_output=True)
    key = os.path.join(ROOT, "device.key")
    cfg = dict(device=DEVICE, portal=f"http://127.0.0.1:{PORT}/api", agent_args=["--device", DEVICE, "--lab", "LAB_01", "--portal", f"http://127.0.0.1:{PORT}/api", "--web", "https://127.0.0.1/", "--key-file", key, "--enroll-file", os.path.join(ROOT, "enroll.key")], relay_args=[], wait_for_other_account=True)
    open(os.path.join(ROOT, "smartlab.json"), "w").write(json.dumps(cfg))
    start_direct()


def start_direct():
    subprocess.Popen([os.path.join(ROOT, "python", "pythonw.exe"), "-E", "-s", os.path.join(ROOT, "pc_agent", "agent_boot.py"), "--config", os.path.join(ROOT, "smartlab.json")], cwd=ROOT)


def stop_direct():
    for pat in ("agent_boot", AGENT):
        for pid in procs(pat):
            subprocess.run(["powershell.exe", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"], capture_output=True)


def procs(pattern):
    out = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | Where-Object { $_.CommandLine -like '*" + ROOT + "*' -and $_.CommandLine -match '" + pattern + "' } | ForEach-Object { $_.ProcessId }"],
                         capture_output=True, text=True).stdout.split()
    return [int(x) for x in out]


def run_entry():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
        try:
            return winreg.QueryValueEx(k, RUN)[0]
        except OSError:
            return None


def check(name, ok, detail=""):
    results.append(dict(test=name, passed=bool(ok), detail=str(detail)[:300])); print("PASS" if ok else "FAIL", name, detail if not ok else "", flush=True)


def wait(fn, secs):
    t = time.time()
    while time.time() - t < secs:
        if fn():
            return True
        time.sleep(1)
    return False


def status():
    try:
        return open(os.path.join(os.environ["TEMP"], "smartlab_status.txt"), encoding="utf-8").read().strip()
    except OSError:
        return ""


def main():
    if subprocess.run(["net", "session"], capture_output=True).returncode == 0:
        print("NOTE: this shell is elevated, so this is not a standard-user test")
    results.append(dict(test="standard user (net session refused)", passed=subprocess.run(["net", "session"], capture_output=True).returncode != 0, detail=""))
    shutil.rmtree(SCRATCH, ignore_errors=True); os.makedirs(SCRATCH)
    shutil.copytree(KIT, COPY)
    # the copy's site points at the stub; the manifest entry is updated to match
    site = json.load(open(os.path.join(COPY, "site.json")))
    site.update(portal_direct=f"http://127.0.0.1:{PORT}/api", portal_via_relay=f"http://127.0.0.1:{PORT}/api", web_direct="https://127.0.0.1/", web_via_relay="https://127.0.0.1/", engineer_hosts=[], relay_address="203.0.113.1")
    open(os.path.join(COPY, "site.json"), "w").write(json.dumps(site))
    m = json.load(open(os.path.join(COPY, "MANIFEST.json")))
    m["files"]["site.json"] = hashlib.sha256(open(os.path.join(COPY, "site.json"), "rb").read()).hexdigest()
    open(os.path.join(COPY, "MANIFEST.json"), "w").write(json.dumps(m))
    srv = serve()
    if not ps_allowed():
        results.append(dict(test="PowerShell scripts executed", passed=False, detail="NOT RUN: script execution is disabled on this machine and was not overridden"))
        print("NOTE: scripts not executed (execution policy). Testing the agent, DPAPI and supervisor directly.", flush=True)
        direct_install()
        keyfile = os.path.join(ROOT, "device.key")
        check("agent enrolls from a PowerShell DPAPI code", wait(lambda: os.path.exists(keyfile), 30), seen)
        check("supervisor and one agent running", wait(lambda: len(procs("agent_boot")) == 1 and len(procs(AGENT)) == 1, 20), (procs("agent_boot"), procs(AGENT)))
        raw = open(keyfile).read()
        check("key file is DPAPI, not plain", raw.startswith("DPAPI1:") and SECRET not in raw)
        check("enrollment code removed", not os.path.exists(os.path.join(ROOT, "enroll.key")))
        check("enrollment carried an account id, no account name", seen["enroll"] and len(seen["enroll"][0].get("account", "")) == 32 and os.environ["USERNAME"].lower() not in json.dumps(seen["enroll"]).lower(), seen["enroll"])
        check("agent polls with the decrypted key", wait(lambda: seen["polls"] > 2 and seen["bad_key"] == 0, 20), seen)
        check("status file says connected", wait(lambda: status() == "connected", 15), status())
        start_direct(); time.sleep(6)
        check("second start makes no duplicate", len(procs("agent_boot")) == 1 and len(procs(AGENT)) == 1, (procs("agent_boot"), procs(AGENT)))
        pid = procs(AGENT)[0]
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"], capture_output=True)
        check("killed agent is restarted", wait(lambda: procs(AGENT) and procs(AGENT)[0] != pid, 25), procs(AGENT))
        srv.shutdown(); srv.server_close()
        check("portal gone: status offline, agent alive", wait(lambda: status() == "offline", 25) and len(procs(AGENT)) == 1, status())
        srv = serve(); p0 = seen["polls"]
        check("portal back: reconnects by itself", wait(lambda: seen["polls"] > p0 and status() == "connected", 40), status())
        n = len(seen["enroll"])
        stop_direct(); time.sleep(2); start_direct()
        check("restart keeps the key, no new enrollment", wait(lambda: len(procs(AGENT)) == 1, 20) and len(seen["enroll"]) == n and open(keyfile).read() == raw)
        stop_direct()
        check("stop leaves nothing running", wait(lambda: not procs("agent_boot|pc_agent"), 10))
        srv.shutdown()
        json.dump(results, open(os.path.join(SCRATCH, "sandbox_results.json"), "w"), indent=1)
        bad = [r["test"] for r in results if not r["passed"]]
        print(f"{len(results) - len(bad)} of {len(results)} passed", bad)
        shutil.rmtree(ROOT, ignore_errors=True)
        return 1 if bad else 0
    common = ["-InstallRoot", ROOT, "-RunName", RUN]
    out = ps("Install-CurrentUser.ps1", *common, "-Role", "Lab", "-KitDevice", DEVICE, "-SkipLegacyCleanup", "-NoPause")
    check("install ends with OK lines", "OK    agent running" in out and "OK    this account has its own key" in out, out[-500:])
    check("HKCU Run entry created", run_entry() and "pythonw" in run_entry())
    check("supervisor and one agent running", wait(lambda: len(procs("agent_boot")) == 1 and len(procs(AGENT)) == 1, 20), (procs("agent_boot"), procs(AGENT)))
    keyfile = os.path.join(ROOT, "device.key")
    raw = open(keyfile).read()
    check("key file is DPAPI, not plain", raw.startswith("DPAPI1:") and SECRET not in raw)
    check("enrollment code removed", not os.path.exists(os.path.join(ROOT, "enroll.key")))
    check("enrollment carried an account id, no account name", seen["enroll"] and len(seen["enroll"][0].get("account", "")) == 32 and os.environ["USERNAME"].lower() not in json.dumps(seen["enroll"]).lower(), seen["enroll"])
    check("agent polls with the decrypted key", wait(lambda: seen["polls"] > 2 and seen["bad_key"] == 0, 20), seen)
    plain = [f for f in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, f)) and SECRET in open(os.path.join(ROOT, f), errors="ignore").read()]
    check("no credential in clear in the install folder", not plain, plain)
    check("status file says connected", wait(lambda: status() == "connected", 15), status())

    ps("Start-Agent.ps1", "-InstallRoot", ROOT); time.sleep(6)
    check("second start makes no duplicate", len(procs("agent_boot")) == 1 and len(procs(AGENT)) == 1, (procs("agent_boot"), procs(AGENT)))

    pid = procs(AGENT)[0]
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"], capture_output=True)
    check("killed agent is restarted", wait(lambda: procs(AGENT) and procs(AGENT)[0] != pid, 25), procs(AGENT))

    srv.shutdown(); srv.server_close()
    check("portal gone: status offline, agent alive", wait(lambda: status() == "offline", 25) and len(procs(AGENT)) == 1, status())
    srv = serve(); p0 = seen["polls"]
    check("portal back: reconnects by itself", wait(lambda: seen["polls"] > p0 and status() == "connected", 40), status())

    out = ps("Check-CurrentUser.ps1", *common, "-NoPause")
    check("check script reports healthy and prints no key", "FAIL" not in out and SECRET not in out and raw[8:40] not in out, out[-500:])

    ps("Stop-Agent.ps1", "-InstallRoot", ROOT)
    check("stop leaves nothing running", wait(lambda: not procs("agent_boot|pc_agent"), 10), procs("agent_boot|pc_agent"))
    ps("Start-Agent.ps1", "-InstallRoot", ROOT)
    check("start brings it back", wait(lambda: len(procs(AGENT)) == 1, 20))

    n = len(seen["enroll"])
    out = ps("Install-CurrentUser.ps1", *common, "-Role", "Lab", "-KitDevice", DEVICE, "-SkipLegacyCleanup", "-NoPause")
    check("repair install keeps the key, no new enrollment", len(seen["enroll"]) == n and open(keyfile).read() == raw and wait(lambda: len(procs(AGENT)) == 1, 20), out[-300:])

    ps("Uninstall-CurrentUser.ps1", *common, "-NoPause")
    check("uninstall removes processes, entry and files", wait(lambda: not procs("agent_boot|pc_agent"), 10) and run_entry() is None and not os.path.exists(keyfile) and not os.path.exists(os.path.join(ROOT, "python")))
    out = ps("Install-CurrentUser.ps1", *common, "-Role", "Lab", "-KitDevice", DEVICE, "-SkipLegacyCleanup", "-NoPause")
    check("reinstall works and enrolls again", "OK    agent running" in out and len(seen["enroll"]) == n + 1, out[-300:])
    ps("Uninstall-CurrentUser.ps1", *common, "-NoPause")
    check("final uninstall clean", run_entry() is None and not procs("agent_boot|pc_agent"))
    srv.shutdown()
    json.dump(results, open(os.path.join(SCRATCH, "sandbox_results.json"), "w"), indent=1)
    bad = [r["test"] for r in results if not r["passed"]]
    print(f"{len(results) - len(bad)} of {len(results)} passed", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
