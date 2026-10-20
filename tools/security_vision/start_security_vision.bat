@echo off
rem Smart Lab - security camera service (security_vision.py).
rem   start_security_vision.bat               camera 1: camera.env  (port 5100 unless PORT is set)
rem   start_security_vision.bat camera2.env   camera 2: camera2.env (its own DEVICE, LAB, PORT, SOURCE)
rem launch.bat opens one window per camera file that exists; each can also be double-clicked.
rem One process per camera: a camera that fails or disconnects never stops the other one.
setlocal EnableExtensions
cd /d "%~dp0"
set "CAMFILE=%~1"
if "%CAMFILE%"=="" set "CAMFILE=camera.env"
set "VIRTUAL_ENV="
set "PORT="
set "PEER_PORT="
if not exist "%CAMFILE%" (
  echo No %CAMFILE% here yet: copy camera.env.example to %CAMFILE% and fill it in.
  pause & exit /b 1
)
rem Read the "set NAME=value" lines (Windows will not run a .env file with
rem "call"). Values are taken literally: write the password's URL codes as-is.
for /f "usebackq tokens=1,* delims= " %%a in ("%CAMFILE%") do if /i "%%a"=="set" set "%%b"
if "%PORT%"=="" set "PORT=5100"
title Smart Lab - Security camera %DEVICE%
rem Only one service per camera: a second copy cannot take the same port, keeps a
rem second stream open and serves nothing (seen at the lab 2026-10-14).
netstat -ano | findstr /r /c:"127.0.0.1:%PORT% .*LISTENING" >nul
if not errorlevel 1 (
  echo The security camera service for %DEVICE% is already running ^(port %PORT%^).
  echo Close its window "Smart Lab - Security camera %DEVICE%" first, then start this again.
  pause & exit /b 1
)
if not exist models\object_detection_yolox_2022nov.onnx (
  echo Downloading the person detector once ^(36 MB, needs internet^)...
  curl -L -o models\object_detection_yolox_2022nov.onnx https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx
)
if not exist models\person_reid_youtu_2021nov.onnx (
  echo Downloading the person re-identification model once ^(107 MB, optional^)...
  curl -L -o models\person_reid_youtu_2021nov.part https://github.com/opencv/opencv_zoo/raw/main/models/person_reid_youtureid/person_reid_youtu_2021nov.onnx && move /y models\person_reid_youtu_2021nov.part models\person_reid_youtu_2021nov.onnx >nul
)
set "PY=py"
%PY% -c "import cv2, flask, requests, waitress" >nul 2>&1 || %PY% -m pip install -r requirements.txt
rem Detector engines: the graphics card (DirectML build of ONNX Runtime) and
rem OpenVINO for the CPU. The plain "onnxruntime" package hides DirectML, so it
rem is swapped for the DirectML build once. vision.py then picks the fastest.
%PY% -c "import onnxruntime as o,sys; sys.exit(0 if 'DmlExecutionProvider' in o.get_available_providers() else 1)" >nul 2>&1 || (
  echo Setting up the graphics-card detector once...
  %PY% -m pip uninstall -y onnxruntime >nul 2>&1
  %PY% -m pip install onnxruntime-directml
)
%PY% -c "import openvino" >nul 2>&1 || %PY% -m pip install openvino
rem The camera address (with its password) goes through the environment, not the command
rem line, so it does not show in Task Manager / process lists (2026-10-14).
set "SECURITY_CAMERA_SOURCE=%SOURCE%"
rem The camera forgets its clock when it loses power: set it from this laptop.
%PY% cam_clock.py --set 2>nul | findstr /b "LocalDateTime" || echo Camera clock not set ^(camera unreachable?^)
echo Do NOT click inside this window: Windows pauses the program while text is
echo selected. If the title says "Select", press Esc.
echo.
%PY% security_vision.py --lab %LAB% --device %DEVICE% --port %PORT% --portal http://127.0.0.1:8000/api
echo.
echo The security camera service has stopped.
