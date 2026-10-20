@echo off
rem Undo install.bat (keeps Python). Right-click -> "Run as administrator".
net session >nul 2>&1
if errorlevel 1 ( echo Run as administrator. & pause & exit /b 1 )
del /q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup\SmartLab_PC_agent.bat" 2>nul
netsh advfirewall firewall delete rule name="Smart Lab ping" >nul 2>&1
echo Agent no longer starts at sign-in; ping rule removed. C:\SmartLab\pc_agent is left for you to delete.
pause
