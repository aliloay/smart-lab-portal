# Smart Lab - troubleshooting (2026-11-03)

First look: the **"Smart Lab - Status"** window (or `scripts\status.ps1`), then `logs\<service>.log`.

| Symptom | Likely cause | Fix |
|---|---|---|
| Everything slow, Status says LOW MEMORY | 16 GB nearly full (VS Code, Chrome, a Docker build) | Close browser tabs, extra VS Code windows; never build/test during the demo |
| Service STARTING for > 3 min | model load under memory pressure, or a console window paused by a click | Press Esc in its window (title "Select ..."); check its log; close window + run launch.bat again |
| Service DOWN | crashed or closed | `logs\<service>.log` last lines; run launch.bat again (starts only missing ones) |
| portal health "no answer" | backend container restarting | `docker compose ps`; wait 30-60 s; `docker compose logs --tail 50 backend` |
| A container "created"/"exited" | started while RAM was exhausted | `docker compose up -d --no-build db backend frontend backup` after freeing RAM |
| Docker not answering | Docker Desktop not started | Start Docker Desktop, wait for "Engine running" |
| UR5e/FANUC "connection failed" | not on the lab cable, or route via Wi-Fi | preflight Network rows; `scripts\fix_lab_routing.ps1` (dry run, then -Apply as admin) |
| Phones / ESP32 cannot reach the laptop | firewall rule missing | `firmware\face_server\allow_firewall.bat` as administrator |
| Phone hotspot peer can reach the portal | old unscoped rule | re-run allow_firewall.bat (now lab + GIU networks only) |
| Assistant slow (30-60 s) | cameras live -> assistant on CPU (camera-first rule) | expected; first question after 30 idle min also loads the model (~3-10 s) |
| `/gpu-gate` 401 | called without the X-KB-Key header | preflight sends it; manual: header from tools\knowledge\config.json |
| GIU PC cannot open https://ENG_IP | relay not running / IT rule missing / cert warning | relay window shows "refused"/"FAILED"; accept the cert warning once |
| Relay log "refused (not in --allow)" | client from another network (e.g. hotspot) | intended; add `--allow <net>` only with GIU IT's OK |
| Screen share button does nothing on a GIU PC | page opened over http | agent opens https://ENG_IP since 2026-11-03; or pass `--web https://ENG_IP` |
| Lab PC offline though agent runs | wrong DEVICE_KEY or --device id | agent window shows 401/404; copy DEVICE_KEY from the laptop .env |

Rollbacks of tonight's changes: certificate -> backups\tls_20261103; firewall script -> backups\allow_firewall.bat.2026-11-03.bak;
WSL limits -> delete %USERPROFILE%\.wslconfig and reboot; Ollama keep-alive -> "24h" in agent.py / ai.py.
