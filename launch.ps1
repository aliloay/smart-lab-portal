<#
  Smart Lab - one-command launcher for the core software stack (database, API, portal, backup, and n8n when configured).

  Run from the repository root:
      powershell -ExecutionPolicy Bypass -File .\launch.ps1            # start (reuses existing images)
      powershell -ExecutionPolicy Bypass -File .\launch.ps1 -Build     # rebuild images first

  What it does, in order:
    1. checks Docker is installed and running
    2. checks .env exists and the required keys are set (copy .env.example to .env first)
    3. creates the local folders the stack writes to
    4. "docker compose up -d" (plus --profile automation when AUTOMATION_WEBHOOK_BASE is set; the API applies database migrations itself on start)
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
# n8n is behind the compose profile "automation": started only when .env configures automation (as launch.bat does)
$profileArgs = @()
if ($envMap['AUTOMATION_WEBHOOK_BASE']) { $profileArgs = @('--profile', 'automation') }
if ($Build) { Step 'Building images'; docker compose @profileArgs build; if ($LASTEXITCODE -ne 0) { Fail 'docker compose build failed (see the output above).' } }
Step 'Starting services'
docker compose @profileArgs up -d
if ($LASTEXITCODE -ne 0) { Fail 'docker compose up failed (see the output above). Your data volumes were not touched.' }

# 5. wait for health
Step "Waiting for health checks (up to $TimeoutSeconds s)"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$services = docker compose @profileArgs ps --services
do {
  $states = foreach ($s in $services) {
    $id = docker compose @profileArgs ps -q $s
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

$apiPort = if ($envMap['SMARTLAB_API_PORT']) { $envMap['SMARTLAB_API_PORT'] } else { '8000' }
$httpsPort = if ($envMap['SMARTLAB_HTTPS_PORT']) { ':' + $envMap['SMARTLAB_HTTPS_PORT'] } else { '' }
$httpAltPort = if ($envMap['SMARTLAB_HTTP_ALT_PORT']) { $envMap['SMARTLAB_HTTP_ALT_PORT'] } else { '8080' }
$n8nPort = if ($envMap['SMARTLAB_N8N_PORT']) { $envMap['SMARTLAB_N8N_PORT'] } else { '5678' }
$api = 'no answer'
for ($i = 0; $i -lt 12 -and $api -ne 200; $i++) {     # the API can need a few seconds after its container reports running
  try { $api = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 "http://127.0.0.1:$apiPort/api/health").StatusCode } catch { Start-Sleep -Seconds 5 }
}
if ($api -ne 200) { Fail "The API did not answer on http://127.0.0.1:$apiPort/api/health. Check 'docker compose logs backend'." }
Write-Host ''
Write-Host 'Smart Lab is running.' -ForegroundColor Green
$httpPort = if ($envMap['SMARTLAB_HTTP_PORT']) { ':' + $envMap['SMARTLAB_HTTP_PORT'] } else { '' }
if ((Test-Path 'deploy	ls\server.crt') -and (Test-Path 'deploy	ls\server.key')) {
  Write-Host "  Portal (HTTPS):  https://localhost$httpsPort/"
} else {
  Write-Host "  Portal:          http://localhost$httpPort/   (HTTPS is off until a certificate exists: docs/SECURITY.md)"
}
Write-Host "  Command Center:  http://localhost:$httpAltPort/"
Write-Host "  API health:      http://127.0.0.1:$apiPort/api/health  ($api)"
if ($services -contains 'n8n') { Write-Host "  n8n (local):     http://127.0.0.1:$n8nPort/" }
Write-Host '  Stop with:       powershell -ExecutionPolicy Bypass -File .\stop.ps1   (keeps all data)'
