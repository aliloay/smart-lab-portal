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
call camera.env
if not exist models\object_detection_yolox_2022nov.onnx (
  echo Downloading the person detector once ^(36 MB, needs internet^)...
  curl -L -o models\object_detection_yolox_2022nov.onnx https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx
)
set "PY=py"
%PY% -c "import cv2, flask, requests, waitress" >nul 2>&1 || %PY% -m pip install -r requirements.txt
echo Do NOT click inside this window: Windows pauses the program while text is
echo selected. If the title says "Select", press Esc.
echo.
%PY% security_vision.py --source "%SOURCE%" --lab %LAB% --device %DEVICE% --portal http://127.0.0.1:8000/api
echo.
echo The security camera service has stopped.
