@echo off
rem Smart Lab - face recognition server (face_server.py).
rem Runs from this folder, so it uses the dataset\, lbph_model.yml and
rem labels.txt next to it. launch.bat opens this in its own window; it can
rem also be double-clicked on its own.
setlocal EnableExtensions
cd /d "%~dp0"
title Smart Lab - Face server
rem Never pick up the portal's virtualenv from the calling window: it has
rem no Flask and no OpenCV contrib (cv2.face).
set "VIRTUAL_ENV="

set "FACEPY="
if exist ".venv\Scripts\python.exe" set "FACEPY=.venv\Scripts\python.exe"
if not defined FACEPY py -c "import cv2, flask; cv2.face" >nul 2>&1 && set "FACEPY=py"
if not defined FACEPY python -c "import cv2, flask; cv2.face" >nul 2>&1 && set "FACEPY=python"
if defined FACEPY goto deps

echo No Python with Flask and OpenCV contrib found - setting one up in
echo firmware\face_server\.venv (once, a few minutes).
py -3 -m venv .venv || python -m venv .venv || goto no_python
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto no_python
set "FACEPY=.venv\Scripts\python.exe"

:deps
rem waitress keeps the camera's connection open between frames (much faster
rem than Flask's built-in server). Added later, so install it if missing.
"%FACEPY%" -c "import waitress" >nul 2>&1 || "%FACEPY%" -m pip install waitress

:run
rem Without this rule Windows Firewall silently drops the camera's frames
rem (the camera then logs "HTTP -1 cannot connect").
netsh advfirewall firewall show rule name="Smart Lab face server" >nul 2>&1
if errorlevel 1 (
  echo ************************************************************
  echo  The camera cannot reach this server yet: Windows Firewall
  echo  has no rule for it. Double-click allow_firewall.bat once
  echo  ^(it asks for administrator rights^), then restart this.
  echo ************************************************************
  echo.
)
echo Do NOT click inside this window: Windows pauses the program while text
echo is selected, and the camera then times out. If the title says "Select",
echo press Esc.
echo.
if not exist dataset\ echo Note: no dataset\ folder here yet - enrol faces first (docs\DOOR_SYSTEM.md).
"%FACEPY%" face_server.py
echo.
echo The face server has stopped.
exit /b

:no_python
echo Could not prepare Python for the face server.
echo Install Python 3 from python.org, then run this again.
pause
