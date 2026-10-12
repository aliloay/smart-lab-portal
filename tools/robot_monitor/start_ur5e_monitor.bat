@echo off
rem Smart Lab - UR5e live twin, READ-ONLY (RTDE receive interface only:
rem joint angles, speeds, tool pose; nothing is ever sent to the robot).
rem Keeps retrying every 3 s, so the UR5e appears ONLINE in the portal by
rem itself as soon as the robot is on the lab LAN - leave this window open.
rem
rem The robot's OWN address goes in robot.env (UR5E_IP=...). Find it on the
rem teach pendant: Settings -> System -> Network. 192.168.1.101 shown on the
rem External Control screen is the ROS laptop, NOT the robot.
setlocal
cd /d "%~dp0"
title Smart Lab - UR5e monitor (read-only)
if not exist robot.env (
  echo UR5E_IP=> robot.env
  echo Put the robot's IP after UR5E_IP= in tools\robot_monitor\robot.env, then start this again.
  pause & exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%a in ("robot.env") do set "%%a=%%b"
if "%UR5E_IP%"=="" ( echo UR5E_IP is empty in robot.env & pause & exit /b 1 )
if "%DEVICE_API_KEY%"=="" for /f "usebackq tokens=1,* delims==" %%a in ("..\..\.env") do if /i "%%a"=="DEVICE_API_KEY" set "DEVICE_API_KEY=%%b"
py -3.12 robot_collector.py --source ur --robot %UR5E_IP% --device UR5E_01 --model UR5e --name "UR5e" --hz 50
echo The UR5e monitor stopped.
pause
