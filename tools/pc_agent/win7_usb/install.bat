@echo off
rem Smart Lab PC agent - OFFLINE install for Windows 7 SP1 (no internet needed). One time per PC.
rem Right-click -> "Run as administrator". Everything comes from this folder (USB stick).
title Smart Lab - install PC agent (Windows 7)
net session >nul 2>&1
if errorlevel 1 ( echo Right-click install.bat and choose "Run as administrator". & pause & exit /b 1 )
cd /d "%~dp0"
set ARCH=win32
set PYEXE=python\python-3.8.10.exe
set UCRT=ucrt\Windows6.1-KB2999226-x86.msu
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" goto x64
if /i "%PROCESSOR_ARCHITEW6432%"=="AMD64" goto x64
goto arch_done
:x64
set ARCH=amd64
set PYEXE=python\python-3.8.10-amd64.exe
set UCRT=ucrt\Windows6.1-KB2999226-x64.msu
:arch_done
echo Windows: %ARCH%
echo.
echo [1/6] C runtime update KB2999226 (Python 3.8 needs it)
if exist "%windir%\System32\ucrtbase.dll" ( echo       already present ) else ( wusa "%~dp0%UCRT%" /quiet /norestart & echo       installed )
echo [2/6] Python 3.8.10 (the last Python for Windows 7)
"%windir%\py.exe" -3.8 --version >nul 2>&1
if errorlevel 1 (
  "%PYEXE%" /quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1 InstallLauncherAllUsers=1 Include_test=0 Include_doc=0
  if errorlevel 1 ( echo Python install FAILED. If it says api-ms-win-crt is missing: restart Windows, run install.bat again. & pause & exit /b 1 )
) else ( echo       already installed )
echo [3/6] libraries: psutil, requests, pillow (from this folder)
"%windir%\py.exe" -3.8 -m pip install --no-index --find-links "%~dp0wheels\%ARCH%" psutil requests pillow
if errorlevel 1 ( echo Library install FAILED. & pause & exit /b 1 )
echo [4/6] agent files -^> C:\SmartLab\pc_agent
xcopy /y /i /q agent\* "C:\SmartLab\pc_agent\" >nul
echo [5/6] allow ping from the lab laptop (fast on/off in the portal)
netsh advfirewall firewall delete rule name="Smart Lab ping" >nul 2>&1
netsh advfirewall firewall add rule name="Smart Lab ping" dir=in action=allow protocol=icmpv4:8,any >nul
echo [6/6] run the agent INVISIBLY: scheduled task at every sign-in + re-check every minute
rem (older installs used a visible window from the Startup folder - removed)
del /q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup\SmartLab_PC_agent.bat" 2>nul
taskkill /f /fi "WINDOWTITLE eq Smart Lab - PC agent*" >nul 2>&1
schtasks /create /tn "Smart Lab PC agent" /xml "C:\SmartLab\pc_agent\SmartLab_PC_agent_task.xml" /f
if errorlevel 1 ( echo Scheduled task FAILED. & pause & exit /b 1 )
schtasks /run /tn "Smart Lab PC agent" >nul
echo.
echo Done. The agent now runs without a window. It is back within a minute if it is stopped,
echo and starts by itself at every sign-in. Log: C:\SmartLab\pc_agent\agent.log
pause
