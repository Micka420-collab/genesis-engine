<#
  Genesis Engine - lanceur de l'Earth Console (Windows).
  Utilise le Python du venv (evite 'python introuvable'), bind 0.0.0.0 pour
  l'acces reseau, affiche l'URL. Les arguments en plus vont au moteur.

  Usage : powershell -ExecutionPolicy Bypass -File start-console.ps1
          .\start-console.ps1 -Port 9000
#>
param(
    [int]$Port = 8090,
    [Parameter(ValueFromRemainingArguments=$true)] $Rest
)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# 1. Python : venv d'abord, sinon python du systeme.
$VPY = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $VPY)) {
    $sys = Get-Command python -ErrorAction SilentlyContinue
    if ($sys) { $VPY = $sys.Source } else { Write-Host "ERREUR : Python introuvable. Lance d'abord install.ps1" -ForegroundColor Red; exit 1 }
}

# 2. IP locale pour l'URL reseau.
$ip = $null
try {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
           Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254*' -and $_.PrefixOrigin -ne 'WellKnown' } |
           Select-Object -First 1).IPAddress
} catch {}
if (-not $ip) { $ip = "<ip-locale>" }

Write-Host "Earth Console -> http://127.0.0.1:$Port/   (reseau : http://${ip}:$Port/)"
Write-Host "Ctrl+C pour arreter."
$env:PYTHONPATH = "runtime"
# --host 0.0.0.0 : accessible depuis un autre appareil du reseau.
& $VPY runtime/scripts/run_earth_console.py --host 0.0.0.0 --port $Port @Rest
