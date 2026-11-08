@echo off
rem Smart Lab - lab PCs on the LAN (on / off by MAC, nothing installed on the PCs). README: tools\lan_presence\README.md
title Smart Lab - LAN presence
cd /d "%~dp0"
py -3.12 lan_presence.py
pause
