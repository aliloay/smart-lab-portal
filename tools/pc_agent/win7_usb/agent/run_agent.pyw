"""Smart Lab PC agent - invisible start (no window), used by the scheduled task "Smart Lab PC agent"
(at every sign-in, and again every minute: a stopped agent is back within a minute; a second copy
exits by itself). Reads agent.env next to this file; output goes to agent.log (kept under 1 MB)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
log = os.path.join(HERE, "agent.log")
try:
    if os.path.getsize(log) > 1_000_000:
        os.replace(log, log + ".1")
except OSError:
    pass
sys.stdout = sys.stderr = open(log, "a", encoding="utf-8", buffering=1)
env = {}
for line in open(os.path.join(HERE, "agent.env"), encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
os.environ["DEVICE_KEY"] = env.get("DEVICE_KEY", "")
sys.argv = ["pc_agent.py", "--device", env["DEVICE_UID"], "--asset", env.get("ASSET_TAG", env["DEVICE_UID"]),
            "--lab", env.get("LAB", "LAB_01"), "--portal", env["PORTAL"]]
if env.get("OPEN_PORTAL", "1") != "0":                 # lab PCs: portal sign-in page at every Windows sign-in
    sys.argv.append("--open-portal")
sys.path.insert(0, HERE)
import pc_agent  # noqa: E402  (reads DEVICE_KEY at import)
pc_agent.main()
