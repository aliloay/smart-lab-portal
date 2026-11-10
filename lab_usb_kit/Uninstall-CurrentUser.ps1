# Smart Lab - remove the agent for THIS Windows account: stops it, removes its HKCU Run entry, its key and its files.
# The portal card and its history stay. Other accounts on this PC are not touched.
param([string]$InstallRoot = (Join-Path $env:USERPROFILE 'SmartLab'), [string]$RunName = 'SmartLab', [switch]$NoPause)
foreach ($pattern in 'agent_boot\.py', 'pc_agent\.py|relay\.py') {
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match $pattern -and $_.CommandLine -like "*$InstallRoot*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 1
Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name $RunName -ErrorAction SilentlyContinue
Remove-Item (Join-Path $env:TEMP 'smartlab_status.txt') -Force -ErrorAction SilentlyContinue
if (Test-Path $InstallRoot) {
    foreach ($item in 'python', 'pc_agent', 'relay', 'device.key', 'enroll.key', 'smartlab.json', 'MANIFEST.json') {      # only the kit's own contents
        Remove-Item (Join-Path $InstallRoot $item) -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (-not (Get-ChildItem $InstallRoot -Force -ErrorAction SilentlyContinue)) { Remove-Item $InstallRoot -Force -ErrorAction SilentlyContinue }
    if (Test-Path (Join-Path $InstallRoot 'pc_agent')) { Write-Host "Could not remove everything in $InstallRoot (a file is in use)." -ForegroundColor Yellow }
}
Write-Host "Smart Lab agent removed for $env:USERNAME." -ForegroundColor Cyan
if ($PSScriptRoot -and -not $NoPause) { [void](Read-Host 'Press Enter to close') }
