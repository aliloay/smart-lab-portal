# Builds the environment-node enclosure in SOLIDWORKS from params.json (same generator as the door box:
# ..\door_enclosure\Build.cs + EnvParts.cs). Usage: build.ps1 [all|body|panel|plate|assembly] [-Out <folder>]
param([string]$Which = "all", [string]$Out = "out")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$redist = "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist"
$asm = "$redist\SolidWorks.Interop.sldworks.dll", "$redist\SolidWorks.Interop.swconst.dll"
foreach ($a in $asm) { Add-Type -Path $a }
Add-Type -Path (Join-Path $here "..\door_enclosure\Build.cs"), (Join-Path $here "EnvParts.cs") -ReferencedAssemblies ($asm + "System.Core")
$out = Join-Path $here $Out
New-Item -ItemType Directory -Force $out | Out-Null
$t = Get-Date
$log = [Builder]::Run((Join-Path $here "params.json"), $out, $Which)
$log
Add-Type -AssemblyName System.Drawing
Get-ChildItem $out -Filter *.bmp | ForEach-Object {
  $img = [System.Drawing.Image]::FromFile($_.FullName)
  $img.Save(($_.FullName -replace '\.bmp$', '.png'), [System.Drawing.Imaging.ImageFormat]::Png); $img.Dispose()
  Remove-Item $_.FullName
}
"done in {0:0} s -> {1}" -f ((Get-Date) - $t).TotalSeconds, $out
