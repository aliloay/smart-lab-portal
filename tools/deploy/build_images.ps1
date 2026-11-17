# Build the portal images by hand WITH their version stamp (2026-11-18 integration fix).
#
#   powershell -ExecutionPolicy Bypass -File tools\deploy\build_images.ps1 [-Only backend|frontend] [-Tag pre-xyz]
#
# 1. tags the running :latest images as :<Tag> (rollback point; default pre-<yyyyMMdd-HHmm>)
# 2. `docker build` each image with --build-arg BUILD_COMMIT=<git short sha>[-dirty] BUILD_TIME=<yyyyMMddHHmmss>
#    (/api/health "version" and /version.json report it; `docker compose build` exits 0 without building on
#    this laptop since Compose v5, so it is never used here)
# 3. prints each image's creation time so a no-op build cannot pass unnoticed
# It does NOT restart anything. Afterwards (owner's standing local-deploy OK):
#   docker compose up -d --no-deps backend frontend
# Rollback: docker tag smart-lab-portal-<svc>:<Tag> smart-lab-portal-<svc>:latest; then the same `up`.
param(
  [ValidateSet('both', 'backend', 'frontend')] [string]$Only = 'both',
  [string]$Tag = ('pre-' + (Get-Date -Format 'yyyyMMdd-HHmm'))
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$sha = (git -C $repo rev-parse --short HEAD).Trim()
$dirty = (git -C $repo status --porcelain --untracked-files=no)
$commit = if ($dirty) { "$sha-dirty" } else { $sha }
$built = Get-Date -Format 'yyyyMMddHHmmss'
$svcs = if ($Only -eq 'both') { @('backend', 'frontend') } else { @($Only) }
foreach ($svc in $svcs) {
  $img = "smart-lab-portal-${svc}"
  $old = docker images -q "${img}:latest"
  if ($old) { docker tag "${img}:latest" "${img}:$Tag"; Write-Host "rollback point ${img}:$Tag = $old" }
  docker build -t "${img}:latest" --build-arg "BUILD_COMMIT=$commit" --build-arg "BUILD_TIME=$built" (Join-Path $repo $svc)
  if ($LASTEXITCODE -ne 0) { throw "docker build $svc failed (exit $LASTEXITCODE) - running containers untouched" }
  $created = docker inspect -f '{{.Created}}' "${img}:latest"
  Write-Host ("built {0}:latest {1} created {2} stamp {3}-{4}" -f $img, (docker images -q "${img}:latest"), $created, $commit, $built)
}
Write-Host "Next: docker compose up -d --no-deps $($svcs -join ' ')   then check /api/health version.id = $commit-$built"
