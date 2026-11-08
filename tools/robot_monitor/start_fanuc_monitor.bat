@echo off
rem Smart Lab - FANUC ER-4iA (R-30iB Mate Plus) live twin, READ-ONLY: HTTP GET of the controller's
rem current-position page only (/MD/CURPOS.DG). Nothing is ever sent that can move the robot.
rem The page format was confirmed on the lab's controller (fanuc_probe.py, 2026-10-14).
rem Put the controller's IP in robot.env as FANUC_IP=... (pendant: MENU > SETUP > Host Comm > TCP/IP).
setlocal
cd /d "%~dp0"
title Smart Lab - FANUC monitor (read-only)
if not exist robot.env ( echo robot.env missing - add FANUC_IP=... & pause & exit /b 1 )
for /f "usebackq tokens=1,* delims==" %%a in ("robot.env") do set "%%a=%%b"
if "%FANUC_IP%"=="" ( echo FANUC_IP is empty in robot.env & pause & exit /b 1 )
if "%DEVICE_API_KEY%"=="" for /f "usebackq tokens=1,* delims==" %%a in ("..\..\.env") do if /i "%%a"=="DEVICE_API_KEY" set "DEVICE_API_KEY=%%b"
py -3.12 robot_collector.py --source fanuc --robot %FANUC_IP% --device FANUC_01 --model FANUC --name "FANUC ER-4iA"
echo The FANUC monitor stopped.
pause
