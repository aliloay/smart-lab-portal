@echo off
rem Smart Lab - stop the project's containers and keep all data (runs stop.ps1).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
