# Builds the MASTER_LAB01 door enclosure parts in SOLIDWORKS from params.json.
#   powershell -ExecutionPolicy Bypass -File tools\cad\door_enclosure\build.ps1 [all|coupon|body|panel|plate|small]
# Output: tools\cad\door_enclosure\out\  (.SLDPRT, .STL, .SLDASM, .png previews). Needs SOLIDWORKS (tested 2025 / v33);
# nothing is installed - the generator is compiled from Build.cs against SOLIDWORKS' own interop assemblies.
#   -Out <folder>: build into another folder (default out\ - which may hold hand-edited SOLIDWORKS files)
param([string]$Which = "all", [string]$Out = "out")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$redist = "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist"
$asm = "$redist\SolidWorks.Interop.sldworks.dll", "$redist\SolidWorks.Interop.swconst.dll"
foreach ($a in $asm) { Add-Type -Path $a }
Add-Type -TypeDefinition ([IO.File]::ReadAllText("$here\Build.cs")) -ReferencedAssemblies ($asm + "System.Core")
$out = Join-Path $here $Out
New-Item -ItemType Directory -Force $out | Out-Null
$t = Get-Date
$log = [Builder]::Run((Join-Path $here "params.json"), $out, $Which)
$log
# previews: SOLIDWORKS writes .bmp; keep small .png copies for the docs
Add-Type -AssemblyName System.Drawing
Get-ChildItem $out -Filter *.bmp | ForEach-Object {
  $img = [System.Drawing.Image]::FromFile($_.FullName)
  $img.Save(($_.FullName -replace '\.bmp$', '.png'), [System.Drawing.Imaging.ImageFormat]::Png); $img.Dispose()
  Remove-Item $_.FullName
}
"done in {0:0} s -> {1}" -f ((Get-Date) - $t).TotalSeconds, $out
