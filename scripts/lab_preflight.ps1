# Smart Lab - lab-day network + portal pre-flight (2026-11-03). READ-ONLY: changes nothing on this laptop,
# the router, the robots or any GIU PC. Prints PASS / WARN / FAIL per check and saves logs\preflight-<time>.txt
#   powershell -ExecutionPolicy Bypass -File scripts\lab_preflight.ps1      (full, ~30 s)
#   powershell -ExecutionPolicy Bypass -File scripts\lab_preflight.ps1 -NoDevices   (laptop only, e.g. at home)
param([switch]$NoDevices)
$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path $PSScriptRoot -Parent
$LAB_IP = '192.168.1.200'
# Smart Lab devices (192.168.1.0/24). Edit here if an address changes; tcp = a port that should answer.
$devices = @(
  @{ name = 'Smart Lab router (Huawei)'; ip = '192.168.1.1';   tcp = 80 },
  @{ name = 'FANUC ER-4iA controller';   ip = '192.168.1.100'; tcp = 80 },
  @{ name = 'UR5e controller (RTDE)';    ip = '192.168.1.102'; tcp = 30004 },
  @{ name = 'ESP32-CAM (door face)';     ip = '192.168.1.150'; tcp = $null },
  @{ name = 'Master ESP32 (door)';       ip = '192.168.1.151'; tcp = $null },
  @{ name = 'Environment node';          ip = '192.168.1.152'; tcp = $null },
  @{ name = 'Security camera 1';         ip = '192.168.1.155'; tcp = 554 },
  @{ name = 'Security camera 2';         ip = '192.168.1.156'; tcp = 554 }
)
$rows = New-Object System.Collections.Generic.List[object]
function Add($area, $check, $state, $detail) { $rows.Add([pscustomobject]@{ Area = $area; Check = $check; State = $state; Detail = $detail }) }
function Ping1($ip) { [bool](ping -n 1 -w 1200 $ip | Select-String 'TTL=') }
function Tcp($ip, $port) {
  $c = New-Object Net.Sockets.TcpClient
  try { $ok = $c.ConnectAsync($ip, $port).Wait(1500); $ok -and $c.Connected } catch { $false } finally { $c.Close() }
}

# --- 1. this laptop's addresses and routes
$labAddr = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq $LAB_IP }
if ($labAddr) {
  $if = $labAddr.InterfaceAlias
  Add 'Network' "Smart Lab address $LAB_IP" $(if ($labAddr.AddressState -eq 'Preferred') { 'PASS' } else { 'FAIL' }) "on '$if' ($($labAddr.AddressState))"
  $gw = (Get-NetIPConfiguration -InterfaceAlias $if).IPv4DefaultGateway
  Add 'Network' "No gateway on '$if'" $(if (-not $gw) { 'PASS' } else { 'WARN' }) $(if ($gw) { "gateway $($gw.NextHop) - internet may try the lab router (it has no internet)" } else { 'internet goes out the other adapter' })
  $route = Find-NetRoute -RemoteIPAddress '192.168.1.102' | Select-Object -First 1
  Add 'Network' 'Robots reached over the cable' $(if ($route.InterfaceAlias -eq $if) { 'PASS' } else { 'WARN' }) "192.168.1.102 leaves via '$($route.InterfaceAlias)' (want '$if'; both nets 192.168.1.x at home is expected to differ)"
} else {
  Add 'Network' "Smart Lab address $LAB_IP" 'FAIL' 'not on any adapter - plug the cable into the Smart Lab router; Ethernet IPv4 = 192.168.1.200 / 255.255.255.0, no gateway'
}
$inet = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1
Add 'Network' 'Internet adapter' $(if ($inet) { 'PASS' } else { 'WARN' }) $(if ($inet) { "$($inet.InterfaceAlias) $($inet.IPv4Address.IPAddress) via $($inet.IPv4DefaultGateway.NextHop) (portal works without it)" } else { 'none - the portal and lab work offline; Claude / cloud tools do not' })
$giu = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '10.*' }
if ($giu) { Add 'Network' 'GIU network on this laptop' 'WARN' "$($giu.IPAddress -join ', ') - this laptop should NOT be on the GIU LAN; only the lab engineer PC is" }

# --- 2. firewall (read only)
$rule = Get-NetFirewallRule -DisplayName 'Smart Lab ports'
$ports = if ($rule) { ($rule | Get-NetFirewallPortFilter).LocalPort -join ',' } else { '' }
Add 'Firewall' "'Smart Lab ports' inbound rule" $(if ($rule -and $ports -match '443') { 'PASS' } elseif ($rule) { 'WARN' } else { 'FAIL' }) $(if ($rule) { "ports $ports" } else { 'missing - run firmware\face_server\allow_firewall.bat once as administrator (phones/ESP32 reach the face server :5000 only with it)' })
foreach ($p in Get-NetConnectionProfile) { Add 'Firewall' "Profile of '$($p.InterfaceAlias)'" 'INFO' "$($p.NetworkCategory) (the rule above uses profile=any, so Public is fine)" }

# --- 3. portal + services on this laptop
$h = try { (Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/api/health' -TimeoutSec 8).StatusCode } catch { 0 }
Add 'Portal' 'Backend health :8000' $(if ($h -eq 200) { 'PASS' } else { 'FAIL' }) "HTTP $h"
# HttpWebRequest without redirects: PS 5.1 Invoke-WebRequest -MaximumRedirection 0 returns nothing on a 301 (Gemini audit)
$w = try { $q = [Net.HttpWebRequest]::Create('http://127.0.0.1/'); $q.AllowAutoRedirect = $false; $q.Timeout = 8000
  $rs = $q.GetResponse(); $c = [int]$rs.StatusCode; $rs.Close(); $c
} catch [Net.WebException] { if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 } } catch { 0 }
Add 'Portal' 'Web :80 (redirects to https)' $(if ($w -in 200, 301, 302, 308) { 'PASS' } else { 'FAIL' }) "HTTP $w"
$ds = docker compose --project-directory $root ps --format '{{.Service}}={{.State}}' 2>$null
Add 'Portal' 'Docker services' $(if (($ds | Where-Object { $_ -notmatch '=running' }).Count -eq 0 -and $ds) { 'PASS' } else { 'FAIL' }) ($ds -join ' ')
$listen = Get-NetTCPConnection -State Listen | Select-Object -ExpandProperty LocalPort -Unique
foreach ($p in @(@{p = 443; n = 'HTTPS (phones, PCs)' }, @{p = 5000; n = 'Face server (ESP32-CAM)' }, @{p = 5100; n = 'Security camera 1' }, @{p = 5101; n = 'Security camera 2' }, @{p = 11434; n = 'Ollama (assistant)' }, @{p = 5199; n = 'Knowledge service' })) {
  # a real connect: Docker-published ports (443) are not always in the Windows listen table
  $ok = ($listen -contains $p.p) -or (Tcp '127.0.0.1' $p.p)
  Add 'Services' "$($p.n) :$($p.p)" $(if ($ok) { 'PASS' } else { 'WARN' }) $(if ($ok) { 'answers' } else { 'not answering - start launch.bat (its window shows why)' })
}
$kbKey = try { (Get-Content (Join-Path $root 'tools\knowledge\config.json') -Raw | ConvertFrom-Json).service_key } catch { '' }
$gate = try { Invoke-RestMethod 'http://127.0.0.1:5199/gpu-gate' -TimeoutSec 4 -Headers @{ 'X-KB-Key' = $kbKey } } catch { $null }
if ($gate) { Add 'Services' 'Assistant device (camera-first gate)' 'INFO' (($gate | ConvertTo-Json -Compress -Depth 3) -replace '(.{160}).+', '$1...') }

# --- 4. lab devices (read only: ping + one TCP connect, nothing is sent to a robot)
if (-not $NoDevices) {
  foreach ($d in $devices) {
    $up = Ping1 $d.ip
    $port = if ($d.tcp) { Tcp $d.ip $d.tcp } else { $null }
    $state = if ($up -or $port) { 'PASS' } else { 'FAIL' }
    $detail = "ping $(if ($up) { 'ok' } else { 'no reply' })" + $(if ($d.tcp) { ", tcp $($d.tcp) $(if ($port) { 'open' } else { 'closed' })" } else { '' })
    Add 'Devices' "$($d.name) $($d.ip)" $state $detail
  }
}

# --- output
$colour = @{ PASS = 'Green'; WARN = 'Yellow'; FAIL = 'Red'; INFO = 'Gray' }
Write-Host "Smart Lab pre-flight  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  on $env:COMPUTERNAME"
foreach ($r in $rows) {
  Write-Host ("  {0,-9} {1,-42} " -f $r.Area, $r.Check) -NoNewline
  Write-Host ("{0,-5}" -f $r.State) -ForegroundColor $colour[$r.State] -NoNewline
  Write-Host "  $($r.Detail)" -ForegroundColor DarkGray
}
$f = @($rows | Where-Object State -eq 'FAIL').Count; $wn = @($rows | Where-Object State -eq 'WARN').Count
Write-Host "  $f FAIL, $wn WARN" -ForegroundColor $(if ($f) { 'Red' } elseif ($wn) { 'Yellow' } else { 'Green' })
$logs = Join-Path $root 'logs'; New-Item -ItemType Directory -Force $logs | Out-Null
$out = Join-Path $logs "preflight-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"
$rows | Format-Table -AutoSize | Out-String -Width 220 | Set-Content -Encoding utf8 $out
Write-Host "  saved $out" -ForegroundColor DarkGray
