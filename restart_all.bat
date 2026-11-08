@echo off
rem Smart Lab - clean restart in one click: stop_all.bat, then launch.bat.
rem Use it when a window is stuck or two copies of a service are running.
cd /d "%~dp0"
call "%~dp0stop_all.bat"
start "" "%~dp0launch.bat"
