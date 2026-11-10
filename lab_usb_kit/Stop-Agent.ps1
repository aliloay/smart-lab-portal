# Smart Lab - stop this account's agent until the next sign-in. Other accounts' agents are not touched.
param([string]$InstallRoot = (Join-Path $env:USERPROFILE 'SmartLab'))
foreach ($pattern in 'agent_boot\.py', 'pc_agent\.py|relay\.py') {     # supervisor first, or it restarts what is being stopped
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match $pattern -and $_.CommandLine -like "*$InstallRoot*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
Remove-Item (Join-Path $env:TEMP 'smartlab_status.txt') -Force -ErrorAction SilentlyContinue
Write-Host 'Stopped.' -ForegroundColor Cyan
