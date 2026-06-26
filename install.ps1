<#
  Genesis Engine - Installeur Windows (PowerShell)
  Usage :
      powershell -ExecutionPolicy Bypass -File install.ps1
      powershell -ExecutionPolicy Bypass -File install.ps1 -Earth   # + Terre reelle (rasterio/pyproj)
      powershell -ExecutionPolicy Bypass -File install.ps1 -NoSmoke # saute le test final
#>
param(
    [switch]$Earth,
    [switch]$NoSmoke
)

$ErrorActionPreference = "Stop"
$ESC = [char]27
function C($code, $txt) { "$ESC[${code}m$txt$ESC[0m" }
$OK   = C "92" "OK"      # vert
$ERRC = C "91" "ERREUR" # rouge
$total = if ($NoSmoke) { 5 } else { 6 }
$script:step = 0

function Banner {
    Write-Host ""
    Write-Host (C "96" "  +--------------------------------------------------------------+")
    Write-Host (C "96" "  |") (C "97;1" "            G E N E S I S   E N G I N E                  ") (C "96" "    |")
    Write-Host (C "96" "  |") (C "90"   "     Laboratoire de simulation civilisationnelle        ") (C "96" "    |")
    Write-Host (C "96" "  |") (C "90"   "       mondes deterministes - agents IA - emergence     ") (C "96" "    |")
    Write-Host (C "96" "  +--------------------------------------------------------------+")
    Write-Host ""
}

function Step($title) {
    $script:step++
    Write-Host ""
    Write-Host (C "96;1" ("  [$($script:step)/$total] ")) (C "97;1" $title)
    Write-Host (C "90" "  ------------------------------------------------------------")
}

function Done($msg)  { Write-Host "      [$OK] $msg" }
function Fail($msg)  { Write-Host "      [$ERRC] $msg" -ForegroundColor Red; exit 1 }

Banner

# --- Etape 1 : Python -------------------------------------------------------
Step "Verification de Python (3.11 - 3.13 recommande)"
$py = $null
foreach ($c in @("python", "py -3")) {
    try {
        $v = & cmd /c "$c --version" 2>&1
        if ($v -match "Python (\d+)\.(\d+)") { $py = $c; $maj=[int]$Matches[1]; $min=[int]$Matches[2]; break }
    } catch {}
}
if (-not $py) { Fail "Python introuvable. Installe Python 3.11-3.13 depuis https://www.python.org/" }
Done "Python detecte : $v  (via '$py')"
if ($maj -ne 3 -or $min -lt 11) { Fail "Python $maj.$min trop ancien - il faut >= 3.11" }
if ($min -gt 13) { Write-Host (C "93" "      [!] Python 3.$min non officiellement supporte (cible 3.11-3.13) - on continue.") }

# --- Etape 2 : venv ---------------------------------------------------------
Step "Creation de l'environnement virtuel (.venv)"
if (Test-Path ".venv") { Done ".venv existe deja - reutilise" }
else { & cmd /c "$py -m venv .venv"; if ($LASTEXITCODE) { Fail "echec creation venv" }; Done ".venv cree" }
$VPY = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $VPY)) { Fail "python du venv introuvable ($VPY)" }

# --- Etape 3 : pip ----------------------------------------------------------
Step "Mise a jour de pip"
& $VPY -m pip install -U pip --quiet; if ($LASTEXITCODE) { Fail "echec mise a jour pip" }
Done "pip a jour"

# --- Etape 4 : dependances --------------------------------------------------
$extra = if ($Earth) { "earth,dev" } else { "dev" }
Step "Installation de Genesis Engine  (extras: $extra)"
Write-Host (C "90" "      pip install -e `".[$extra]`"  (peut prendre 1-3 min)...")
& $VPY -m pip install -e ".[$extra]"; if ($LASTEXITCODE) { Fail "echec installation des dependances" }
Done "Genesis Engine installe en mode editable"

# --- Etape 5 : doctor -------------------------------------------------------
Step "Diagnostic (doctor) - outils + imports"
$env:PYTHONPATH = "runtime"
& $VPY runtime/scripts/doctor.py
if ($LASTEXITCODE) { Write-Host (C "93" "      [!] doctor signale des avertissements - voir ci-dessus.") }
else { Done "doctor : environnement sain" }

# --- Etape 6 : smoke --------------------------------------------------------
if (-not $NoSmoke) {
    Step "Test de fumee (p0_smoke) - doit finir par PASSED"
    & $VPY runtime/scripts/p0_smoke.py
    if ($LASTEXITCODE) { Fail "le smoke p0 a echoue" }
    Done "smoke p0 : PASSED"
}

# --- Final ------------------------------------------------------------------
Write-Host ""
Write-Host (C "92;1" "  +--------------------------------------------------------------+")
Write-Host (C "92;1" "  |   INSTALLATION TERMINEE                                       |")
Write-Host (C "92;1" "  +--------------------------------------------------------------+")
Write-Host ""
Write-Host "  Pour demarrer :"
Write-Host (C "97" "    .\.venv\Scripts\activate")
Write-Host (C "97" "    `$env:PYTHONPATH='runtime'; python runtime/run.py origins   ") (C "90" "# biosphere emergente")
Write-Host (C "97" "    python -m pytest runtime/tests                            ") (C "90" "# 800+ tests")
Write-Host ""
Write-Host (C "90" "  Doc : README.md  -  docs/EMERGENCE-SIM-v2.md")
Write-Host ""
