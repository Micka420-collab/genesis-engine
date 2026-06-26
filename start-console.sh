#!/usr/bin/env bash
#
#  Genesis Engine - lanceur de l'Earth Console (Linux / macOS).
#  Trouve le bon Python (venv en priorite), bind 0.0.0.0 pour l'acces reseau,
#  affiche l'URL. Tout argument supplementaire est passe a run_earth_console.py.
#
#  Usage : ./start-console.sh                 # port 8090, accessible sur le LAN
#          ./start-console.sh --port 9000     # autre port
#          ./start-console.sh --founders 80   # passe-plat vers le moteur
#
set -euo pipefail
cd "$(dirname "$0")"

# 1. Python : venv d'abord (evite le classique 'python introuvable' sur Ubuntu),
#    sinon python3 / python du systeme.
if [ -x ".venv/bin/python" ]; then PY="./.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then PY="python3"
elif command -v python  >/dev/null 2>&1; then PY="python"
else echo "ERREUR : Python introuvable. Lance d'abord ./install.sh" >&2; exit 1; fi

# 2. Port (defaut 8090, ou --port N passe en argument).
PORT=8090; HAS_PORT=0; prev=""
for a in "$@"; do
  [ "$a" = "--port" ] && HAS_PORT=1
  [ "$prev" = "--port" ] && PORT="$a"
  prev="$a"
done

# 3. IP locale pour l'URL reseau.
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -z "$IP" ] && IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
[ -z "$IP" ] && IP="<ip-locale>"

echo "Earth Console -> http://127.0.0.1:$PORT/   (reseau : http://$IP:$PORT/)"
echo "Ctrl+C pour arreter."
export PYTHONPATH=runtime
# --host 0.0.0.0 : accessible depuis un autre appareil du reseau.
if [ "$HAS_PORT" = 1 ]; then
  exec "$PY" runtime/scripts/run_earth_console.py --host 0.0.0.0 "$@"
else
  exec "$PY" runtime/scripts/run_earth_console.py --host 0.0.0.0 --port "$PORT" "$@"
fi
