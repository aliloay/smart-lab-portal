@echo off
rem Switch round 1 finish (2026-10-30): waits for the sw11 training, then scores it on unseen scenes (eval_switch.py:
rem 29 held-out switch photos vs 461 no-switch pictures) and exports best.onnx for the portal. Nothing is deployed here.
cd /d "%~dp0data\switch_r1"
:wait
if not exist "%~dp0data\switch_r1\sw_done.txt" ( timeout /t 120 /nobreak >nul & goto wait )
"%~dp0.venv\Scripts\python.exe" -I "%~dp0eval_switch.py" "runs\detect\runs\sw11\weights\best.pt" > switch_eval.log 2>&1
"%~dp0.venv\Scripts\python.exe" -I -c "from ultralytics import YOLO; YOLO('runs/detect/runs/sw11/weights/best.pt').export(format='onnx', imgsz=640)" >> switch_eval.log 2>&1
echo done > switch_eval_done.txt
