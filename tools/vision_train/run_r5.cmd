@echo off
rem Round-5 bin training (2026-10-29): round 4 + 33 frames of the owner's video, from the deployed round-4 YOLO11n
cd /d "%~dp0data\bin_r5"
"%~dp0.venv\Scripts\python.exe" -I "%~dp0train_bin.py" ..\bin_r4\runs\detect\runs\y11\weights\best.pt y11 30 > y11.log 2>&1
echo done > r5_done.txt
