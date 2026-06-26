#!/usr/bin/env bash
#
#  Genesis Engine - Installeur Linux (Ubuntu/Debian) / macOS
#  Usage :
#      chmod +x install.sh && ./install.sh
#      ./install.sh --earth        # + Terre reelle (rasterio/pyproj)
#      ./install.sh --no-smoke     # saute le test final
#      ./install.sh --apt          # paquets systeme (Ubuntu/Debian, sudo)
#      ./install.sh --no-ai        # n'installe pas Ollama / l'IA locale
#      ./install.sh --model NAME   # choisit le modele LLM sans menu (ex: llama3.2:3b)
#
set -euo pipefail
cd "$(dirname "$0")"

EARTH=0; NOSMOKE=0; APT=0; NOAI=0; MODEL_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --earth) EARTH=1 ;;
    --no-smoke) NOSMOKE=1 ;;
    --apt) APT=1 ;;
    --no-ai) NOAI=1 ;;
    --model) shift; MODEL_ARG="${1:-}" ;;
    *) echo "option inconnue : $1"; exit 2 ;;
  esac
  shift
done

# --- detection distribution -------------------------------------------------
DISTRO="inconnu"
if [ -r /etc/os-release ]; then DISTRO="$(. /etc/os-release; echo "${ID:-inconnu}")"; fi
IS_APT=0
command -v apt-get >/dev/null 2>&1 && IS_APT=1

# --- couleurs ---------------------------------------------------------------
if [ -t 1 ]; then
  C(){ printf '\033[%sm' "$1"; }; R(){ printf '\033[0m'; }
else
  C(){ :; }; R(){ :; }
fi
CYAN="96"; GREEN="92"; GREY="90"; WHITE="97;1"; YEL="93"; REDC="91"
TOTAL=5                                   # python, venv, pip, deps, doctor
[ "$NOSMOKE" != 1 ] && TOTAL=$((TOTAL+1))  # + smoke
[ "$APT" = 1 ] && TOTAL=$((TOTAL+1))       # + paquets systeme
[ "$NOAI" != 1 ] && TOTAL=$((TOTAL+1))     # + IA locale (Ollama)
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

# Paquets systeme requis sur Ubuntu/Debian (venv + build des deps natives).
APT_PKGS="python3-venv python3-pip python3-dev build-essential"
apt_install(){
  local sudo=""; [ "$(id -u)" -ne 0 ] && sudo="sudo"
  echo "$(C $GREY)      $sudo apt-get update && $sudo apt-get install -y $APT_PKGS$(R)"
  $sudo apt-get update -qq && $sudo apt-get install -y $APT_PKGS
}
apt_hint(){
  warn "Sur Ubuntu/Debian, installe d'abord les paquets systeme :"
  local sudo=""; [ "$(id -u)" -ne 0 ] && sudo="sudo"
  echo "$(C 97)        $sudo apt-get update && $sudo apt-get install -y $APT_PKGS$(R)"
  echo "$(C $GREY)      puis relance ./install.sh   (ou : ./install.sh --apt)$(R)"
}

# --- IA locale : catalogue de modeles Ollama (observateur/narrateur) --------
# nom|taille|RAM mini|vitesse|qualite|note
MODELS=(
  "llama3.2:1b|1.3 Go|4 Go|tres rapide|basique|ultra-leger"
  "llama3.2:3b|2.0 Go|8 Go|rapide|bon|RECOMMANDE (defaut)"
  "llama3.1:8b|4.7 Go|16 Go|moyen|tres bon|narration riche"
  "phi3:mini|2.3 Go|8 Go|rapide|bon|compact (Microsoft)"
  "mistral:7b|4.1 Go|16 Go|moyen|tres bon|polyvalent"
  "qwen2.5:7b|4.7 Go|16 Go|moyen|tres bon|multilingue FR"
)
DEFAULT_MODEL_IDX=2

print_model_table(){
  echo "$(C $GREY)        #  modele          taille   RAM    vitesse      qualite    note$(R)"
  local i=1 name size ram speed qual note
  for m in "${MODELS[@]}"; do
    IFS='|' read -r name size ram speed qual note <<< "$m"
    printf "        %-2s %-15s %-8s %-6s %-12s %-10s %s\n" \
      "$i" "$name" "$size" "$ram" "$speed" "$qual" "$note"
    i=$((i+1))
  done
}

write_llm_config(){
  printf '{"host": "http://127.0.0.1:11434", "model": "%s"}\n' "$1" > genesis_llm.json
  done_ "connexion configuree -> genesis_llm.json (modele $1)"
}

ollama_serving(){ curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; }

ai_step(){
  step "IA locale (Ollama) - observateur/narrateur"
  # 1. Installer Ollama si absent.
  if command -v ollama >/dev/null 2>&1; then
    done_ "Ollama deja present"
  else
    case "$(uname -s)" in
      Linux)
        if command -v curl >/dev/null 2>&1; then
          echo "$(C $GREY)      curl -fsSL https://ollama.com/install.sh | sh$(R)"
          curl -fsSL https://ollama.com/install.sh | sh \
            && done_ "Ollama installe" \
            || { warn "echec install Ollama - voir https://ollama.com/download"; return 0; }
        else warn "curl absent - installe Ollama: https://ollama.com/download"; return 0; fi ;;
      Darwin)
        if command -v brew >/dev/null 2>&1; then
          brew install ollama && done_ "Ollama installe (brew)" || { warn "echec brew install ollama"; return 0; }
        else warn "telecharge Ollama: https://ollama.com/download"; return 0; fi ;;
      *) warn "OS non reconnu - installe Ollama: https://ollama.com/download"; return 0 ;;
    esac
  fi
  # 2. Demarrer le service si pas deja en ecoute.
  if ! ollama_serving; then (ollama serve >/dev/null 2>&1 &) ; sleep 2; fi
  if ollama_serving; then done_ "service Ollama en ecoute (127.0.0.1:11434)"
  else warn "service Ollama pas encore en ecoute (lance 'ollama serve')"; fi
  # 3. Choix du modele (menu style, sauf si --model fourni).
  local choice="$MODEL_ARG" name
  if [ -z "$choice" ]; then
    echo; echo "    Choisis le modele a telecharger :"
    print_model_table; echo
    if [ -t 0 ]; then
      printf "      Numero [defaut %s, 0=aucun, ou un nom Ollama] : " "$DEFAULT_MODEL_IDX"
      read -r choice || choice=""
    else warn "mode non-interactif -> modele par defaut"; fi
    [ -z "$choice" ] && choice="$DEFAULT_MODEL_IDX"
  fi
  if [ "$choice" = "0" ]; then
    warn "aucun modele telecharge (fais 'ollama pull <nom>' plus tard)"; return 0
  elif printf '%s' "$choice" | grep -qE '^[1-9][0-9]*$' && [ "$choice" -le "${#MODELS[@]}" ]; then
    IFS='|' read -r name _ <<< "${MODELS[$((choice-1))]}"
  else
    name="$choice"   # nom de modele tape directement
  fi
  # 4. Pull + ecriture de la config (connexion auto).
  echo "$(C $GREY)      ollama pull $name  (peut prendre quelques minutes)...$(R)"
  ollama pull "$name" && done_ "modele '$name' pret" || warn "echec du pull de '$name'"
  write_llm_config "$name"
}

banner

# --- Etape 0 (optionnelle) : paquets systeme Ubuntu/Debian ------------------
if [ "$APT" = 1 ]; then
  step "Paquets systeme (Ubuntu/Debian)"
  if [ "$IS_APT" = 1 ]; then apt_install && done_ "paquets systeme installes ($APT_PKGS)" \
      || fail "echec apt-get (droits sudo ?)"
  else warn "apt-get absent (distro '$DISTRO') - etape ignoree."; fi
fi

# --- Etape 1 : Python -------------------------------------------------------
step "Verification de Python (3.11 - 3.14 supporte)"
PY=""; V=""
for c in python3 python python3.13 python3.12 python3.11; do
  command -v "$c" >/dev/null 2>&1 || continue
  vline="$("$c" --version 2>&1 || true)"
  case "$vline" in Python\ 3.*) PY="$c"; V="$vline"; break ;; esac
done
[ -z "$PY" ] && fail "Python 3 introuvable. Installe Python 3.11-3.14 depuis https://www.python.org/"
MAJ="$("$PY" -c 'import sys;print(sys.version_info[0])')"
MIN="$("$PY" -c 'import sys;print(sys.version_info[1])')"
done_ "Python detecte : $V  (via '$PY')"
{ [ "$MAJ" -ne 3 ] || [ "$MIN" -lt 11 ]; } && fail "Python $MAJ.$MIN trop ancien - il faut >= 3.11"
[ "$MIN" -gt 14 ] && warn "Python 3.$MIN non officiellement supporte (cible 3.11-3.14) - on continue."

# --- Etape 2 : venv ---------------------------------------------------------
step "Creation de l'environnement virtuel (.venv)"
if [ -d .venv ]; then
  done_ ".venv existe deja - reutilise"
elif "$PY" -m venv .venv 2>/tmp/ge_venv_err; then
  done_ ".venv cree"
else
  cat /tmp/ge_venv_err 2>/dev/null | sed 's/^/        /'
  # Cas classique Ubuntu/Debian : le module venv/ensurepip manque.
  if [ "$IS_APT" = 1 ]; then
    if [ "$APT" = 1 ]; then fail "venv a echoue malgre --apt - voir l'erreur ci-dessus"; fi
    warn "echec de la creation du venv (paquet python3-venv manquant ?)"
    apt_hint
    fail "installe les paquets systeme puis relance"
  else
    fail "echec creation venv - voir l'erreur ci-dessus"
  fi
fi
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

# --- Etape IA locale (Ollama) ----------------------------------------------
[ "$NOAI" != 1 ] && ai_step

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
# IP locale (LAN) pour voir/controler l'interface depuis un autre appareil.
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -z "$IP" ] && IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
[ -z "$IP" ] && IP="$(ipconfig getifaddr en1 2>/dev/null || true)"
[ -z "$IP" ] && IP="<votre-ip-locale>"
PORT=8090

echo
echo "$(C "$GREEN;1")  +--------------------------------------------------------------+$(R)"
echo "$(C "$GREEN;1")  |   INSTALLATION TERMINEE                                       |$(R)"
echo "$(C "$GREEN;1")  +--------------------------------------------------------------+$(R)"
echo
echo "$(C "$CYAN;1")  L'INTERFACE  (Earth Console - voir ET controler le monde)$(R)"
echo "$(C $GREY)  ------------------------------------------------------------$(R)"
echo "    Lancer :"
echo "$(C 97)      PYTHONPATH=runtime python runtime/scripts/run_earth_console.py$(R)"
echo "$(C $GREY)      (ajoute  --host 0.0.0.0  pour autoriser le controle a distance)$(R)"
echo
echo "    Ouvrir dans un navigateur :"
echo "      $(C $GREEN)cet ordinateur : $(R)$(C 97)http://127.0.0.1:$PORT/$(R)"
echo "      $(C $GREEN)reseau local   : $(R)$(C 97)http://$IP:$PORT/$(R)"
echo
# Etat de l'IA locale (narrateur).
AI_MODEL=""
[ -f genesis_llm.json ] && AI_MODEL="$(sed -n 's/.*"model": *"\([^"]*\)".*/\1/p' genesis_llm.json)"
echo "$(C "$CYAN;1")  L'IA LOCALE  (Ollama - narrateur, lecture seule)$(R)"
echo "$(C $GREY)  ------------------------------------------------------------$(R)"
if [ -n "$AI_MODEL" ]; then
  echo "      $(C $GREEN)pret$(R) : modele $(C 97)$AI_MODEL$(R) sur http://127.0.0.1:11434"
  echo "$(C $GREY)      Connexion AUTOMATIQUE : le moteur lit genesis_llm.json.$(R)"
else
  echo "$(C $GREY)      Aucun modele configure. Lance : ollama pull llama3.2:3b$(R)"
fi
echo "      L'IA DECRIT le monde, elle ne pilote jamais les agents (emergence)."
echo
echo "$(C "$CYAN;1")  COMMENT CA MARCHE$(R)"
echo "$(C $GREY)  ------------------------------------------------------------$(R)"
echo "    L'Earth Console sert une page web temps reel (flux SSE) : tu VOIS"
echo "    le monde vivre (climat, biomes, agents, ressources) et tu le"
echo "    CONTROLES en mode dieu (pause, vitesse, perturbations)."
echo
echo "$(C "$CYAN;1")  LE BUT DU PROJET$(R)"
echo "$(C $GREY)  ------------------------------------------------------------$(R)"
echo "    Laboratoire de simulation civilisationnelle ZERO script : seules"
echo "    les lois physiques sont codees. Le langage, les outils, la"
echo "    civilisation doivent EMERGER des agents IA - jamais etre scriptes."
echo "    Chaque emergence est inscrite dans un ledger refutable."
echo
echo "$(C $GREY)  Doc : README.md  -  docs/EMERGENCE-SIM-v2.md  -  docs/EARTH-CONSOLE.md$(R)"
echo
