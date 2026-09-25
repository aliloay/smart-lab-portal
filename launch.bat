@echo off
rem Smart Lab Portal - one-click launcher.
rem It only runs "docker compose up --build"; docker-compose.yml is the single
rem definition of the system. Close this window or press Ctrl+C to stop.
setlocal
cd /d "%~dp0"
title Smart Lab Portal

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker was not found. Install Docker Desktop, then run this again.
  pause & exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is not running. Start it, wait until it says
  echo "Engine running", then run this again.
  pause & exit /b 1
)

rem The address phones and the ESP32 boards must use: the adapter with a
rem default gateway (Wi-Fi or hotspot), not VMware/WSL virtual adapters.
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1).IPv4Address.IPAddress"`) do set LANIP=%%i

echo.
echo  Smart Lab Portal is starting (the first build takes a few minutes).
echo.
echo    On this laptop : http://localhost
if defined LANIP (
  echo    Phones, same Wi-Fi : http://%LANIP%
  echo    ESP32 BACKEND_IP   : %LANIP%   ^(API on port 8000^)
) else (
  echo    No network with a gateway found - connect to the Wi-Fi or hotspot.
)
echo.

docker compose up --build
pause
