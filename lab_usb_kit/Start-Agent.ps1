# Smart Lab - start this account's agent now (it also starts by itself at sign-in). A second copy leaves at once.
param([string]$InstallRoot = (Join-Path $env:USERPROFILE 'SmartLab'))
$cfgFile = Join-Path $InstallRoot 'smartlab.json'
if (-not (Test-Path $cfgFile)) { Write-Host "Not installed for $env:USERNAME: run Install-CurrentUser.ps1" -ForegroundColor Red; exit 1 }
$boot = Join-Path $InstallRoot 'pc_agent\agent_boot.py'
Start-Process -FilePath (Join-Path $InstallRoot 'python\pythonw.exe') -ArgumentList "-E -s `"$boot`" --config `"$cfgFile`"" -WorkingDirectory $InstallRoot -WindowStyle Hidden
Write-Host 'Started.' -ForegroundColor Green
