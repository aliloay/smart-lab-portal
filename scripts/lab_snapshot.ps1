# Smart Lab - synchronized system snapshot for the full-system lab test. READ-ONLY.
# One CSV row per interval: laptop RAM/CPU/GPU, Docker health, backend health + latency, Ollama residency,
# how long ago each node last reported, and which services answer. It sends nothing to any device, camera or robot,
# changes nothing, prints no keys/credentials/URLs, and writes only its own CSV file.
# A source that cannot be read is written as NA - never as 0.
#   powershell -ExecutionPolicy Bypass -File scripts\lab_snapshot.ps1                       (every 60 s for 15 min, logs\)
#   powershell -ExecutionPolicy Bypass -File scripts\lab_snapshot.ps1 -Once                 (one row, e.g. to test)
#   powershell -ExecutionPolicy Bypass -File scripts\lab_snapshot.ps1 -IntervalSec 60 -Minutes 30 -OutDir D:\SmartLabData\lab_2026-11-17
# Stop with Ctrl+C. Node ages come from a read-only SELECT on devices.last_seen_at (no row is changed); "never" = the node
# has never reported. Units: RAM MB, GPU memory MB, commit/CPU/GPU util %, GPU temp C, ages seconds, backend_ms milliseconds.
param([int]$IntervalSec = 60, [int]$Minutes = 15, [switch]$Once, [string]$OutDir = '')
$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path $PSScriptRoot -Parent
if (-not $OutDir) { $OutDir = Join-Path $root 'logs' }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$out = Join-Path $OutDir ("lab_snapshot-{0}-{1}.csv" -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'), $PID)   # never overwrites an earlier file
$nodes = @('MASTER_LAB01', 'ENV_LAB01', 'BIN_NODE_1', 'REUSE_BIN_1')
$containers = [ordered]@{ backend = 'smart-lab-portal-backend-1'; frontend = 'smart-lab-portal-frontend-1'; db = 'smart-lab-portal-db-1'; n8n = 'smart-lab-portal-n8n-1' }
$listen = @(80, 443, 5000, 5100, 5101, 5199, 8000, 11434)
$NA = 'NA'

function Answers([int]$p) {
  # Docker-published ports are not always in the Windows listen table, so also try one plain local connect (nothing is sent)
  if (Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue) { return 1 }
  $c = New-Object Net.Sockets.TcpClient
  try { if ($c.ConnectAsync('127.0.0.1', $p).Wait(400) -and $c.Connected) { 1 } else { 0 } } catch { 0 } finally { $c.Close() }
}

function Row {
  $t = Get-Date
  $os = Get-CimInstance Win32_OperatingSystem
  $freeMb = if ($os) { [math]::Round($os.FreePhysicalMemory / 1KB) } else { $NA }
  $commit = if ($os) { [math]::Round(100 * ($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / $os.TotalVirtualMemorySize) } else { $NA }
  $cs = (Get-Counter '\Processor(_Total)\% Processor Time' -ErrorAction SilentlyContinue).CounterSamples
  $cpu = if ($cs) { [math]::Round($cs[0].CookedValue) } else { $NA }
  $g = (nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu --format=csv,noheader,nounits 2>$null) -split ',\s*'
  $gOk = ($g.Count -eq 3)
  # Docker: per-service health; NA when Docker itself does not answer (never a fabricated "0 unhealthy")
  $dockerUp = [bool](docker info --format '{{.ServerVersion}}' 2>$null)
  $health = @{}; foreach ($k in $containers.Keys) { $v = if ($dockerUp) { (docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $containers[$k] 2>$null) } else { $null }; $health[$k] = if ($v) { $v } else { $NA } }
  $restarts = if ($dockerUp) { (docker inspect -f '{{.RestartCount}}' (docker ps -q 2>$null) 2>$null | Measure-Object -Sum).Sum } else { $null }
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $h = try { Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 5 } catch { $null }
  $sw.Stop()
  $backend = if ($h) { if ($h.status -eq 'ok' -and $h.database -eq $true) { 'ok' } else { 'degraded' } } else { 'down' }
  $ps = try { Invoke-RestMethod 'http://127.0.0.1:11434/api/ps' -TimeoutSec 3 } catch { $null }
  if ($ps) { $olN = @($ps.models).Count; $olV = [math]::Round((@($ps.models | ForEach-Object { $_.size_vram }) | Measure-Object -Sum).Sum / 1MB) } else { $olN = $NA; $olV = $NA }
  # node ages (seconds since last_seen_at), read-only; 'never' = no report ever, NA = the database could not be read
  $sql = "select device_uid, coalesce(round(extract(epoch from now()-last_seen_at))::text,'never') from devices where device_uid in ('" + ($nodes -join "','") + "')"
  $ages = $null
  if ($dockerUp) { $raw = $sql | docker exec -i $containers.db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F,' 2>$null
    if ($LASTEXITCODE -eq 0) { $ages = @{}; $raw | ForEach-Object { $p = $_ -split ','; if ($p.Count -eq 2) { $ages[$p[0]] = $p[1] } } } }
  $o = [ordered]@{
    time = $t.ToString('s'); free_ram_mb = $freeMb; commit_pct = $commit; cpu_pct = $cpu
    gpu_mem_mb = $(if ($gOk) { $g[0] } else { $NA }); gpu_util_pct = $(if ($gOk) { $g[1] } else { $NA }); gpu_temp_c = $(if ($gOk) { $g[2] } else { $NA })
    docker_up = [int]$dockerUp; docker_restart_total = $(if ($null -ne $restarts) { $restarts } else { $NA })
    backend = $backend; backend_ms = [math]::Round($sw.Elapsed.TotalMilliseconds)
    ollama_models = $olN; ollama_vram_mb = $olV }
  foreach ($k in $containers.Keys) { $o["docker_$k"] = $health[$k] }
  foreach ($n in $nodes) { $o["age_s_$n"] = if ($null -eq $ages) { $NA } elseif ($ages.ContainsKey($n)) { $ages[$n] } else { 'unregistered' } }
  foreach ($p in $listen) { $o["port_$p"] = Answers $p }
  [pscustomobject]$o
}

$end = (Get-Date).AddMinutes($Minutes)
do {
  $r = Row
  $r | Export-Csv -NoTypeInformation -Append -Encoding utf8 $out
  Write-Host ("{0}  RAM free {1} MB  CPU {2}%  GPU {3} MB  backend {4} ({5} ms)  docker {6}/{7}/{8}/{9}  ages {10}" -f `
    $r.time, $r.free_ram_mb, $r.cpu_pct, $r.gpu_mem_mb, $r.backend, $r.backend_ms, $r.docker_backend, $r.docker_frontend, $r.docker_db, $r.docker_n8n,
    (($nodes | ForEach-Object { "$($_.Split('_')[0])=$($r."age_s_$_")" }) -join ' '))
  if ($Once) { break }
  Start-Sleep -Seconds $IntervalSec
} while ((Get-Date) -lt $end)
Write-Host "saved $out"
