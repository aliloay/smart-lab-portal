@echo off
rem Smart Lab - one-click launcher. It:
rem   1. starts Docker Desktop if it is not running yet
rem   2. opens the face server (firmware\face_server) in its own window
rem   3. starts the free local AI (Ollama) if it is installed, and downloads
rem      its two models the first time
rem   4. builds (when it can) and runs "docker compose up": portal, API and database
rem      (docker-compose.yml is the single definition of the system), plus
rem      n8n when automation is configured in .env (AUTOMATION_WEBHOOK_BASE)
rem   5. opens the portal in the browser as soon as it answers
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

rem ---- Security camera (optional): only once tools\security_vision\camera.env
rem exists, so a webcam is never switched on by surprise ----------------------
set "SEC_STARTED="
set "SEC_STATE=off - see tools\security_vision\README.md"
if exist "%~dp0tools\security_vision\camera.env" (
  set "SEC_STATE=on (port 5100)"
  netstat -ano | findstr /r /c:":5100 .*LISTENING" >nul
  if errorlevel 1 (
    start "Smart Lab - Security camera" cmd /k call "%~dp0tools\security_vision\start_security_vision.bat"
    set "SEC_STARTED=1"
  )
)

rem ---- Security camera 2 (optional): its own window and process once
rem tools\security_vision\camera2.env exists (the start script refuses a second copy) ----
if exist "%~dp0tools\security_vision\camera2.env" (
  tasklist /v /fi "WINDOWTITLE eq Smart Lab - Security camera SECCAM_LAB02*" | findstr /i "SECCAM_LAB02" >nul || (
    start "Smart Lab - Security camera 2" cmd /k call "%~dp0tools\security_vision\start_security_vision.bat" camera2.env
  )
)

rem ---- UR5e monitor (optional, read-only): once tools\robot_monitor\robot.env
rem has the robot's IP. It retries by itself, so the robot shows ONLINE as soon
rem as it is on the lab LAN. ---------------------------------------------------
if exist "%~dp0tools\robot_monitor\robot.env" (
  findstr /r /c:"^UR5E_IP=..*" "%~dp0tools\robot_monitor\robot.env" >nul && (
    tasklist /v /fi "WINDOWTITLE eq Smart Lab - UR5e monitor*" | findstr /i "UR5e" >nul || (
      start "Smart Lab - UR5e monitor" cmd /k call "%~dp0tools\robot_monitor\start_ur5e_monitor.bat"
    )
  )
)

rem ---- FANUC monitor (optional, read-only): once robot.env has FANUC_IP ----------
if exist "%~dp0tools\robot_monitor\robot.env" (
  findstr /r /c:"^FANUC_IP=..*" "%~dp0tools\robot_monitor\robot.env" >nul && (
    tasklist /v /fi "WINDOWTITLE eq Smart Lab - FANUC monitor*" | findstr /i "FANUC" >nul || (
      start "Smart Lab - FANUC monitor" cmd /k call "%~dp0tools\robot_monitor\start_fanuc_monitor.bat"
    )
  )
)

rem ---- Local AI (Ollama) is optional: used when installed ---------------------
rem Ollama normally starts with Windows (tray icon). If it is not running,
rem start it; the helper then fetches missing models in a minimized window.
set "OLLAMA_EXE="
where ollama >nul 2>&1 && set "OLLAMA_EXE=ollama"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
set "AI_STATE=off - install Ollama from ollama.com for the free AI chat"
if not defined OLLAMA_EXE goto ai_done
set "AI_STATE=Ollama (free, on this laptop)"
netstat -ano | findstr /r /c:":11434 .*LISTENING" >nul && goto ai_models
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
  start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
) else (
  start "Smart Lab - Ollama" /min "%OLLAMA_EXE%" serve
)
:ai_models
start "Smart Lab - AI models" /min cmd /c call "%~dp0scripts\ollama_models.bat"
:ai_done

rem ---- Project knowledge (admins/staff in the portal, and the n8n knowledge jobs):
rem local service on 127.0.0.1:5199 only - not reachable from the lab network.
rem Starts once tools\knowledge\config.json exists (it holds the private paths and key).
if exist "%~dp0tools\knowledge\config.json" (
  tasklist /v /fi "WINDOWTITLE eq Smart Lab - Knowledge*" | findstr /i "Knowledge" >nul || (
    start "Smart Lab - Knowledge" /min cmd /k py "%~dp0tools\knowledge\serve.py"
  )
)

rem ---- The friendly name https://smartlab.local for every device on the Smart_Lab network (mDNS).
tasklist /v /fi "WINDOWTITLE eq Smart Lab - Name*" | findstr /i "Name" >nul || (
  start "Smart Lab - Name smartlab.local" /min cmd /k py "%~dp0tools\mdns\announce.py"
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
  echo    Tablet             : http://192.168.1.151
  if not "%LANIP%"=="192.168.1.200" (
    echo.
    echo    WARNING: this laptop is %LANIP%, but the ESP32 boards expect 192.168.1.200.
    echo             Settings ^> Wi-Fi ^> IP assignment ^> Manual: 192.168.1.200, gateway 192.168.1.1
  )
) else (
  echo    No network with a gateway found - connect to the Wi-Fi or hotspot.
)
echo.
if defined PROFILE (
  echo    n8n automation     : http://localhost:5678   ^(this laptop only^)
) else (
  echo    n8n automation     : off - see docs\AUTOMATION.md to enable it
)
echo    AI chat            : %AI_STATE%
echo    Security camera    : %SEC_STATE%
echo.
echo  Stop everything: Ctrl+C here.
echo.

rem Open the browser once the portal answers; this window keeps the logs.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "$null = 'smartlab-open-browser'; for ($i = 0; $i -lt 150; $i++) { try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost/api/health).StatusCode -eq 200) { Start-Process 'http://localhost'; break } } catch {} ; Start-Sleep 2 }" >nul 2>&1

rem Build first, separately. A build needs the internet (Docker checks the base
rem images online), and the Smart_Lab router has none. Offline, skip it and
rem start the last version that was built - the lab must run offline.
powershell -NoProfile -Command "try { $null = [Net.Dns]::GetHostEntry('registry-1.docker.io'); exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
  echo  No internet - starting the last built version ^(no rebuild^).
  echo  Code changes since that build need one launch with internet.
  echo.
  goto start_portal
)
docker compose %PROFILE% build
if errorlevel 1 (
  echo.
  echo  Could not rebuild - starting the last built version.
  echo.
)
:start_portal
docker compose %PROFILE% up --no-build

rem ---- Stopped: close the face server we opened -----------------------------
if defined FACE_STARTED taskkill /fi "WINDOWTITLE eq Smart Lab - Face server*" /t /f >nul 2>&1
if defined SEC_STARTED taskkill /fi "WINDOWTITLE eq Smart Lab - Security camera*" /t /f >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like ('*smartlab-open' + '-browser*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
echo.
echo Smart Lab stopped. Your data is kept for next time.
pause
