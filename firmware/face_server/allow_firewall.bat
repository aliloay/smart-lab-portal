@echo off
rem Smart Lab - let the camera reach the face server through Windows Firewall.
rem
rem Run ONCE (double-click; it asks for administrator rights). The rule is
rem permanent: it survives restarts and applies whether Windows calls the
rem Wi-Fi Private or Public. Run it again only if Python is reinstalled or
rem moved, because the rule is tied to the Python program the face server
rem uses (a port-only rule was ignored on this laptop; a program rule works).
setlocal EnableExtensions
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  echo Asking for administrator rights...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

rem The same Python choice as start_face_server.bat.
set "VIRTUAL_ENV="
set "FACEPY="
if exist ".venv\Scripts\python.exe" set "FACEPY=.venv\Scripts\python.exe"
if not defined FACEPY py -c "import cv2, flask; cv2.face" >nul 2>&1 && set "FACEPY=py"
if not defined FACEPY python -c "import cv2, flask; cv2.face" >nul 2>&1 && set "FACEPY=python"
if not defined FACEPY (
  echo No Python with the face server's packages found. Run start_face_server.bat
  echo once first, then run this again.
  pause & exit /b 1
)

set "PYEXE="
rem 2026-11-03: no quotes around %FACEPY% here - "py" -c "..." inside for /f was mangled by cmd ('py" -c "import'
rem is not recognized) and the script stopped before any rule was written. FACEPY never contains spaces.
for /f "usebackq delims=" %%i in (`%FACEPY% -c "import sys; print(sys.executable)"`) do set "PYEXE=%%i"
if not defined PYEXE (
  echo Could not locate the Python program.
  pause & exit /b 1
)

rem 2026-11-03 lab (Gemini ACT-04 reviewed): GIU PCs never reach this laptop directly - the engineer PC's relay
rem connects from its Smart Lab cable address (192.168.1.104), so the GIU subnets (10.30.x, 10.40.x) are NOT opened
rem here: least privilege = the Smart Lab LAN only.
set "LABNETS=192.168.1.0/24"
echo Allowing incoming connections (from %LABNETS% only) for:
echo   %PYEXE%
rem the old catch-all rule "Smart Lab" (any address) is replaced too
netsh advfirewall firewall delete rule name="Smart Lab" >nul 2>&1
netsh advfirewall firewall delete rule name="Smart Lab face server" >nul 2>&1
netsh advfirewall firewall add rule name="Smart Lab face server" dir=in action=allow program="%PYEXE%" enable=yes profile=any remoteip=%LABNETS%
rem Ports too (portal on 80, API on 8000, face server on 5000, security camera
rem service on 5100), for any profile but ONLY from the Smart Lab LAN and the GIU lab LAN:
rem a phone hotspot / cafe Wi-Fi peer cannot reach them (Gemini audit 2026-11-03).
netsh advfirewall firewall delete rule name="Smart Lab ports" >nul 2>&1
netsh advfirewall firewall add rule name="Smart Lab ports" dir=in action=allow protocol=TCP localport=80,443,5000,5100,8000,8080,8443 enable=yes profile=any remoteip=%LABNETS%
echo.
echo Done. This does not need to be run again.
pause
