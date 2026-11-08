@echo off
rem Overnight lab-detector round 2 (2026-11-03), detached from the editor, low CPU priority (the laptop stays usable).
cd /d "%~dp0"
if not exist data\lab_r2 mkdir data\lab_r2
rem window title NOT "Smart Lab - ..." - stop_all.bat closes those (it ended the first run at 19:03, 2026-11-03)
start "SmartLab training (overnight r2)" /low /min cmd /c ""%~dp0.venv\Scripts\python.exe" -I "%~dp0overnight_r2.py" > "%~dp0data\lab_r2\train.log" 2>&1"
