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
rem 2026-11-03 (owner): "stop all should also CLOSE the windows at once". Every program of this project and the
rem cmd / PowerShell window around it (their command lines name this folder) is ended - the windows close with them.
rem Spared: this window itself and its parent, and the detached training (tools\vision_train).
powershell -NoProfile -Command "$root = '%~dp0'.TrimEnd('\'); $me = (Get-CimInstance Win32_Process -Filter \"ProcessId=$PID\").ParentProcessId; $keep = @($PID, $me, (Get-CimInstance Win32_Process -Filter \"ProcessId=$me\").ParentProcessId); Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(py|pyw|python|pythonw|cmd|powershell|conhost)\.exe$' -and $_.CommandLine -and $_.CommandLine.Contains($root) -and $_.CommandLine -notmatch 'vision_train|stop_all\.bat' -and $keep -notcontains $_.ProcessId } | Sort-Object { $_.Name -match 'cmd|powershell' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
rem the status window and hidden helpers started by script name only (their command line may not hold the folder)
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(py|python|pythonw|powershell)\.exe$' -and $_.CommandLine -match 'security_vision\.py|robot_collector\.py|knowledge\\serve\.py|face_server|voice_service\.py|opcua_server\.py|pc_agent\.py|lan_presence|mdns\\announce\.py|scripts\\status\.ps1|smartlab-open-browser' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
taskkill /fi "WINDOWTITLE eq Smart Lab - *" /t /f >nul 2>&1
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
