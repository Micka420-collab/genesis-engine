"""Genesis Engine — observateur/narrateur LLM local (Ollama).

Couche d'OBSERVATION uniquement (LLM tier-2, Phase 5). Le modèle LIT un
résumé du monde et le raconte en langage naturel. Il ne décide JAMAIS d'une
action d'agent : la règle « tout doit émerger, jamais être scripté » est
préservée — ce module est read-only sur la simulation, exactement comme les
observers epidemic / lineage / vision.

Connexion : serveur Ollama local (par défaut ``http://127.0.0.1:11434``),
surchargé par la variable d'environnement ``OLLAMA_HOST``. Modèle choisi à
l'installation via ``GENESIS_LLM_MODEL`` (défaut ``llama3.2:3b``).

Aucune dépendance externe : on parle à Ollama via ``urllib`` (stdlib).

Usage::

    from engine.llm_observer import LlmObserver
    obs = LlmObserver()
    if obs.available():
        print(obs.narrate(world.summary()))
"""
from __future__ import annotations

import json
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

PIPELINE_LAYER = "Genesis-L5 Observer (LLM tier-2)"

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:3b"

# Fichier de config écrit par l'installeur (choix du modèle pendant l'install).
# Repli quand les variables d'environnement ne sont pas posées -> connexion
# automatique sans rien exporter à la main.
_CONFIG_NAME = "genesis_llm.json"


def _config() -> Dict[str, str]:
    here = pathlib.Path(__file__).resolve()
    for base in (here.parents[2], here.parents[1]):  # racine dépôt, puis runtime/
        p = base / _CONFIG_NAME
        try:
            if p.is_file():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return {}

# Garde-fou émergence : le narrateur DÉCRIT, il ne PRESCRIT pas. Le prompt
# système interdit explicitement toute consigne d'action.
_SYSTEM_PROMPT = (
    "Tu es un observateur scientifique d'un monde simule. On te donne un "
    "resume chiffre de l'etat du monde (climat, biomes, agents, ressources). "
    "Tu DECRIS ce que tu observes en 2-4 phrases factuelles, en francais. "
    "Tu n'inventes aucun chiffre absent du resume. Tu ne donnes JAMAIS "
    "d'ordre ni de conseil aux agents : tu es un temoin, pas un pilote."
)


def _host() -> str:
    cfg = _config()
    return os.environ.get(
        "OLLAMA_HOST", cfg.get("host", DEFAULT_HOST)).rstrip("/")


def _model() -> str:
    cfg = _config()
    return os.environ.get("GENESIS_LLM_MODEL", cfg.get("model", DEFAULT_MODEL))


@dataclass
class LlmObserver:
    """Narrateur read-only adossé à un Ollama local."""

    host: str = ""
    model: str = ""
    timeout_s: float = 30.0

    def __post_init__(self) -> None:
        self.host = (self.host or _host()).rstrip("/")
        self.model = self.model or _model()

    # -- connexion -----------------------------------------------------------
    def available(self) -> bool:
        """True si le serveur Ollama répond sur ``/api/tags``."""
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def models(self) -> list[str]:
        """Liste des modèles tirés localement (vide si Ollama injoignable)."""
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                data = json.loads(r.read().decode("utf-8"))
            return [m.get("name", "") for m in data.get("models", [])]
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return []

    # -- narration -----------------------------------------------------------
    def narrate(self, summary: Dict[str, Any]) -> Optional[str]:
        """Rend une description en langage naturel d'un ``world.summary()``.

        Retourne ``None`` si Ollama est injoignable (jamais d'exception qui
        casserait un run de simulation).
        """
        payload = {
            "model": self.model,
            "system": _SYSTEM_PROMPT,
            "prompt": "Etat du monde (JSON) :\n" + json.dumps(
                summary, ensure_ascii=False, sort_keys=True, default=str),
            "stream": False,
            # Déterminisme côté narration : température 0, seed fixe.
            "options": {"temperature": 0.0, "seed": 0},
        }
        try:
            req = urllib.request.Request(
                f"{self.host}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                data = json.loads(r.read().decode("utf-8"))
            text = (data.get("response") or "").strip()
            return text or None
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return None


def connection_report() -> Dict[str, Any]:
    """Diagnostic de connexion (pour le smoke et l'Earth Console)."""
    obs = LlmObserver()
    up = obs.available()
    return {
        "layer": PIPELINE_LAYER,
        "host": obs.host,
        "model": obs.model,
        "reachable": up,
        "models_local": obs.models() if up else [],
        "role": "observer-narrator (read-only, emergence-safe)",
    }
