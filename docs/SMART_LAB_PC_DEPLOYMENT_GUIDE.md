# Smart Lab - Engineer PC and lab PC deployment (2026-11-03)

**Needs GIU IT / the lab engineer:** the engineer PC's USB-Ethernet adapter, its firewall rule for the relay, and
permission to run Python foreground programs on GIU PCs. Nothing below installs anything or changes a GIU policy.
**Never run `tools\pc_agent\win7_usb\install.bat` on a GIU PC** (it writes a Run key and restarts explorer).

## 0. Find the real addresses first (do not assume .17/.18/.19)
On each PC: `hostname` and `ipconfig`. Write down hostname -> 10.40.20.x. The certificate already covers
10.40.20.17/.18/.19; another engineer-PC address needs the certificate step in SMART_LAB_NETWORK_CONFIGURATION.md.

## 1. Portal laptop (ADMIN-LAPTOP) - automatic
`launch.bat` starts its PC agent (`--portal http://127.0.0.1:8000/api`). Nothing to do.

## 2. Lab engineer PC (PC_ENG) - GIU Ethernet + USB-Ethernet to the Smart Lab router
1. USB-Ethernet adapter: IPv4 192.168.1.210, mask 255.255.255.0, **gateway empty**, DNS empty. GIU adapter unchanged.
2. `ping 192.168.1.200` must answer.
3. Copy the folder `tools\relay` and `tools\pc_agent` to a USB stick / temp folder on that PC (no install).
4. Window 1 - relay (GIU IT must allow inbound TCP 8000 and 443 to python.exe on the GIU adapter):
   `py relay.py --listen <ENG_GIU_IP> --map 8000=192.168.1.200:8000 --map 443=192.168.1.200:443`
   - prints "portal 192.168.1.200:8000 reachable - OK";
   - only clients from 10.40.20.0/24, 192.168.1.0/24 and the PC itself get through (`--allow` to change);
   - port 80 is optional (often taken on Windows); the agent uses https://<ENG_GIU_IP> anyway.
5. Window 2 - agent:
   `set DEVICE_KEY=<DEVICE_KEY from the laptop's .env>`
   `py pc_agent.py --device PC_ENG --lab LAB_01 --portal http://192.168.1.200:8000/api`
   (or fill `agent.env` from agent.env.example and run `start_pc_agent.bat`)
6. Portal -> Equipment: PC_ENG turns online with a screen preview within a few seconds.
Rollback: Ctrl+C in both windows, delete the copied folder, unplug the USB adapter (and IT removes its rule).

## 3. Each approved GIU lab PC (PC_01, PC_02, ...)
1. `Test-NetConnection <ENG_GIU_IP> -Port 8000` and `-Port 443` -> TcpTestSucceeded True.
2. Copy `tools\pc_agent` to a temp folder. Foreground window:
   `set DEVICE_KEY=<DEVICE_KEY from the laptop's .env>`
   `py pc_agent.py --device PC_01 --asset PC-01 --lab LAB_01 --portal http://<ENG_GIU_IP>:8000/api`
   (the agent now opens the portal pages at https://<ENG_GIU_IP> by itself - needed for screen sharing)
3. Browser on that PC: `https://<ENG_GIU_IP>/` -> accept the certificate warning once (or install
   deploy\tls\smartlab-ca.crt only if GIU IT allows it).
Windows 7 PCs: Python 3.8 runs the same agent (syntax checked for 3.8).
Rollback: Ctrl+C, delete the temp folder. No registry or startup change.

## 4. What crosses the relay and what does not
Works: agent heartbeat/online state, screen thumbnails and focus view, admin broadcast, share requests (HTTPS),
normal / exam mode. Does not: lan_presence ARP/ping discovery of GIU PCs (layer 2 does not cross a TCP relay) -
GIU PCs are shown online by their agent heartbeat instead.

## Tested offline tonight
relay 5 tests (incl. allow-list refuses a 172.20.10.x hotspot peer) + live relay to the running portal (API 200,
HTTPS 200); pc_agent 15 tests incl. the https web address over a relay. Not tested: a real GIU PC and the engineer PC.
