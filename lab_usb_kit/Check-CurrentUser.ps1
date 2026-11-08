# Smart Lab - health check for this Windows account. Only reads, changes nothing, never prints a key.
# -Full also checks every kit file on the stick against MANIFEST.json.
param([switch]$Full, [string]$InstallRoot = (Join-Path $env:USERPROFILE 'SmartLab'), [string]$RunName = 'SmartLab', [switch]$NoPause)
function Finish { if ($PSScriptRoot -and -not $NoPause) { [void](Read-Host 'Press Enter to close') } }
function Line($ok, $text) {
    if ($ok -eq $true) { Write-Host "OK    $text" -ForegroundColor Green }
    elseif ($ok -eq $false) { Write-Host "FAIL  $text" -ForegroundColor Red; $script:failed++ }
    else { Write-Host "NOTE  $text" -ForegroundColor Yellow }
}
$failed = 0
$src = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
if ($Full -and (Test-Path (Join-Path $src 'MANIFEST.json'))) {
    $m = Get-Content -Raw (Join-Path $src 'MANIFEST.json') | ConvertFrom-Json
    $bad = @($m.files.PSObject.Properties | Where-Object {
        $f = Join-Path $src $_.Name; -not (Test-Path $f) -or (Get-FileHash $f -Algorithm SHA256).Hash.ToLower() -ne $_.Value })
    Line ($bad.Count -eq 0) "kit: $(@($m.files.PSObject.Properties).Count) files checked, $($bad.Count) wrong"
}
$cfgFile = Join-Path $InstallRoot 'smartlab.json'
if (-not (Test-Path $cfgFile)) { Line $false "not installed for $env:USERNAME: run Install-CurrentUser.ps1"; Finish; exit 1 }
$cfg = Get-Content -Raw $cfgFile | ConvertFrom-Json
Write-Host "Smart Lab on $env:COMPUTERNAME, account $env:USERNAME: $($cfg.device), in $InstallRoot" -ForegroundColor Cyan
Line (Test-Path (Join-Path $InstallRoot 'python\pythonw.exe')) 'Python runtime present'
$procs = Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like "*$InstallRoot*" }
Line ([bool]($procs | Where-Object { $_.CommandLine -match 'agent_boot\.py' })) 'supervisor running'
$agents = @($procs | Where-Object { $_.CommandLine -match 'pc_agent\.py' })
if ($agents.Count -eq 1) { Line $true 'agent running (1 copy)' }
elseif ($agents.Count -eq 0 -and (Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'pc_agent\.py' })) { Line $null "another account's agent serves this PC; this one takes over when it signs out" }
else { Line $false "agent running ($($agents.Count) copies)" }
if ($cfg.relay_args) {
    $relays = @($procs | Where-Object { $_.CommandLine -match 'relay\.py' })
    Line ($relays.Count -eq 1) "relay running ($($relays.Count) copy)"
}
$run = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name $RunName -ErrorAction SilentlyContinue
Line ([bool]$run) "starts at sign-in of $env:USERNAME"
Line $null 'other Windows accounts are not checked here; each must run this under its own login'

$keyFile = Join-Path $InstallRoot 'device.key'
if (Test-Path $keyFile) {
    $raw = (Get-Content -Raw $keyFile).Trim()
    if ($raw.StartsWith('DPAPI1:')) {
        try {
            Add-Type -AssemblyName System.Security
            $k = [Text.Encoding]::UTF8.GetString([Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($raw.Substring(7)), $null, [Security.Cryptography.DataProtectionScope]::CurrentUser))
            Line $true 'key is protected with DPAPI for this account'
            try {
                $r = Invoke-WebRequest -UseBasicParsing "$($cfg.portal)/equipment/pc/poll?device_uid=$($cfg.device)" -Headers @{ 'X-Device-Key' = $k } -TimeoutSec 6
                Line ($r.StatusCode -eq 200) "portal accepts this account's key ($($cfg.portal))"
            } catch {
                $code = $_.Exception.Response.StatusCode.value__
                if ($code -in 401, 403) { Line $false "portal REFUSES this key (HTTP $code): run Install-CurrentUser.ps1 again" }
                else { Line $null "portal not reachable now at $($cfg.portal): the agent keeps trying" }
            }
            $k = $null
        } catch { Line $false 'this account cannot read the key file: run Install-CurrentUser.ps1 again' }
    } else { Line $null 'key is still in plain text; the agent protects it the next time it starts' }
} elseif (Test-Path (Join-Path $InstallRoot 'enroll.key')) { Line $null 'not registered yet: waiting for the portal' }
else { Line $false 'no key and no enrollment code: run Install-CurrentUser.ps1 again' }
foreach ($log in 'smartlab_boot.log', 'smartlab_agent.log', 'smartlab_relay.log') {
    $p = Join-Path $env:TEMP $log
    if (Test-Path $p) { Write-Host "--- last lines of $log" -ForegroundColor DarkGray; Get-Content $p -Tail 4 | ForEach-Object { Write-Host "    $($_.Substring(0, [Math]::Min(150, $_.Length)))" } }
}
Finish
exit $failed
