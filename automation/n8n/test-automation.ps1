# Smart Lab - n8n automation self-test (Windows PowerShell 5.1+).
# Run test_automation.bat in the project folder, with the portal and n8n up.
#
# It checks, in order:
#   1. the portal accepts AUTOMATION_API_KEY from .env
#      (n8n credential "Smart Lab automation key" must hold the same value)
#   2. n8n is running
#   3. the four event workflows (01, 03, 04, 05) accept an event with
#      AUTOMATION_WEBHOOK_TOKEN (credential "Smart Lab webhook token"),
#      replaying the latest real booking / issue so the workflow runs end to end
#   4. which workflows reported a run back to the portal in the last 2 minutes
# Safe to repeat: every notification and alert n8n creates has a dedupe key,
# so a replay never creates a duplicate.

$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Push-Location $root
$envFile = Join-Path $root '.env'

function Get-EnvValue($name) {
  if (-not (Test-Path $envFile)) { return '' }
  $m = Select-String -Path $envFile -Pattern "^$name=(.*)$" | Select-Object -First 1
  if ($m) { return $m.Matches[0].Groups[1].Value.Trim() } else { return '' }
}
function Ok($msg)   { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Bad($msg)  { Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Info($msg) { Write-Host "         $msg" -ForegroundColor Gray }
function Sql($q)    { docker compose exec -T db psql -U smartlab -d smartlab -tAc $q }
function First($q)  { $r = Sql $q; if ($r) { return ("$r").Trim() } else { return '' } }

$key   = Get-EnvValue 'AUTOMATION_API_KEY'
$token = Get-EnvValue 'AUTOMATION_WEBHOOK_TOKEN'

Write-Host "`n1) Portal automation key" -ForegroundColor Cyan
if (-not $key) { Bad 'AUTOMATION_API_KEY is empty in .env' }
else {
  try {
    Invoke-RestMethod 'http://localhost/api/automation/health' -Headers @{ 'X-Automation-Key' = $key } | Out-Null
    Ok 'The portal accepts the key in .env.'
    Info 'If a workflow still says "Invalid automation key", its globe (HTTP) nodes use the'
    Info 'wrong credential, or "Smart Lab automation key" in n8n holds a different value.'
  } catch { Bad "The portal rejected the key in .env ($($_.Exception.Message)). Restart with launch.bat." }
}

Write-Host "`n2) n8n" -ForegroundColor Cyan
try { Invoke-WebRequest 'http://localhost:5678/healthz' -UseBasicParsing | Out-Null; Ok 'n8n is running on http://localhost:5678' }
catch { Bad 'n8n is not reachable on port 5678 - is AUTOMATION_WEBHOOK_BASE set in .env and launch.bat running?'; Pop-Location; exit 1 }

Write-Host "`n3) Event workflows (webhooks)" -ForegroundColor Cyan
if (-not $token) { Bad 'AUTOMATION_WEBHOOK_TOKEN is empty in .env' }
$booking = First "select coalesce(max(id),0) from bookings where status='CONFIRMED'"
$issue   = First "select coalesce(max(id),0) from issues"
$lab     = First "select coalesce(min(id),1) from labs"
$device  = First "select coalesce(min(id),0) from devices"

$tests = @(
  @{ name = '01 Booking confirmation';  path = 'smartlab-booking-confirmed'; skip = ($booking -eq '0' -or -not $booking)
     body = @{ type = 'booking.confirmed'; lab_id = [int]$lab; object = @{ type = 'booking'; id = "$booking" } } },
  @{ name = '03 Access denial';         path = 'smartlab-access-denied';     skip = $false
     body = @{ type = 'access.denied'; lab_id = [int]$lab; payload = @{ reason = 'SELF_TEST' } } },
  @{ name = '04 Device offline';        path = 'smartlab-device-offline';    skip = ($device -eq '0' -or -not $device)
     body = @{ type = 'device.offline'; device_id = [int]$device } },
  @{ name = '05 Maintenance';           path = 'smartlab-issue-created';     skip = ($issue -eq '0' -or -not $issue)
     body = @{ type = 'issue.created'; lab_id = [int]$lab; object = @{ type = 'issue'; id = "$issue" } } }
)
foreach ($t in $tests) {
  if ($t.skip) { Write-Host "  [SKIP] $($t.name): nothing in the database to test with yet" -ForegroundColor Yellow; continue }
  try {
    Invoke-RestMethod -Method Post "http://localhost:5678/webhook/$($t.path)" `
      -Headers @{ 'X-Smartlab-Token' = $token } -ContentType 'application/json' `
      -Body ($t.body | ConvertTo-Json -Depth 5) | Out-Null
    Ok "$($t.name): n8n accepted the event"
  } catch {
    $code = 0
    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
    if ($code -eq 404)                   { Bad "$($t.name): webhook not found - open the workflow and click Publish" }
    elseif ($code -eq 401 -or $code -eq 403) { Bad "$($t.name): token rejected - the first (pink) node must use 'Smart Lab webhook token'" }
    else                                 { Bad "$($t.name): $($_.Exception.Message)" }
  }
}

Write-Host "`n4) Runs reported back to the portal (last 2 minutes)" -ForegroundColor Cyan
Start-Sleep -Seconds 8
$runs = Sql "select to_char(created_at at time zone 'Africa/Cairo','HH24:MI:SS') || '  ' || rpad(entity_id, 32) || coalesce(detail->>'status','') from audit_logs where action='AUTOMATION_RUN' and created_at > now() - interval '2 minutes' order by id"
if ($runs) { $runs | ForEach-Object { if ("$_".Trim()) { Write-Host "         $_" } } }
else { Bad 'No workflow reported a run. Open n8n > Overview > Executions and click the red run to see which node failed.' }
Info 'A workflow that got the event but is missing here stopped at a red node:'
Info 'open it in n8n > Executions. "Authorization failed" = that node needs "Smart Lab automation key".'

Write-Host "`n5) Scheduled workflows (02, 06-12)" -ForegroundColor Cyan
Info 'These run on their own timers. To test one now: open it in n8n and click "Execute workflow".'
Info 'Green on every node = working. Then run this script again to see its run in step 4.'
Write-Host ''
Pop-Location
