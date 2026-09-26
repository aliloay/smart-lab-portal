@echo off
rem Smart Lab - one-click launcher. It:
rem   1. starts Docker Desktop if it is not running yet
rem   2. opens the face server (firmware\face_server) in its own window
rem   3. runs "docker compose up --build" here: portal, API and database
rem      (docker-compose.yml is the single definition of the system), plus
rem      n8n when automation is configured in .env (AUTOMATION_WEBHOOK_BASE)
rem   4. opens the portal in the browser as soon as it answers
rem Ctrl+C in this window stops the portal and closes the face server.
setlocal EnableExtensions
cd /d "%~dp0"
title Smart Lab - Portal

rem ---- Docker ----------------------------------------------------------------
where docker >nul 2>&1
if errorlevel 1 (
  echo Docker was not found. Install Docker Desktop, then run this again.
  pause & exit /b 1
)
docker info >nul 2>&1 && goto docker_ready
echo Starting Docker Desktop...
set "DD=%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe"
if not exist "%DD%" set "DD=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if exist "%DD%" start "" "%DD%"
set /a tries=0
:wait_docker
timeout /t 3 /nobreak >nul
docker info >nul 2>&1 && goto docker_ready
set /a tries+=1
if %tries% lss 60 goto wait_docker
echo Docker Desktop did not start within 3 minutes. Open it, wait until it
echo says "Engine running", then run this again.
pause & exit /b 1
:docker_ready

rem ---- Face server (own window, own lifecycle) --------------------------------
set "FACE_STARTED="
netstat -ano | findstr /r /c:":5000 .*LISTENING" >nul
if not errorlevel 1 (
  echo Face server already running on port 5000 - leaving it as it is.
) else (
  start "Smart Lab - Face server" cmd /k call "%~dp0firmware\face_server\start_face_server.bat"
  set "FACE_STARTED=1"
)

rem ---- Automation (n8n) is optional: on only when .env configures it ----------
set "PROFILE="
if exist ".env" findstr /r /c:"^AUTOMATION_WEBHOOK_BASE=..*" ".env" >nul && set "PROFILE=--profile automation"

rem ---- Addresses ----------------------------------------------------------------
rem The address phones and the ESP32 boards must use: the adapter with a
rem default gateway (Wi-Fi or hotspot), not VMware/WSL virtual adapters.
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1).IPv4Address.IPAddress"`) do set LANIP=%%i

echo.
echo  Smart Lab is starting (the first build takes a few minutes).
echo.
echo    On this laptop     : http://localhost   (opens by itself when ready)
if defined LANIP (
  echo    Phones, same Wi-Fi : http://%LANIP%
  echo    ESP32 master       : BACKEND_IP = %LANIP%   ^(API on port 8000^)
  echo    ESP32-CAM          : SERVER_IP  = %LANIP%   ^(face server, port 5000^)
) else (
  echo    No network with a gateway found - connect to the Wi-Fi or hotspot.
)
echo.
if defined PROFILE (
  echo    n8n automation     : http://localhost:5678   ^(this laptop only^)
) else (
  echo    n8n automation     : off - see docs\AUTOMATION.md to enable it
)
echo.
echo  Stop everything: Ctrl+C here.
echo.

rem Open the browser once the portal answers; this window keeps the logs.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "$null = 'smartlab-open-browser'; for ($i = 0; $i -lt 150; $i++) { try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost/api/health).StatusCode -eq 200) { Start-Process 'http://localhost'; break } } catch {} ; Start-Sleep 2 }" >nul 2>&1

docker compose %PROFILE% up --build

rem ---- Stopped: close the face server we opened -----------------------------
if defined FACE_STARTED taskkill /fi "WINDOWTITLE eq Smart Lab - Face server*" /t /f >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like ('*smartlab-open' + '-browser*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
echo.
echo Smart Lab stopped. Your data is kept for next time.
pause
