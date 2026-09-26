@echo off
rem Checks the n8n automation end to end. Portal and n8n must be running.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0automation\n8n\test-automation.ps1"
pause
