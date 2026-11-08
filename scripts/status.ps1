# Smart Lab - are the launch.bat services up AND answering? (2026-11-03; ports + docker + RAM/VRAM after the Gemini audit)
#   powershell -ExecutionPolicy Bypass -File scripts\status.ps1          one table
#   powershell -ExecutionPolicy Bypass -File scripts\status.ps1 -Watch   refresh every 5 s (Ctrl+C to quit)
# Read-only: running processes, one TCP connect per port, the portal health URL, docker compose ps, logs\<service>.log.
#   UP       process running and its port answers (or it has no port)
#   STARTING process running, port not answering yet (still loading models, or hung)
#   DOWN     no process
param([switch]$Watch)
$root = Split-Path $PSScriptRoot -Parent
# service = log name in logs\, match = text in the running process's command line, port = what it serves (0 = none)
$services = [ordered]@{
  face_server      = @('face_server.py', 5000)
  security_camera  = @('security_vision.py*SECCAM_LAB01', 5100)
  security_camera2 = @('security_vision.py*SECCAM_LAB02', 5101)
  ur5e_monitor     = @('ur5e', 0)
  fanuc_monitor    = @('fanuc', 0)
  ollama           = @('ollama.exe*serve', 11434)
  knowledge        = @('knowledge*serve.py', 5199)
  voice            = @('voice_service.py', 5320)
  opcua            = @('opcua_server.py', 4840)
  pc_agent         = @('pc_agent.py', 0)
  lan_presence     = @('lan_presence.py', 0)
  mdns             = @('announce.py', 0)
}
function Tcp($port) {
  $c = New-Object Net.Sockets.TcpClient
  try { $c.ConnectAsync('127.0.0.1', $port).Wait(700) -and $c.Connected } catch { $false } finally { $c.Close() }
}
function Show {
  $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='py.exe' or Name='ollama.exe' or Name='python3.exe'" |
           Where-Object CommandLine | Select-Object -ExpandProperty CommandLine
  $rows = foreach ($s in $services.Keys) {
    $match, $port = $services[$s]
    $up = [bool]($procs | Where-Object { $_ -like "*$match*" })
    $state = if (-not $up) { 'DOWN' } elseif ($port -and -not (Tcp $port)) { 'STARTING' } else { 'UP' }
    $log = Join-Path $root "logs\$s.log"
    $last = if (Test-Path $log) { [string](Get-Content $log -Tail 1 -ErrorAction SilentlyContinue) } else { '(no log yet)' }
    if ($last.Length -gt 70) { $last = $last.Substring(0, 70) + '...' }
    [pscustomobject]@{ Service = $s; Port = $(if ($port) { $port } else { '' }); State = $state; Last = $last }
  }
  try { $h = (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health -TimeoutSec 5).StatusCode } catch { $h = 'no answer' }
  $os = Get-CimInstance Win32_OperatingSystem
  $free = [int]($os.FreePhysicalMemory / 1KB); $total = [int]($os.TotalVisibleMemorySize / 1KB)
  $vram = try { (& nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits 2>$null) -replace ',\s*', ' / ' } catch { '' }
  Write-Host "Smart Lab services  $(Get-Date -Format 'HH:mm:ss')   portal health: $h   free RAM: $free / $total MB" -NoNewline
  Write-Host $(if ($vram) { "   GPU: $vram MB" } else { '' })
  if ($free -lt 1500) { Write-Host "  LOW MEMORY: close browser tabs / extra VS Code windows" -ForegroundColor Yellow }
  $ds = docker compose --project-directory $root ps -a --format '{{.Service}}={{.State}}' 2>$null
  if ($ds) {
    Write-Host '  docker:' -NoNewline
    foreach ($d in $ds) { $n, $st = $d -split '=', 2; Write-Host " $n " -NoNewline; Write-Host $st -ForegroundColor $(if ($st -eq 'running') { 'Green' } else { 'Red' }) -NoNewline }
    Write-Host ''
  } else { Write-Host '  docker: not answering (start Docker Desktop)' -ForegroundColor Red }
  foreach ($r in $rows) {
    $c = @{ UP = 'Green'; STARTING = 'Yellow'; DOWN = 'Red' }[$r.State]
    Write-Host ("  {0,-17}{1,6} " -f $r.Service, $r.Port) -NoNewline; Write-Host ("{0,-9}" -f $r.State) -ForegroundColor $c -NoNewline
    Write-Host "  $($r.Last)" -ForegroundColor DarkGray
  }
  $down = @($rows | Where-Object State -eq 'DOWN').Count; $slow = @($rows | Where-Object State -eq 'STARTING').Count
  if ($down) { Write-Host "  $down down - see logs\<service>.log; run launch.bat again to restart only the missing ones." -ForegroundColor Yellow }
  if ($slow) { Write-Host "  $slow starting - give cameras ~1 min to load; still STARTING after 3 min = check its log." -ForegroundColor Yellow }
}
if ($Watch) { while ($true) { Clear-Host; Show; Start-Sleep 5 } } else { Show }
