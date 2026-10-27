@echo off
rem Double-click: deploy the current code (asks for your admin password at a hidden prompt; window stays open).
cd /d "%~dp0..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy_now.ps1"
pause
