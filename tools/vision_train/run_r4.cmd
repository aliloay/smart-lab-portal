@echo off
rem Round-4 bin training, detached from the editor (2026-10-29): resume YOLO11n, then YOLO26n from its round-3 weights
cd /d "%~dp0data\bin_r4"
"%~dp0.venv\Scripts\python.exe" -I -c "from ultralytics import YOLO; YOLO('runs/detect/runs/y11/weights/last.pt').train(resume=True)" > y11_resume.log 2>&1
"%~dp0.venv\Scripts\python.exe" -I "%~dp0train_bin.py" ..\bin_r3\runs\detect\runs\y26\weights\best.pt y26 40 > y26.log 2>&1
echo done > r4_done.txt
