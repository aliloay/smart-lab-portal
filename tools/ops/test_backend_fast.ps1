# Full backend test suite against a throw-away test database held in memory (2026-11-11).
#   powershell -ExecutionPolicy Bypass -File tools\ops\test_backend_fast.ps1 [pytest args]
# Why: Docker's disk moved to D: (a spinning disk). The tests empty and refill tables thousands of times, and with
# the test database on that disk the suite took hours. This starts a separate PostgreSQL in memory (fsync off),
# runs the suite against it and removes it again. The live database is never touched: tests always use a
# database called smartlab_test (backend/tests/conftest.py), and here it is not even the same server.
param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $PytestArgs)
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
# Random password for this run only (the database lives in memory and is removed at the end); never printed.
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$bytes = New-Object byte[] 18; $rng.GetBytes($bytes)
$dbPass = -join ($bytes | ForEach-Object { $_.ToString('x2') })
# 2026-11-19: a name of its own per run. With one fixed name, a second session starting the suite removed the first
# run's database mid-run (27 errors, all "connection refused"). Nothing here removes another run's container.
$dbName = 'smartlab-testdb-' + $dbPass.Substring(0, 8)
docker run -d --name $dbName --network smart-lab-portal_default `
  --tmpfs /var/lib/postgresql/data:rw,size=1g `
  -e POSTGRES_USER=smartlab -e POSTGRES_PASSWORD=$dbPass -e POSTGRES_DB=smartlab_test `
  postgres:16-alpine -c fsync=off -c synchronous_commit=off -c full_page_writes=off | Out-Null
try {
  do { Start-Sleep 1; docker exec $dbName pg_isready -U smartlab -d smartlab_test 2>$null | Out-Null } while ($LASTEXITCODE -ne 0)
  $args2 = @($PytestArgs | Where-Object { $_ })    # @(): one argument stays an array (a bare string splats per character)
  docker compose run --rm --no-deps -T `
    -e TEST_DATABASE_URL=postgresql+psycopg://smartlab:${dbPass}@${dbName}:5432/smartlab_test `
    -v "${root}\backend:/app" backend python -m pytest -q -p no:cacheprovider @args2
  $code = $LASTEXITCODE
} finally {
  docker rm -f $dbName 2>$null | Out-Null
}
exit $code
