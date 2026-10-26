@echo off
rem Smart Lab - stop everything that launch.bat started, in one click.
rem   1. closes every window titled "Smart Lab - ..." (portal log, face server,
rem      security camera, UR5e monitor, knowledge service, AI model helper)
rem   2. stops the Docker containers (portal, API, database, n8n) - "stop", not
rem      "down": nothing is deleted, the database and all data are kept.
rem Ollama (tray icon) and Docker Desktop keep running so the next start is fast.
rem Start again: double-click launch.bat  (or restart_all.bat does both).
setlocal
cd /d "%~dp0"
echo Closing the Smart Lab windows...
taskkill /fi "WINDOWTITLE eq Smart Lab - *" /t /f >nul 2>&1
rem Python services whose window title changed while running (safety net, by script name only)
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^py(thon)?(w)?\.exe$' -and $_.CommandLine -match 'security_vision\.py|robot_collector\.py|tools\\knowledge\\serve\.py|face_server|voice_service\.py|ur_local_control\.py|opcua_server\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker is not running - nothing else to stop.
) else (
  echo Stopping the portal containers ^(data is kept^)...
  docker compose --profile automation stop
)
echo.
echo Smart Lab stopped. Start again with launch.bat.
timeout /t 4 >nul
