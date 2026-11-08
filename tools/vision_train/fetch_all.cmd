@echo off
rem 2026-11-02: download every object zip from the owner's BSc Drive folder into data\raw_all
cd /d "%~dp0"
".venv\Scripts\python.exe" -I -m gdown --folder "https://drive.google.com/drive/folders/12DlDTUkGZK3G37YGxNNONLzUJKG07xrk" -O data\raw_all > data\raw_all\fetch.log 2>&1
echo done > data\raw_all\fetch_done.txt
