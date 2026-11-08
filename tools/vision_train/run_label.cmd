@echo off
rem 2026-11-02: automatic boxes for every object photo (prepare_lab.py label), detached from the editor
cd /d "%~dp0"
".venv\Scripts\python.exe" -I prepare_lab.py label yolov8m-worldv2.pt > data\lab_label.log 2>&1
echo done > data\lab_label_done.txt
