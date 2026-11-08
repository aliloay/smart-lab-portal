# Builds the reusable-bin floor DOCK in SOLIDWORKS from params.json (run gen_params.py first; same generator as the door box:
# ..\door_enclosure\Build.cs + ..\env_enclosure\EnvParts.cs + DockParts.cs). Usage: build.ps1 [all|tray|cover|body|lid|plate|bin|assembly] [-Out <folder>]
param([string]$Which = "all", [string]$Out = "out")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$redist = "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist"
$asm = "$redist\SolidWorks.Interop.sldworks.dll", "$redist\SolidWorks.Interop.swconst.dll"
foreach ($a in $asm) { Add-Type -Path $a }
Add-Type -Path (Join-Path $here "..\door_enclosure\Build.cs"), (Join-Path $here "..\env_enclosure\EnvParts.cs"), (Join-Path $here "DockParts.cs") -ReferencedAssemblies ($asm + "System.Core")
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
