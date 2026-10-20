@echo off
rem Smart Lab PC agent - visible window, runs in the signed-in user's session (needed to see the
rem screen and to lock). Install steps and IT requirements: tools\pc_agent\README.md.
setlocal
cd /d "%~dp0"
if not exist agent.env (
  echo agent.env is missing: copy agent.env.example to agent.env and fill it in.
  pause & exit /b 1
)
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("agent.env") do set "%%a=%%b"
if "%DEVICE_KEY%"=="" ( echo DEVICE_KEY is empty in agent.env & pause & exit /b 1 )
title Smart Lab - PC agent %DEVICE_UID%
rem Screen frames need Pillow (pip install pillow) or OpenCV + numpy; everything else needs psutil + requests.
py -3 pc_agent.py --device %DEVICE_UID% --asset %ASSET_TAG% --lab %LAB% --portal %PORTAL%
pause
