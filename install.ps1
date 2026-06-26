<#
  Genesis Engine - Installeur Windows (PowerShell)
  Usage :
      powershell -ExecutionPolicy Bypass -File install.ps1
      powershell -ExecutionPolicy Bypass -File install.ps1 -Earth   # + Terre reelle (rasterio/pyproj)
      powershell -ExecutionPolicy Bypass -File install.ps1 -NoSmoke # saute le test final
#>
param(
    [switch]$Earth,
    [switch]$NoSmoke,
    [switch]$NoAi,
    [string]$Model = ""
)

$ErrorActionPreference = "Stop"
$ESC = [char]27
function C($code, $txt) { "$ESC[${code}m$txt$ESC[0m" }
$OK   = C "92" "OK"      # vert
$ERRC = C "91" "ERREUR" # rouge
$total = 5                       # python, venv, pip, deps, doctor
if (-not $NoSmoke) { $total++ }  # + smoke
if (-not $NoAi)    { $total++ }  # + IA locale (Ollama)
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
function Warn($msg)  { Write-Host (C "93" "      [!] $msg") }

# --- IA locale : catalogue de modeles Ollama (observateur/narrateur) --------
$MODELS = @(
    @{ name="llama3.2:1b"; size="1.3 Go"; ram="4 Go";  speed="tres rapide"; qual="basique";  note="ultra-leger" }
    @{ name="llama3.2:3b"; size="2.0 Go"; ram="8 Go";  speed="rapide";      qual="bon";      note="RECOMMANDE (defaut)" }
    @{ name="llama3.1:8b"; size="4.7 Go"; ram="16 Go"; speed="moyen";       qual="tres bon"; note="narration riche" }
    @{ name="phi3:mini";   size="2.3 Go"; ram="8 Go";  speed="rapide";      qual="bon";      note="compact (Microsoft)" }
    @{ name="mistral:7b";  size="4.1 Go"; ram="16 Go"; speed="moyen";       qual="tres bon"; note="polyvalent" }
    @{ name="qwen2.5:7b";  size="4.7 Go"; ram="16 Go"; speed="moyen";       qual="tres bon"; note="multilingue FR" }
)
$DEFAULT_MODEL_IDX = 2

function Print-ModelTable {
    Write-Host (C "90" ("        {0,-2} {1,-15} {2,-8} {3,-6} {4,-12} {5,-10} {6}" -f "#","modele","taille","RAM","vitesse","qualite","note"))
    for ($i=0; $i -lt $MODELS.Count; $i++) {
        $m = $MODELS[$i]
        Write-Host ("        {0,-2} {1,-15} {2,-8} {3,-6} {4,-12} {5,-10} {6}" -f ($i+1), $m.name, $m.size, $m.ram, $m.speed, $m.qual, $m.note)
    }
}

function Ollama-Serving {
    try { $r = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 -UseBasicParsing; return $r.StatusCode -eq 200 }
    catch { return $false }
}

function Write-LlmConfig($name) {
    '{"host": "http://127.0.0.1:11434", "model": "' + $name + '"}' | Out-File -Encoding utf8 -NoNewline genesis_llm.json
    Done "connexion configuree -> genesis_llm.json (modele $name)"
}

function Ai-Step {
    Step "IA locale (Ollama) - observateur/narrateur"
    # 1. Installer Ollama si absent.
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Done "Ollama deja present"
    } elseif (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host (C "90" "      winget install Ollama.Ollama ...")
        winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
        $exe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (Get-Command ollama -ErrorAction SilentlyContinue) { Done "Ollama installe" }
        elseif (Test-Path $exe) { $env:Path += ";" + (Split-Path $exe); Done "Ollama installe" }
        else { Warn "echec winget - telecharge Ollama: https://ollama.com/download"; return }
    } else {
        Warn "winget absent - telecharge Ollama: https://ollama.com/download"; return
    }
    # 2. Demarrer le service si pas en ecoute.
    if (-not (Ollama-Serving)) { Start-Process -WindowStyle Hidden ollama -ArgumentList "serve" -ErrorAction SilentlyContinue; Start-Sleep 2 }
    if (Ollama-Serving) { Done "service Ollama en ecoute (127.0.0.1:11434)" }
    else { Warn "service Ollama pas encore en ecoute (lance 'ollama serve')" }
    # 3. Choix du modele (menu, sauf si -Model fourni).
    $choice = $Model
    if (-not $choice) {
        Write-Host ""; Write-Host "    Choisis le modele a telecharger :"
        Print-ModelTable; Write-Host ""
        $choice = Read-Host ("      Numero [defaut $DEFAULT_MODEL_IDX, 0=aucun, ou un nom Ollama]")
        if (-not $choice) { $choice = "$DEFAULT_MODEL_IDX" }
    }
    if ($choice -eq "0") { Warn "aucun modele telecharge (fais 'ollama pull <nom>' plus tard)"; return }
    if ($choice -match '^[1-9][0-9]*$' -and [int]$choice -le $MODELS.Count) { $name = $MODELS[[int]$choice - 1].name }
    else { $name = $choice }
    # 4. Pull + config (connexion auto).
    Write-Host (C "90" "      ollama pull $name  (peut prendre quelques minutes)...")
    & ollama pull $name
    if ($LASTEXITCODE -eq 0) { Done "modele '$name' pret" } else { Warn "echec du pull de '$name'" }
    Write-LlmConfig $name
}

Banner

# --- Etape 1 : Python -------------------------------------------------------
Step "Verification de Python (3.11 - 3.14 supporte)"
$py = $null
foreach ($c in @("python", "py -3")) {
    try {
        $v = & cmd /c "$c --version" 2>&1
        if ($v -match "Python (\d+)\.(\d+)") { $py = $c; $maj=[int]$Matches[1]; $min=[int]$Matches[2]; break }
    } catch {}
}
if (-not $py) { Fail "Python introuvable. Installe Python 3.11-3.14 depuis https://www.python.org/" }
Done "Python detecte : $v  (via '$py')"
if ($maj -ne 3 -or $min -lt 11) { Fail "Python $maj.$min trop ancien - il faut >= 3.11" }
if ($min -gt 14) { Write-Host (C "93" "      [!] Python 3.$min non officiellement supporte (cible 3.11-3.14) - on continue.") }

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

# --- Etape IA locale (Ollama) ----------------------------------------------
if (-not $NoAi) { Ai-Step }

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
# IP locale (LAN) pour voir/controler l'interface depuis un autre appareil.
$ip = $null
try {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
           Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254*' -and $_.PrefixOrigin -ne 'WellKnown' } |
           Select-Object -First 1).IPAddress
} catch {}
if (-not $ip) { $ip = "<votre-ip-locale>" }
$port = 8090

Write-Host ""
Write-Host (C "92;1" "  +--------------------------------------------------------------+")
Write-Host (C "92;1" "  |   INSTALLATION TERMINEE                                       |")
Write-Host (C "92;1" "  +--------------------------------------------------------------+")
Write-Host ""
Write-Host (C "96;1" "  L'INTERFACE  (Earth Console - voir ET controler le monde)")
Write-Host (C "90"   "  ------------------------------------------------------------")
Write-Host "    Lancer (1 commande, bind reseau + bon Python automatiques) :"
Write-Host (C "97" "      powershell -ExecutionPolicy Bypass -File start-console.ps1")
Write-Host (C "90" "      (accessible depuis un autre appareil ; Ctrl+C pour arreter)")
Write-Host ""
Write-Host "    Ouvrir dans un navigateur :"
Write-Host ("      " + (C "92" "cet ordinateur : ") + (C "97" "http://127.0.0.1:$port/"))
Write-Host ("      " + (C "92" "reseau local   : ") + (C "97" "http://${ip}:$port/"))
Write-Host ""
# Etat de l'IA locale (narrateur).
$aiModel = ""
if (Test-Path genesis_llm.json) {
    try { $aiModel = (Get-Content genesis_llm.json -Raw | ConvertFrom-Json).model } catch {}
}
Write-Host (C "96;1" "  L'IA LOCALE  (Ollama - narrateur, lecture seule)")
Write-Host (C "90"   "  ------------------------------------------------------------")
if ($aiModel) {
    Write-Host ("      " + (C "92" "pret") + " : modele " + (C "97" $aiModel) + " sur http://127.0.0.1:11434")
    Write-Host (C "90" "      Connexion AUTOMATIQUE : le moteur lit genesis_llm.json.")
} else {
    Write-Host (C "90" "      Aucun modele configure. Lance : ollama pull llama3.2:3b")
}
Write-Host "      L'IA DECRIT le monde, elle ne pilote jamais les agents (emergence)."
Write-Host ""
Write-Host (C "96;1" "  COMMENT CA MARCHE")
Write-Host (C "90"   "  ------------------------------------------------------------")
Write-Host "    L'Earth Console sert une page web temps reel (flux SSE) : tu VOIS"
Write-Host "    le monde vivre (climat, biomes, agents, ressources) et tu le"
Write-Host "    CONTROLES en mode dieu (pause, vitesse, perturbations)."
Write-Host ""
Write-Host (C "96;1" "  LE BUT DU PROJET")
Write-Host (C "90"   "  ------------------------------------------------------------")
Write-Host "    Laboratoire de simulation civilisationnelle ZERO script : seules"
Write-Host "    les lois physiques sont codees. Le langage, les outils, la"
Write-Host "    civilisation doivent EMERGER des agents IA - jamais etre scriptes."
Write-Host "    Chaque emergence est inscrite dans un ledger refutable."
Write-Host ""
Write-Host (C "90" "  Doc : README.md  -  docs/EMERGENCE-SIM-v2.md  -  docs/EARTH-CONSOLE.md")
Write-Host ""
