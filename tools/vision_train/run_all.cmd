@echo off
rem Combined detector (2026-10-30): reusable_bin + network_switch + network_router in ONE YOLO11n (data\all_r1)
cd /d "%~dp0data\all_r1"
"%~dp0.venv\Scripts\python.exe" -I "%~dp0train_bin.py" "%~dp0yolo11n.pt" all11 60 > all11.log 2>&1
echo done > all_done.txt
