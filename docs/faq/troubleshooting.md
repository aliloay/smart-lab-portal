# FAQ: troubleshooting

## Q: Why is a device shown as partly working?
Also asked: DEGRADED device, orange device, camera partly working
**A:** Its reporting service runs, but the hardware behind it is not delivering: for example a camera service with no picture, or a robot collector with no robot data.
Source: `backend/app/services/devices.py` (derived state)

## Q: When does a device count as offline?
Also asked: offline timeout, how long until offline, stale device
**A:** After 90 seconds without a report (DEVICE_STALE_SECONDS). The portal recomputes this every time the device list is read.
Source: `backend/app/core/config.py`, `backend/app/services/devices.py` (refresh_liveness)

## Q: Why does the door say RFID offline?
Also asked: RFID frozen, card reader not working, PN532 not responding
**A:** The RFID reader (PN532) can freeze when the lock switches off: the lock coil's voltage spike reaches it. Only a power cycle (USB and 12 V off for 10 s) clears it. Meanwhile use your QR code or personal door QR. The fix is a 1N4007 diode across the lock.
Source: `docs/reports/MEASUREMENTS_2026-11-21.md` (findings), `firmware/SmartLab_Master_Portal` (relock guard)

## Q: Why is the AI assistant slow?
Also asked: assistant takes long, slow answers
**A:** While the security cameras analyse, the assistants run on the CPU, which takes about 10–18 s per answer. Short questions about status, labs, devices, reports and this FAQ are answered instantly without the model.
Source: `tools/knowledge/gpu_gate.py`, `backend/app/services/agent_live.py`, `docs/faq/README.md`

## Q: Why do the cameras show no picture at home?
Also asked: camera offline at home, no camera image
**A:** The two security cameras are IP cameras installed at GIU. Away from the lab, the camera services run but cannot reach them, so the cameras show as partly working with no picture.
Source: camera `/metrics` (capture fps 0, open failures)

## Q: What should be started for the lab to work?
Also asked: how to start everything, launch the services
**A:** Docker Desktop (portal, database, n8n, backups) and launch.bat started by double-clicking it in File Explorer (face server, cameras, knowledge, voice, robot monitors). Starting launch.bat from the VS Code terminal uses the wrong Python environment.
Source: `launch.bat`, `docs/PROGRESS_CHECKPOINT.md`

## Q: How do I check the whole system quickly?
Also asked: health check, is everything running, system doctor
**A:** Run `smartlab doctor` in a terminal: a read-only check of the portal, containers, services, cameras, ESP32 boards, AI models, GPU gate, disk and git, each marked PASS, WARN or FAIL. The portal's System Health page shows the same from the server's side.
Source: `tools/smartlab_cli/` (cli-anything-smartlab)
