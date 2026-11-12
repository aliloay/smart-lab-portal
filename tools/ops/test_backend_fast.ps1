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
docker rm -f smartlab-testdb 2>$null | Out-Null
docker run -d --name smartlab-testdb --network smart-lab-portal_default `
  --tmpfs /var/lib/postgresql/data:rw,size=1g `
  -e POSTGRES_USER=smartlab -e POSTGRES_PASSWORD=testonly -e POSTGRES_DB=smartlab_test `
  postgres:16-alpine -c fsync=off -c synchronous_commit=off -c full_page_writes=off | Out-Null
try {
  do { Start-Sleep 1; docker exec smartlab-testdb pg_isready -U smartlab -d smartlab_test 2>$null | Out-Null } while ($LASTEXITCODE -ne 0)
  $args2 = @($PytestArgs | Where-Object { $_ })    # @(): one argument stays an array (a bare string splats per character)
  docker compose run --rm --no-deps -T `
    -e TEST_DATABASE_URL=postgresql+psycopg://smartlab:testonly@smartlab-testdb:5432/smartlab_test `
    -v "${root}\backend:/app" backend python -m pytest -q -p no:cacheprovider @args2
  $code = $LASTEXITCODE
} finally {
  docker rm -f smartlab-testdb 2>$null | Out-Null
}
exit $code
