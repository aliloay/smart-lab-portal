<#
  Smart Lab - stop the project's containers. Keeps every volume (database, uploads, n8n data): it runs "docker compose stop",
  never "down -v". Start again with launch.ps1.
      powershell -ExecutionPolicy Bypass -File .\stop.ps1
#>
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Write-Host 'Docker is not installed; nothing to stop.'; exit 0 }
docker compose --profile automation stop
if ($LASTEXITCODE -ne 0) { Write-Host 'docker compose stop reported an error (see above). No data was deleted.' -ForegroundColor Yellow; exit 1 }
Write-Host 'Smart Lab containers stopped. Data volumes kept.' -ForegroundColor Green
