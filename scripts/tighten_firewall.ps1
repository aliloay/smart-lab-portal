# Smart Lab laptop: close the old "from anywhere" firewall rules (Gemini + Claude audits, 2026-11-04).
# Right-click -> Run with PowerShell; it asks for administrator rights once. -DryRun only shows what it would do.
#
# Found: "SmartLab API 8000", "SmartLab Flask 5000" and Windows' own "Python" rules allow ANY address, and Docker Desktop's
# rule lets any address reach every published port. On a phone hotspot or a university network, anyone could reach the portal.
# After this: only the Smart Lab network (192.168.1.0/24), through the rules allow_firewall.bat already made.
# Undo: netsh advfirewall import "<the backup file it names>"  (run as administrator).
param([switch]$DryRun)
$elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $DryRun -and -not $elevated) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    return
}
$lab = '192.168.1.0/24'
function Finish { if ($PSCommandPath -and -not $DryRun) { [void](Read-Host 'Press Enter to close') } }
function Show($r) { $a = $r | Get-NetFirewallAddressFilter; $p = $r | Get-NetFirewallPortFilter; "  {0,-28} remote={1,-28} ports={2}" -f $r.DisplayName, ($a.RemoteAddress -join ','), ($p.LocalPort -join ',') }
$inbound = @(Get-NetFirewallRule -Direction Inbound -Enabled True -Action Allow)

# The replacement must be in place first, or the portal would go dark on the lab network.
$scoped = $inbound | Where-Object { $_.DisplayName -eq 'Smart Lab ports' }
if (-not $scoped -or (($scoped | Get-NetFirewallAddressFilter).RemoteAddress -notmatch '^192\.168\.1\.')) {
    Write-Host 'The rule "Smart Lab ports" (192.168.1.0/24 only) is missing: run firmware\face_server\allow_firewall.bat as administrator first. Nothing changed.' -ForegroundColor Red
    Finish; return
}
$remove = @($inbound | Where-Object { $_.DisplayName -in 'SmartLab API 8000', 'SmartLab Flask 5000' })
$narrow = @($inbound | Where-Object { $_.DisplayName -in 'Python', 'Docker Desktop Backend' -and (($_ | Get-NetFirewallAddressFilter).RemoteAddress -contains 'Any') })
Write-Host 'Remove:' -ForegroundColor Cyan; $remove | ForEach-Object { Show $_ }
Write-Host "Narrow to $lab :" -ForegroundColor Cyan; $narrow | ForEach-Object { Show $_ }
if ($DryRun) { Write-Host 'Dry run: nothing changed.' -ForegroundColor Yellow; return }
$backup = Join-Path (Split-Path $PSCommandPath -Parent) ("..\backups\firewall_{0}.wfw" -f (Get-Date -Format 'yyyyMMdd_HHmm'))
& netsh advfirewall export "$backup" | Out-Null
Write-Host "Backup of all rules: $backup"
$remove | Remove-NetFirewallRule
$narrow | Set-NetFirewallRule -RemoteAddress $lab
Write-Host 'After:' -ForegroundColor Cyan
Get-NetFirewallRule -Direction Inbound -Enabled True -Action Allow | Where-Object { $_.DisplayName -match 'smart|python|docker' } | ForEach-Object { Show $_ }
Write-Host 'Done. Test: https://192.168.1.200 from a lab PC or a phone on Smart_Lab must still open.' -ForegroundColor Green
Finish