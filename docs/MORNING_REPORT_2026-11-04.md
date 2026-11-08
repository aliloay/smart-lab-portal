# Morning report 2026-11-04 (written 02:50, before power-off)

## Training (Colab v2 Chrome / v3 Edge) - fetched, compared, NOT deployed
Results: `C:\Users\dell\Downloads\colab_results_2026-11-04\{v2,v3}` (best.json, test_report.json, lab_detector.onnx).
Same hand-checked test split as the live model (171 objects, 12 classes).

| Model | mAP50 | mAP50-95 | found/171 | false | ms |
|---|---|---|---|---|---|
| LIVE r1_n (11-02) | 0.947 | **0.839** | 148 | - | 4.9 |
| v2 r2_n (v2 pick) | **0.973** | 0.835 | 152 | 1 | 4.2 |
| v2 r1_n | 0.926 | 0.808 | **163** | 1 | 6.4 |
| v3 r1_s (v3 pick) | 0.913 | 0.820 | 153 | 0 | 8.2 |
| v3 r1_m / r2_m | 0.93 | 0.79-0.81 | 147-152 | 0-1 | 18 |

Verdict: none is clearly better (v2 r2_n: more found, higher mAP50, but slightly lower mAP50-95 and 1 false hit
on an empty frame). Live model kept (md5 C678E06C...). Bigger "m" models are slower and not more accurate.
If you prefer recall (find more objects), v2 r2_n is the candidate - say "deploy v2" and I swap it with a backup.

## Tests (21:2x-22:xx, after the deploy) - all pass
backend 736 passed / 2 skipped · security_vision 295 · knowledge 49 · robot_monitor 43 · pc_agent 15 ·
lan_presence 6 · relay 5 · frontend tsc clean, vite build OK · USB kit double-click sandbox OK.
Log: `logs\tests_2026-11-03_night.txt`.

## Portal
Deployed (today's images), https://192.168.1.200 -> 200, all containers healthy at 02:50.

## Not committed (deployed in the images, waiting for your OK)
App.tsx, auth.tsx, WatchShare.tsx, pcStatus.ts, RobotTwin*, pc_agent.py, relay.py, stop_all.bat,
start_security_vision.bat, security_vision.py and others (`git status`).

## Your items at the lab
1. Print `lab_qr_2026-11-03\print\seccam_qr_A4.pdf` (QR stickers).
2. Copy `lab_usb_kit` (with device.key + python) to the stick; double-click 1_ENGINEER on Hemaly's PC, 2_LAB on each lab PC.
3. Engineer PC: allow pythonw in Windows Firewall if asked.
4. Physical tests: share / mirror / exam on 3 PCs; robot "driven by" line (pendant vs hand-guiding).
