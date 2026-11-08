# Smart Lab - deploy the current code to the live portal, in one step (2026-10-27).
# Asks for YOUR admin password at a hidden prompt (used only for deploy.py's read-only smoke tests, never stored
# or shown), then runs tools\deploy\deploy.py: TypeScript check, backend tests, schema check, rollback point
# (:previous images), build, start, health + smoke tests, automatic rollback if anything fails.
#   Right-click > Run with PowerShell   (or: powershell -ExecutionPolicy Bypass -File tools\deploy\deploy_now.ps1)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\..')
$email = Read-Host 'Admin e-mail (Enter = admin@giu-uni.de)'
if (-not $email) { $email = 'admin@giu-uni.de' }
$secure = Read-Host 'Admin password' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:SMARTLAB_EMAIL = $email
  $env:SMARTLAB_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  py -I tools\deploy\deploy.py --full-tests
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  Remove-Item Env:SMARTLAB_PASSWORD -ErrorAction SilentlyContinue
}
Write-Host ''
Write-Host 'Done - the result is above and in backups\deploy_history.jsonl.'
Read-Host 'Press Enter to close'
