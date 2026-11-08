# Smart Lab - start one launch.bat service with no window (2026-11-02, owner: "no unnecessary terminal windows").
#   powershell -File scripts\bg.ps1 <log name> <normal|low> <command...>
# The command runs in a hidden cmd.exe; everything it prints goes to logs\<log name>.log (appended, with a start line).
# The command line still holds the service's script path, so launch.bat's "already running?" check keeps working.
param([string]$Name, [string]$Priority)
$Command = $args          # everything after the two names, as given (a plain script keeps unknown words in $args)
$logs = Join-Path (Split-Path $PSScriptRoot -Parent) 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs "$Name.log"
try { Add-Content -Encoding utf8 $log "`r`n===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') start: $($Command -join ' ')" -ErrorAction Stop } catch {}   # a locked log must not stop the start
$line = ($Command | ForEach-Object { if ($_ -match '[\s\\]') { '"' + $_ + '"' } else { $_ } }) -join ' '
# Outer quotes: cmd /c strips the first and last quote, so a quoted program path keeps its own quotes.
# < nul: a "pause" in a hidden script returns at once instead of hanging invisibly (and blocking the restart check).
$p = Start-Process cmd.exe -ArgumentList "/c `"$line < nul >> `"$log`" 2>&1`"" -WindowStyle Hidden -PassThru
if ($Priority -eq 'low') { try { $p.PriorityClass = 'BelowNormal' } catch {} }
