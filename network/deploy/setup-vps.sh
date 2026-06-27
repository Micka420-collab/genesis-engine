#!/usr/bin/env bash
#
#  Genesis Network — bootstrap d'un VPS Linux (Ubuntu/Debian).
#  À lancer DANS le dossier qui contient le sous-dossier `network/`.
#
#      chmod +x network/deploy/setup-vps.sh
#      ./network/deploy/setup-vps.sh
#
#  Crée un venv, installe les dépendances (fastapi/uvicorn/pydantic),
#  et vérifie que le module démarre. N'expose RIEN : voir QUICKSTART-VPS.md
#  pour le tunnel Cloudflare.
#
set -euo pipefail
cd "$(dirname "$0")/../.."   # → racine contenant network/

if [ ! -d network ]; then
  echo "ERREUR : lance ce script depuis la racine contenant le dossier network/." >&2
  exit 1
fi

echo ">> Python : $(python3 --version)"

# venv isolé
if [ ! -d .venv-genesis ]; then
  echo ">> Création du venv .venv-genesis"
  python3 -m venv .venv-genesis
fi
# shellcheck disable=SC1091
. .venv-genesis/bin/activate

echo ">> Installation des dépendances"
pip install --quiet --upgrade pip
pip install --quiet fastapi "uvicorn[standard]" pydantic

echo ">> Vérification de l'import du module"
python -c "import network.coordinator, network.worldgen, network.store; print('   network OK')"

cat <<'EOF'

============================================================
  ✅ VPS prêt.

  1) Lancer le coordinateur (test en avant-plan) :
       . .venv-genesis/bin/activate
       python -m network coordinator --host 127.0.0.1 --port 8770 --db world.db

  2) Exposer publiquement (Cloudflare Tunnel, gratuit, autre terminal) :
       cloudflared tunnel --url http://localhost:8770
     → copie l'URL https://xxxx.trycloudflare.com affichée.

  3) Partager la commande de don (voir QUICKSTART-VPS.md).

  Pour rester en ligne 24/7 : systemd (deploy/genesis-coordinator.service).
============================================================
EOF
