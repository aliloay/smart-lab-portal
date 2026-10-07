@echo off
rem Smart Lab - security camera service (security_vision.py), port 5100.
rem launch.bat opens this in its own window when camera.env exists; it can
rem also be double-clicked on its own.
setlocal EnableExtensions
cd /d "%~dp0"
title Smart Lab - Security camera
set "VIRTUAL_ENV="
if not exist camera.env (
  echo No camera.env here yet: copy camera.env.example to camera.env and fill it in.
  pause & exit /b 1
)
rem Read the "set NAME=value" lines (Windows will not run a .env file with
rem "call"). Values are taken literally: write the password's URL codes as-is.
for /f "usebackq tokens=1,* delims= " %%a in ("camera.env") do if /i "%%a"=="set" set "%%b"
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
rem The camera forgets its clock when it loses power: set it from this laptop.
%PY% cam_clock.py --set 2>nul | findstr /b "LocalDateTime" || echo Camera clock not set ^(camera unreachable?^)
echo Do NOT click inside this window: Windows pauses the program while text is
echo selected. If the title says "Select", press Esc.
echo.
%PY% security_vision.py --source "%SOURCE%" --lab %LAB% --device %DEVICE% --portal http://127.0.0.1:8000/api
echo.
echo The security camera service has stopped.
