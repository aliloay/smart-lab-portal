@echo off
rem Smart Lab - live monitor (the wall screen) in its own full-screen window.
rem
rem Run launch.bat first (the portal must be up). Then double-click this, or
rem pin it: right-click > Show more options > Send to > Desktop (shortcut),
rem then right-click the shortcut > Pin to taskbar.
rem
rem It opens http://localhost/monitor as an app window (no tabs, no address
rem bar) in full screen. F11 leaves full screen; Alt+F4 closes it. Sign in
rem with a staff or administrator account when it opens; it stays signed in
rem while the window is open (a sign-in lasts 8 hours).
setlocal
set "URL=http://localhost/monitor"
if not "%~1"=="" set "URL=%~1"

reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>&1 && goto chrome
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>&1 && goto chrome
start "" msedge --new-window --app="%URL%" --start-fullscreen
exit /b

:chrome
start "" chrome --new-window --app="%URL%" --start-fullscreen
