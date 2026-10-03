@echo off
rem Name-lock test on THIS laptop's webcam: no portal, no lab camera needed.
rem Two people: click "X enters" on the page, X walks into view alone and
rem stands clear for 2 s; then the next person; then cross and bump.
setlocal EnableExtensions
cd /d "%~dp0"
title Smart Lab - Name lock demo (webcam)
set "PY=py"
%PY% -c "import cv2, flask, requests, waitress" >nul 2>&1 || %PY% -m pip install -r requirements.txt
if not exist models\object_detection_yolox_2022nov.onnx (
  curl -L -o models\object_detection_yolox_2022nov.onnx https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx
)
if not exist models\person_reid_youtu_2021nov.onnx (
  curl -L -o models\person_reid_youtu_2021nov.part https://github.com/opencv/opencv_zoo/raw/main/models/person_reid_youtureid/person_reid_youtu_2021nov.onnx && move /y models\person_reid_youtu_2021nov.part models\person_reid_youtu_2021nov.onnx >nul
)
set "NAMES=USER1=Ali,USER2=Friend"
if not "%~1"=="" set "NAMES=%~1"
start "" http://127.0.0.1:5101/demo
%PY% security_vision.py --source 0 --demo "%NAMES%" --port 5101
pause
