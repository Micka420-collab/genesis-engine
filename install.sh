#!/usr/bin/env bash
#
#  Genesis Engine - Installeur Linux / macOS
#  Usage :
#      chmod +x install.sh && ./install.sh
#      ./install.sh --earth     # + Terre reelle (rasterio/pyproj)
#      ./install.sh --no-smoke  # saute le test final
#
set -euo pipefail
cd "$(dirname "$0")"

EARTH=0; NOSMOKE=0
for a in "$@"; do
  case "$a" in
    --earth) EARTH=1 ;;
    --no-smoke) NOSMOKE=1 ;;
    *) echo "option inconnue : $a"; exit 2 ;;
  esac
done

# --- couleurs ---------------------------------------------------------------
if [ -t 1 ]; then
  C(){ printf '\033[%sm' "$1"; }; R(){ printf '\033[0m'; }
else
  C(){ :; }; R(){ :; }
fi
CYAN="96"; GREEN="92"; GREY="90"; WHITE="97;1"; YEL="93"; REDC="91"
TOTAL=6; [ "$NOSMOKE" = 1 ] && TOTAL=5
STEP=0

banner(){
  echo
  echo "$(C $CYAN)  +--------------------------------------------------------------+$(R)"
  echo "$(C $CYAN)  |$(R)$(C $WHITE)            G E N E S I S   E N G I N E                  $(R)$(C $CYAN)    |$(R)"
  echo "$(C $CYAN)  |$(R)$(C $GREY)     Laboratoire de simulation civilisationnelle        $(R)$(C $CYAN)    |$(R)"
  echo "$(C $CYAN)  |$(R)$(C $GREY)       mondes deterministes - agents IA - emergence     $(R)$(C $CYAN)    |$(R)"
  echo "$(C $CYAN)  +--------------------------------------------------------------+$(R)"
  echo
}
step(){ STEP=$((STEP+1)); echo; echo "$(C "$CYAN;1")  [$STEP/$TOTAL]$(R) $(C $WHITE)$1$(R)";
        echo "$(C $GREY)  ------------------------------------------------------------$(R)"; }
done_(){ echo "      [$(C $GREEN)OK$(R)] $1"; }
fail(){ echo "      [$(C $REDC)ERREUR$(R)] $1"; exit 1; }
warn(){ echo "$(C $YEL)      [!] $1$(R)"; }

banner

# --- Etape 1 : Python -------------------------------------------------------
step "Verification de Python (3.11 - 3.13 recommande)"
PY=""; V=""
for c in python3 python python3.13 python3.12 python3.11; do
  command -v "$c" >/dev/null 2>&1 || continue
  vline="$("$c" --version 2>&1 || true)"
  case "$vline" in Python\ 3.*) PY="$c"; V="$vline"; break ;; esac
done
[ -z "$PY" ] && fail "Python 3 introuvable. Installe Python 3.11-3.13 depuis https://www.python.org/"
MAJ="$("$PY" -c 'import sys;print(sys.version_info[0])')"
MIN="$("$PY" -c 'import sys;print(sys.version_info[1])')"
done_ "Python detecte : $V  (via '$PY')"
{ [ "$MAJ" -ne 3 ] || [ "$MIN" -lt 11 ]; } && fail "Python $MAJ.$MIN trop ancien - il faut >= 3.11"
[ "$MIN" -gt 13 ] && warn "Python 3.$MIN non officiellement supporte (cible 3.11-3.13) - on continue."

# --- Etape 2 : venv ---------------------------------------------------------
step "Creation de l'environnement virtuel (.venv)"
if [ -d .venv ]; then done_ ".venv existe deja - reutilise"
else "$PY" -m venv .venv && done_ ".venv cree" || fail "echec creation venv"; fi
VPY="./.venv/bin/python"
[ -x "$VPY" ] || fail "python du venv introuvable ($VPY)"

# --- Etape 3 : pip ----------------------------------------------------------
step "Mise a jour de pip"
"$VPY" -m pip install -U pip --quiet && done_ "pip a jour" || fail "echec mise a jour pip"

# --- Etape 4 : dependances --------------------------------------------------
EXTRA="dev"; [ "$EARTH" = 1 ] && EXTRA="earth,dev"
step "Installation de Genesis Engine  (extras: $EXTRA)"
echo "$(C $GREY)      pip install -e \".[$EXTRA]\"  (peut prendre 1-3 min)...$(R)"
"$VPY" -m pip install -e ".[$EXTRA]" && done_ "Genesis Engine installe en mode editable" \
  || fail "echec installation des dependances"

# --- Etape 5 : doctor -------------------------------------------------------
step "Diagnostic (doctor) - outils + imports"
PYTHONPATH=runtime "$VPY" runtime/scripts/doctor.py && done_ "doctor : environnement sain" \
  || warn "doctor signale des avertissements - voir ci-dessus."

# --- Etape 6 : smoke --------------------------------------------------------
if [ "$NOSMOKE" != 1 ]; then
  step "Test de fumee (p0_smoke) - doit finir par PASSED"
  PYTHONPATH=runtime "$VPY" runtime/scripts/p0_smoke.py && done_ "smoke p0 : PASSED" \
    || fail "le smoke p0 a echoue"
fi

# --- Final ------------------------------------------------------------------
echo
echo "$(C "$GREEN;1")  +--------------------------------------------------------------+$(R)"
echo "$(C "$GREEN;1")  |   INSTALLATION TERMINEE                                       |$(R)"
echo "$(C "$GREEN;1")  +--------------------------------------------------------------+$(R)"
echo
echo "  Pour demarrer :"
echo "$(C 97)    source .venv/bin/activate$(R)"
echo "$(C 97)    PYTHONPATH=runtime python runtime/run.py origins   $(R)$(C $GREY)# biosphere emergente$(R)"
echo "$(C 97)    python -m pytest runtime/tests                     $(R)$(C $GREY)# 800+ tests$(R)"
echo
echo "$(C $GREY)  Doc : README.md  -  docs/EMERGENCE-SIM-v2.md$(R)"
echo
