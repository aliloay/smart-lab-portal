<#
  Smart Lab - one-command launcher for the core software stack (database, API, portal, backup, and n8n when configured).

  Run from the repository root:
      powershell -ExecutionPolicy Bypass -File .\launch.ps1            # start (reuses existing images)
      powershell -ExecutionPolicy Bypass -File .\launch.ps1 -Build     # rebuild images first

  What it does, in order:
    1. checks Docker is installed and running
    2. checks .env exists and the required keys are set (copy .env.example to .env first)
    3. creates the local folders the stack writes to
    4. "docker compose up -d" (the API applies database migrations itself on start)
    5. waits for the health checks and prints the URLs

  What it never does: delete containers' data ("down -v"), touch the firewall, expose ports beyond docker-compose.yml,
  or start anything that moves hardware (door lock, robots). Camera services, the face server and Ollama are separate:
  see launch.bat and docs/How_To_Run_System.md.
#>
param([switch]$Build, [int]$TimeoutSeconds = 300)
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }
function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# 1. Docker
Step 'Checking Docker'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'Docker is not installed. Install Docker Desktop (free for personal and education use), then run this again.' }
docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail 'Docker is installed but not running. Start Docker Desktop and wait until it says "Engine running".' }
docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Fail 'The Docker Compose plugin is missing. Update Docker Desktop.' }

# 2. .env
Step 'Checking .env'
if (-not (Test-Path '.env')) { Fail '.env not found. Copy .env.example to .env and fill in the values marked as required.' }
$envMap = @{}
foreach ($line in Get-Content '.env') {
  if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$') { $envMap[$Matches[1]] = $Matches[2].Trim('"', "'") }
}
$required = 'POSTGRES_PASSWORD', 'SECRET_KEY', 'DEVICE_API_KEY'
$missing = $required | Where-Object { -not $envMap[$_] -or $envMap[$_] -match '^(change|your|example)' }
if ($missing) { Fail ("Set these keys in .env (no placeholder values): " + ($missing -join ', ')) }
if ($envMap['SECRET_KEY'].Length -lt 32) { Fail 'SECRET_KEY in .env must be at least 32 characters.' }

# 3. local folders (never deletes anything)
Step 'Creating local folders'
foreach ($d in 'backups', 'logs') { if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null } }

# 4. start
if ($Build) { Step 'Building images'; docker compose build; if ($LASTEXITCODE -ne 0) { Fail 'docker compose build failed (see the output above).' } }
Step 'Starting services'
docker compose up -d
if ($LASTEXITCODE -ne 0) { Fail 'docker compose up failed (see the output above). Your data volumes were not touched.' }

# 5. wait for health
Step "Waiting for health checks (up to $TimeoutSeconds s)"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$services = docker compose ps --services
do {
  $states = foreach ($s in $services) {
    $id = docker compose ps -q $s
    if (-not $id) { continue }
    $h = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $id
    [pscustomobject]@{ Service = $s; State = $h }
  }
  $waiting = $states | Where-Object { $_.State -notin 'healthy', 'running' }
  if (-not $waiting) { break }
  Start-Sleep -Seconds 5
} while ((Get-Date) -lt $deadline)
$states | Format-Table -AutoSize | Out-String | Write-Host
if ($waiting) { Fail ("Not healthy in time: " + (($waiting | ForEach-Object { "$($_.Service)=$($_.State)" }) -join ', ') + '. Check "docker compose logs <service>".') }

try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 'http://127.0.0.1:8000/api/health'; $api = $r.StatusCode } catch { $api = 'no answer' }
Write-Host ''
Write-Host 'Smart Lab is running.' -ForegroundColor Green
Write-Host "  Portal (HTTPS):  https://localhost/"
Write-Host "  Portal (HTTP):   http://localhost:8080/"
Write-Host "  API health:      http://127.0.0.1:8000/api/health  ($api)"
if ($services -contains 'n8n') { Write-Host "  n8n (local):     http://127.0.0.1:5678/" }
Write-Host '  Stop with:       powershell -ExecutionPolicy Bypass -File .\stop.ps1   (keeps all data)'
