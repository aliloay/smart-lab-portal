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
if defined FACEPY goto run

echo No Python with Flask and OpenCV contrib found - setting one up in
echo firmware\face_server\.venv (once, a few minutes).
py -3 -m venv .venv || python -m venv .venv || goto no_python
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto no_python
set "FACEPY=.venv\Scripts\python.exe"

:run
if not exist dataset\ echo Note: no dataset\ folder here yet - enrol faces first (docs\DOOR_SYSTEM.md).
"%FACEPY%" face_server.py
echo.
echo The face server has stopped.
exit /b

:no_python
echo Could not prepare Python for the face server.
echo Install Python 3 from python.org, then run this again.
pause
