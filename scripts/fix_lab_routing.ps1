# Smart Lab - send the lab devices out of the Ethernet cable even when Wi-Fi is ALSO a 192.168.1.x network (2026-11-03).
# Problem (measured): Wi-Fi 192.168.1.8/24 and Ethernet 192.168.1.200/24 both own 192.168.1.0/24; Wi-Fi has the lower
# metric, so 192.168.1.102 (UR5e) left over Wi-Fi. Fix: one /32 host route per lab device on Ethernet - a /32 always
# beats a /24, whatever the metrics. Internet, DNS and the Wi-Fi gateway are untouched (no metric swap: with home Wi-Fi
# on 192.168.1.x a swap would send its DNS 192.168.1.1 down the lab cable).
# The routes live in the ActiveStore: a reboot removes them (= automatic rollback).
#   powershell -ExecutionPolicy Bypass -File scripts\fix_lab_routing.ps1            show what WOULD change (read-only)
#   powershell -ExecutionPolicy Bypass -File scripts\fix_lab_routing.ps1 -Apply     add the routes (administrator)
#   powershell -ExecutionPolicy Bypass -File scripts\fix_lab_routing.ps1 -Revert    remove them again (administrator)
# Not needed when the Wi-Fi is a phone hotspot (172.20.10.x / 192.168.43.x): then there is no overlap.
param([switch]$Apply, [switch]$Revert, [string]$Adapter = '')
$LAB_IP = '192.168.1.200'
$hosts = @('192.168.1.1', '192.168.1.100', '192.168.1.101', '192.168.1.102', '192.168.1.150', '192.168.1.151', '192.168.1.152',
           '192.168.1.153', '192.168.1.154', '192.168.1.155', '192.168.1.156', '192.168.1.210')
# .1 = the Smart Lab router: left out automatically when the Wi-Fi network is also 192.168.1.x (its router is .1 too)
$ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -eq $LAB_IP }
if ($Adapter) { $ip = Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias $Adapter -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $ip) { Write-Host "No adapter has $LAB_IP - plug the cable into the Smart Lab router first." -ForegroundColor Red; exit 1 }
$idx = $ip.InterfaceIndex; $alias = $ip.InterfaceAlias
$wifiGw = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Where-Object InterfaceIndex -ne $idx | Select-Object -First 1
$wifiOverlap = $wifiGw -and ((Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $wifiGw.InterfaceIndex).IPAddress -like '192.168.1.*')
if ($wifiOverlap) { $hosts = $hosts | Where-Object { $_ -ne '192.168.1.1' }; Write-Host "Wi-Fi is also 192.168.1.x (router .1 stays on Wi-Fi)." -ForegroundColor Yellow }
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (($Apply -or $Revert) -and -not $admin) { Write-Host 'Run this from an administrator PowerShell.' -ForegroundColor Red; exit 1 }
foreach ($h in $hosts) {
  $p = "$h/32"
  $have = Get-NetRoute -DestinationPrefix $p -InterfaceIndex $idx -PolicyStore ActiveStore -ErrorAction SilentlyContinue
  if ($Revert) {
    if ($have) { Remove-NetRoute -DestinationPrefix $p -InterfaceIndex $idx -Confirm:$false; Write-Host "removed $p" }
  } elseif ($Apply) {
    if (-not $have) { New-NetRoute -DestinationPrefix $p -InterfaceIndex $idx -NextHop 0.0.0.0 -RouteMetric 1 -PolicyStore ActiveStore | Out-Null; Write-Host "added   $p -> $alias" }
  }
  $via = (Find-NetRoute -RemoteIPAddress $h -ErrorAction SilentlyContinue | Select-Object -First 1).InterfaceAlias
  Write-Host ("  {0,-15} leaves via {1}" -f $h, $via) -ForegroundColor $(if ($via -eq $alias) { 'Green' } else { 'Yellow' })
}
$inet = (Find-NetRoute -RemoteIPAddress 8.8.8.8 -ErrorAction SilentlyContinue | Select-Object -First 1).InterfaceAlias
Write-Host "  internet (8.8.8.8) leaves via $inet"
if (-not ($Apply -or $Revert)) { Write-Host 'Dry run - nothing changed. Add -Apply (administrator) to add the routes; a reboot or -Revert removes them.' -ForegroundColor DarkGray }
