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
for /f "usebackq delims=" %%i in (`"%FACEPY%" -c "import sys; print(sys.executable)"`) do set "PYEXE=%%i"
if not defined PYEXE (
  echo Could not locate the Python program.
  pause & exit /b 1
)

echo Allowing incoming connections for:
echo   %PYEXE%
netsh advfirewall firewall delete rule name="Smart Lab face server" >nul 2>&1
netsh advfirewall firewall add rule name="Smart Lab face server" dir=in action=allow program="%PYEXE%" enable=yes profile=any
rem Ports too (portal on 80, API on 8000, face server on 5000), for any profile.
netsh advfirewall firewall delete rule name="Smart Lab ports" >nul 2>&1
netsh advfirewall firewall add rule name="Smart Lab ports" dir=in action=allow protocol=TCP localport=80,5000,8000 enable=yes profile=any
echo.
echo Done. This does not need to be run again.
pause
