# Smart Lab - synchronized system snapshot for the full-system lab test (2026-11-17). READ-ONLY.
# One CSV row per interval: laptop RAM/CPU/GPU, Docker health, backend health + latency, Ollama residency,
# how long ago each node last reported, and which services listen. It sends nothing to any device, camera or robot,
# changes nothing, prints no keys/credentials/URLs, and writes only logs\lab_snapshot-<time>.csv (git-ignored).
#   powershell -ExecutionPolicy Bypass -File scripts\lab_snapshot.ps1                      (every 60 s for 15 min)
#   powershell -ExecutionPolicy Bypass -File scripts\lab_snapshot.ps1 -Once                (one row, e.g. to test)
#   powershell -ExecutionPolicy Bypass -File scripts\lab_snapshot.ps1 -IntervalSec 30 -Minutes 30
# Stop with Ctrl+C. Node ages come from a read-only SELECT on devices.last_seen_at (no row is changed).
param([int]$IntervalSec = 60, [int]$Minutes = 15, [switch]$Once)
$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force (Join-Path $root 'logs') | Out-Null
$out = Join-Path $root ("logs\lab_snapshot-{0}.csv" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$nodes = @('MASTER_LAB01', 'ENV_LAB01', 'BIN_NODE_1', 'REUSE_BIN_1')
$listen = @(80, 443, 5000, 5100, 5101, 5199, 8000, 11434)

function Listening([int]$p) { [bool](Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue) }

function Row {
  $t = Get-Date
  $os = Get-CimInstance Win32_OperatingSystem
  $freeMb = [math]::Round($os.FreePhysicalMemory / 1KB)
  $commitPct = [math]::Round(100 * ($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / $os.TotalVirtualMemorySize)
  $cpu = [math]::Round((Get-Counter '\Processor(_Total)\% Processor Time' -ErrorAction SilentlyContinue).CounterSamples[0].CookedValue)
  $gpu = (nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu --format=csv,noheader,nounits 2>$null) -split ',\s*'
  $ps = docker ps --format '{{.Names}}|{{.Status}}' 2>$null
  $unhealthy = @($ps | Where-Object { $_ -match 'unhealthy|Restarting|Exited' }).Count
  $restarts = (docker inspect -f '{{.RestartCount}}' (docker ps -q 2>$null) 2>$null | Measure-Object -Sum).Sum
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $h = try { Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 5 } catch { $null }
  $sw.Stop()
  $health = if ($h) { if ($h.status -eq 'ok' -and $h.database -eq $true) { 'ok' } else { 'degraded' } } else { 'down' }
  $ol = try { (Invoke-RestMethod 'http://127.0.0.1:11434/api/ps' -TimeoutSec 3).models } catch { $null }
  $olN = @($ol).Count; $olVram = [math]::Round((@($ol | ForEach-Object { $_.size_vram }) | Measure-Object -Sum).Sum / 1MB)
  # node ages (seconds since last_seen_at), read-only
  $sql = "select device_uid, coalesce(round(extract(epoch from now()-last_seen_at)),-1) from devices where device_uid in ('" + ($nodes -join "','") + "')"
  $ages = @{}
  ($sql | docker exec -i smart-lab-portal-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F,' 2>$null) | ForEach-Object {
    $p = $_ -split ','; if ($p.Count -eq 2) { $ages[$p[0]] = $p[1] } }
  $o = [ordered]@{
    time = $t.ToString('s'); free_ram_mb = $freeMb; commit_pct = $commitPct; cpu_pct = $cpu
    gpu_mem_mb = $gpu[0]; gpu_util_pct = $gpu[1]; gpu_temp_c = $gpu[2]
    docker_unhealthy = $unhealthy; docker_restart_total = $restarts
    backend = $health; backend_ms = [math]::Round($sw.Elapsed.TotalMilliseconds)
    ollama_models = $olN; ollama_vram_mb = $olVram }
  foreach ($n in $nodes) { $o["age_s_$n"] = if ($ages.ContainsKey($n)) { $ages[$n] } else { '' } }
  foreach ($p in $listen) { $o["port_$p"] = [int](Listening $p) }
  [pscustomobject]$o
}

$end = (Get-Date).AddMinutes($Minutes)
do {
  $r = Row
  $r | Export-Csv -NoTypeInformation -Append -Encoding utf8 $out
  Write-Host ("{0}  RAM free {1} MB  CPU {2}%  GPU {3} MB  backend {4} ({5} ms)  docker unhealthy {6}  ages {7}" -f `
    $r.time, $r.free_ram_mb, $r.cpu_pct, $r.gpu_mem_mb, $r.backend, $r.backend_ms, $r.docker_unhealthy,
    (($nodes | ForEach-Object { "$($_.Split('_')[0])=$($r."age_s_$_")" }) -join ' '))
  if ($Once) { break }
  Start-Sleep -Seconds $IntervalSec
} while ((Get-Date) -lt $end)
Write-Host "saved $out"
