@echo off
rem Smart Lab - local AI helper, started by launch.bat when Ollama is installed.
rem Waits for Ollama, then downloads the two AI models only if they are
rem missing (first run, about 3 GB). Afterwards it finds them and exits.
setlocal EnableExtensions
title Smart Lab - AI models
set "OLLAMA_EXE=ollama"
where ollama >nul 2>&1 || set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"

rem Model names: the same defaults as docker-compose.yml, or .env if set there.
set "M1=qwen2.5:3b"
set "M2=qwen2.5:1.5b"
if exist "%~dp0..\.env" (
  for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0..\.env") do (
    if /i "%%a"=="OLLAMA_MODEL" if not "%%b"=="" set "M1=%%b"
    if /i "%%a"=="OLLAMA_STUDENT_MODEL" if not "%%b"=="" set "M2=%%b"
  )
)

rem Ollama may take a few seconds to come up after launch.bat starts it.
set /a tries=0
:wait
"%OLLAMA_EXE%" list >nul 2>&1 && goto ready
set /a tries+=1
if %tries% geq 20 (
  echo Ollama did not start. Open the Ollama app from the Start menu.
  timeout /t 15 >nul
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait
:ready

for %%m in ("%M1%" "%M2%") do (
  "%OLLAMA_EXE%" list | findstr /b /c:"%%~m " >nul || (
    echo Downloading AI model %%~m - first time only, please wait...
    "%OLLAMA_EXE%" pull %%~m
  )
)
exit /b 0
