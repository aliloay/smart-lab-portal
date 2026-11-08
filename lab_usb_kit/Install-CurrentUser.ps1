# Smart Lab - install the PC agent for THE WINDOWS ACCOUNT THAT RUNS THIS, without administrator rights and without cmd.
# Each authorized account runs it once under its own login. It does not touch other accounts.
#
#   powershell -ExecutionPolicy Bypass is NOT used or needed by this kit: if script execution is blocked on a PC, that is
#   a university setting. Report it to GIU IT (see the guide) instead of working around it.
#
#   Right-click -> Run with PowerShell, or:  .\Install-CurrentUser.ps1 [-Role Auto|Engineer|Lab] [-InstallRoot <folder>]
#
# What it does: copies the kit to %USERPROFILE%\SmartLab, stores the enrollment code protected with Windows DPAPI for this
# account, adds one HKCU Run entry, starts the agent now. Run it again to repair or upgrade; the portal card stays the same.
param(
    [ValidateSet('Auto', 'Engineer', 'Lab')][string]$Role = 'Auto',
    [string]$InstallRoot = (Join-Path $env:USERPROFILE 'SmartLab'),
    [string]$RunName = 'SmartLab',
    [string]$KitDevice = '',       # testing only: the device name to use
    [switch]$SkipLegacyCleanup,    # testing only: leave entries of older kits alone
    [switch]$NoPause
)
$ErrorActionPreference = 'Stop'
function Finish { if ($PSScriptRoot -and -not $NoPause) { [void](Read-Host 'Press Enter to close') } }
function Say($text, $color = 'Gray') { Write-Host $text -ForegroundColor $color }
trap { Say "ERROR: $_" Red; Say 'Nothing was bypassed. Send a photo of this window to the Smart Lab admin.' Yellow; Finish; break }
$src = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

# ---- 1. kit complete and undamaged?
foreach ($need in 'MANIFEST.json', 'site.json', 'enroll.key', 'python\pythonw.exe', 'python\python.exe', 'pc_agent\agent_boot.py', 'pc_agent\pc_agent.py', 'pc_agent\status_tray.py', 'relay\relay.py') {
    if (-not (Test-Path (Join-Path $src $need))) { Say "The kit is incomplete: $need is missing in $src" Red; Finish; return }
}
$manifest = Get-Content -Raw (Join-Path $src 'MANIFEST.json') | ConvertFrom-Json
$bad = @()
foreach ($item in $manifest.files.PSObject.Properties) {
    if ($item.Name -like 'python/*' -and $item.Name -notmatch '^python/pythonw?\.exe$') { continue }    # runtime: Check-CurrentUser.ps1 -Full
    $file = Join-Path $src $item.Name
    if (-not (Test-Path $file) -or (Get-FileHash $file -Algorithm SHA256).Hash.ToLower() -ne $item.Value) { $bad += $item.Name }
}
if ($bad.Count) { Say "The kit is damaged - copy it again. Wrong files: $($bad -join ', ')" Red; Finish; return }

# ---- 2. which PC? All addresses come from site.json; change them there, not in this script.
$site = Get-Content -Raw (Join-Path $src 'site.json') | ConvertFrom-Json
$ips = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() |
    ForEach-Object { $_.GetIPProperties().UnicastAddresses } | ForEach-Object { $_.Address.IPAddressToString }
$eng = switch ($Role) {
    'Engineer' { $true } 'Lab' { $false }
    default { ($site.engineer_hosts -contains $env:COMPUTERNAME) -or ($ips -contains $site.relay_address) }
}
$dev = if ($KitDevice) { $KitDevice } elseif ($eng) { $site.engineer_device } else { "PC_$env:COMPUTERNAME" }
$portal = if ($eng) { $site.portal_direct } else { $site.portal_via_relay }
$web = if ($eng) { $site.web_direct } else { $site.web_via_relay }
Say "Smart Lab $($manifest.version) on $env:COMPUTERNAME for account $env:USERNAME as $dev" Cyan
Say "  portal: $portal"

# ---- 3. stop this account's old copy (supervisor first)
foreach ($pattern in 'agent_boot\.py', 'pc_agent\.py|relay\.py') {
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match $pattern } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }   # another account's fails, as it should
}
Start-Sleep -Seconds 1

# ---- 4. entries and plain keys left by older kits, for this account only
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if (-not $SkipLegacyCleanup) {
    try { Unregister-ScheduledTask -TaskName 'SmartLab watchdog' -Confirm:$false -ErrorAction SilentlyContinue } catch { }
    foreach ($n in 'SmartLab relay', 'SmartLab agent') { Remove-ItemProperty -Path $runKey -Name $n -ErrorAction SilentlyContinue }
    $startup = [Environment]::GetFolderPath('Startup')
    foreach ($old in (Join-Path $startup 'SmartLab_autostart.cmd'), (Join-Path $startup 'SmartLab_autostart.cmd.old'),
                     (Join-Path $startup 'SmartLab relay.lnk'), (Join-Path $startup 'SmartLab agent.lnk'), 'C:\SmartLab\device.key', 'C:\SmartLab\enroll.key') {
        if (Test-Path $old) { Remove-Item $old -Force -ErrorAction SilentlyContinue }
    }
}

# ---- 5. copy
New-Item -ItemType Directory -Force $InstallRoot | Out-Null
foreach ($d in 'python', 'pc_agent', 'relay') {
    $to = Join-Path $InstallRoot $d
    if (Test-Path $to) { Remove-Item $to -Recurse -Force }
    Copy-Item (Join-Path $src $d) $to -Recurse -Force
}
Copy-Item (Join-Path $src 'MANIFEST.json') $InstallRoot -Force
$pyw = Join-Path $InstallRoot 'python\pythonw.exe'
if (-not (Test-Path $pyw)) { throw "Windows or the university's security software refused the copy in $InstallRoot." }
Start-Sleep -Seconds 3
if (-not (Test-Path $pyw)) { Say "Security software removed the program from $InstallRoot. This is a university policy decision: ask GIU IT. Stopping." Red; Finish; return }

# ---- 6. credentials: enrollment code under DPAPI, for this account only. The key is never shown or kept in the clear.
Add-Type -AssemblyName System.Security
$key = Join-Path $InstallRoot 'device.key'
$code = Join-Path $InstallRoot 'enroll.key'
$haveKey = Test-Path $key
if (-not $haveKey) {
    $plain = [Text.Encoding]::UTF8.GetBytes((Get-Content -Raw (Join-Path $src 'enroll.key')).Trim())
    $blob = [Security.Cryptography.ProtectedData]::Protect($plain, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
    [IO.File]::WriteAllText($code, 'DPAPI1:' + [Convert]::ToBase64String($blob), (New-Object System.Text.UTF8Encoding($false)))
}

# ---- 7. settings and start-up: one HKCU Run entry, nothing else
$agentArgs = @('--device', $dev, '--lab', $site.lab, '--portal', $portal, '--web', $web, '--key-file', $key, '--enroll-file', $code)
$relayArgs = @()
if ($eng) {
    $relayArgs = @('--listen', $site.relay_address)
    foreach ($m in $site.relay_map) { $relayArgs += @('--map', $m) }
    foreach ($a in $site.relay_allow) { $relayArgs += @('--allow', $a) }
}
$cfg = [ordered]@{ device = $dev; portal = $portal; web = $web; agent_args = $agentArgs; relay_args = $relayArgs; wait_for_other_account = $true; run_name = $RunName } | ConvertTo-Json -Depth 3
$cfgFile = Join-Path $InstallRoot 'smartlab.json'
[IO.File]::WriteAllText($cfgFile, $cfg, (New-Object System.Text.UTF8Encoding($false)))
$boot = Join-Path $InstallRoot 'pc_agent\agent_boot.py'
$bootArgs = "-E -s `"$boot`" --config `"$cfgFile`""
Set-ItemProperty -Path $runKey -Name $RunName -Value "`"$pyw`" $bootArgs"
Say "  starts at every sign-in of $env:USERNAME (HKCU Run: $RunName). Other accounts need their own install." Gray

# ---- 8. start and prove it
Start-Process -FilePath $pyw -ArgumentList $bootArgs -WorkingDirectory $InstallRoot -WindowStyle Hidden
$registered = $false
for ($i = 0; $i -lt 15 -and -not $registered; $i++) {
    Start-Sleep -Seconds 2
    if (Test-Path $key) { $registered = $true }
}
$running = Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'pc_agent\.py' -and $_.CommandLine -like "*$InstallRoot*" }
if ($running) { Say 'OK    agent running. Look for the Smart Lab icon in the notification area.' Green }
else { Say "FAIL  agent is not running. Logs: $env:TEMP\smartlab_agent.log and smartlab_boot.log" Red }
if ($registered) { Say "OK    this account has its own key for $dev, protected with DPAPI" Green }
else { Say 'WAIT  the portal does not answer yet. Nothing to do: it registers by itself when the portal can be reached.' Yellow }
Say 'Check any time with Check-CurrentUser.ps1.' Cyan
Finish
