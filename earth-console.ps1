# Genesis Earth Console (Windows — équivalent de `make earth-console`)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$env:PYTHONPATH = Join-Path $Root "runtime"
Set-Location $Root
Write-Host "[earth-console] PYTHONPATH=$env:PYTHONPATH"
python (Join-Path $Root "runtime\scripts\run_earth_console.py") @args
