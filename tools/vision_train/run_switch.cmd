@echo off
rem Switch detector training (2026-10-29): waits for bin round 5, then YOLO11n on data\switch_r1 (owner's TP-Link switch)
cd /d "%~dp0data\switch_r1"
:wait
if not exist "%~dp0data\bin_r5\r5_done.txt" ( timeout /t 60 /nobreak >nul & goto wait )
"%~dp0.venv\Scripts\python.exe" -I "%~dp0train_bin.py" "%~dp0yolo11n.pt" sw11 40 > sw11.log 2>&1
echo done > sw_done.txt
