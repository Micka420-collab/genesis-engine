"""Extension non-invasive du dashboard : endpoints audio + artefacts.

Ce module n'altère ni `communication.py` ni `knowledge_artifacts.py`. Il
patche dynamiquement la classe `_Handler` du dashboard en wrappant `do_GET`
pour intercepter trois nouvelles routes avant la chaîne existante :

    GET /api/audio?listener_x&listener_y&listener_row
    GET /api/audio/history?row=N&n=30
    GET /api/artifacts?xmin&ymin&xmax&ymax

Utilisation depuis `dashboard.py` :

    from engine.audio_endpoints import register_audio_endpoints
    register_audio_endpoints(_Handler, sim, sound_field, knowledge_registry)

Tout est exposé en JSON. Les phonèmes sont décodés à partir du vecteur
lexical 16-D du locuteur via `lexicon_to_phonemes`.
"""
from __future__ import annotations

import json
from typing import Dict, Optional

import numpy as np

from engine.communication import (
    AUDIBILITY_THRESHOLD_DB,
    SoundField,
    lexicon_to_phonemes,
    utterance_to_dict,
)
from engine.knowledge_artifacts import (
    ArtifactMedium,
    KnowledgeArtifact,
    KnowledgeRegistry,
)


# ---------------------------------------------------------------------------
# Helpers de sérialisation
# ---------------------------------------------------------------------------

_MEDIUM_LABELS = {
    ArtifactMedium.PARCHMENT: "parchemin",
    ArtifactMedium.TABLET: "tablette d'argile",
    ArtifactMedium.INSCRIPTION: "inscription lapidaire",
    ArtifactMedium.CERAMIC: "tablette céramique",
}


def _agent_pos(sim, row: int) -> Optional[tuple]:
    """Retourne (x, y, z) pour l'agent `row` ou None si invalide."""
    a = getattr(sim, "agents", None)
    if a is None:
        return None
    n = getattr(a, "n_active", 0)
    if row < 0 or row >= n:
        return None
    if not bool(a.alive[row]):
        return None
    p = a.pos[row]
    return float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0


def _agent_lex_vector(sim, row: int) -> Optional[np.ndarray]:
    a = getattr(sim, "agents", None)
    if a is None or getattr(a, "lexicon", None) is None:
        return None
    n = getattr(a, "n_active", 0)
    if row < 0 or row >= n:
        return None
    return a.lexicon[row]


def _artifact_to_dict(ka: KnowledgeArtifact, sim=None) -> dict:
    d = {
        "artifact_id": int(ka.artifact_id),
        "pos": [float(ka.pos[0]), float(ka.pos[1]),
                float(ka.pos[2]) if len(ka.pos) > 2 else 0.0],
        "medium_id": int(ka.medium),
        "medium": _MEDIUM_LABELS.get(ka.medium, str(ka.medium)),
        "durability": float(ka.durability),
        "kind_id": int(ka.kind),
        "kind": ka.kind.name.lower() if hasattr(ka.kind, "name") else str(ka.kind),
        "author_row": int(ka.author_row),
        "created_tick": int(ka.created_tick),
        "times_read": int(ka.times_read),
    }
    if ka.tech_encoded is not None:
        d["tech_encoded"] = int(ka.tech_encoded)
    return d


# ---------------------------------------------------------------------------
# Handlers logiques (testables sans HTTP)
# ---------------------------------------------------------------------------

def audio_snapshot(sim, sound_field: SoundField, qs: Dict[str, str]) -> dict:
    """Retourne {utterances: [...]} audibles depuis la position d'écoute."""
    lx = qs.get("listener_x"); ly = qs.get("listener_y")
    listener_row = qs.get("listener_row")
    x = y = None
    row_used: Optional[int] = None
    if listener_row not in (None, ""):
        try:
            row_used = int(listener_row)
        except ValueError:
            row_used = None
        if row_used is not None:
            pos = _agent_pos(sim, row_used)
            if pos is not None:
                x, y = pos[0], pos[1]
    if x is None and lx not in (None, "") and ly not in (None, ""):
        try:
            x = float(lx); y = float(ly)
        except ValueError:
            x = y = None
    if x is None or y is None:
        return {"utterances": [], "listener": None,
                "error": "listener position missing"}

    out = []
    for u, perceived in sound_field.audible_at(x, y, AUDIBILITY_THRESHOLD_DB):
        lex_vec = _agent_lex_vector(sim, u.speaker_row)
        out.append(utterance_to_dict(u, perceived_db=perceived,
                                     lex_vector=lex_vec))
    return {
        "utterances": out,
        "listener": {"x": x, "y": y, "row": row_used},
        "tick": int(getattr(sim, "tick", 0)),
    }


def audio_history(sim, sound_field: SoundField, qs: Dict[str, str]) -> dict:
    """Retourne les n dernières utterances proches de l'agent `row`."""
    try:
        row = int(qs.get("row", "-1"))
    except ValueError:
        row = -1
    try:
        n = int(qs.get("n", "30"))
    except ValueError:
        n = 30
    n = max(1, min(n, 200))
    pos = _agent_pos(sim, row)
    if pos is None:
        return {"utterances": [], "error": "invalid row"}

    out = []
    for u in sound_field.history_around(pos[0], pos[1], max_distance_m=30.0, n=n):
        lex_vec = _agent_lex_vector(sim, u.speaker_row)
        out.append(utterance_to_dict(u, lex_vector=lex_vec))
    return {
        "utterances": out,
        "row": row,
        "listener_pos": [pos[0], pos[1]],
        "tick": int(getattr(sim, "tick", 0)),
    }


def artifacts_in_bbox(sim, knowledge_registry: KnowledgeRegistry,
                      qs: Dict[str, str]) -> dict:
    """Retourne les KnowledgeArtifacts intersectant la bbox demandée."""
    try:
        xmin = float(qs.get("xmin", "-1e9"))
        ymin = float(qs.get("ymin", "-1e9"))
        xmax = float(qs.get("xmax", "1e9"))
        ymax = float(qs.get("ymax", "1e9"))
    except ValueError:
        return {"artifacts": [], "error": "invalid bbox"}

    out = []
    for ka in knowledge_registry.artifacts.values():
        if ka.is_destroyed():
            continue
        x, y = float(ka.pos[0]), float(ka.pos[1])
        if xmin <= x <= xmax and ymin <= y <= ymax:
            out.append(_artifact_to_dict(ka, sim))
    return {"artifacts": out, "count": len(out),
            "tick": int(getattr(sim, "tick", 0))}


# ---------------------------------------------------------------------------
# Enregistrement par monkey-patch
# ---------------------------------------------------------------------------

def register_audio_endpoints(handler_class, sim, sound_field: SoundField,
                             knowledge_registry: KnowledgeRegistry) -> None:
    """Patche `handler_class.do_GET` pour intercepter les routes audio.

    Idempotent : un second appel remplace les références sim / sound_field /
    knowledge_registry sans empiler les wrappers.
    """
    handler_class._sim_audio = sim
    handler_class._sound_field = sound_field
    handler_class._knowledge_registry = knowledge_registry

    if getattr(handler_class, "_audio_patched", False):
        return
    handler_class._audio_patched = True

    original_do_get = handler_class.do_GET

    def patched_do_get(self):
        path = self.path.split("?", 1)[0]
        try:
            if path == "/api/audio":
                payload = audio_snapshot(self._sim_audio, self._sound_field,
                                         self._qs())
                self._json(200, payload); return
            if path == "/api/audio/history":
                payload = audio_history(self._sim_audio, self._sound_field,
                                        self._qs())
                self._json(200, payload); return
            if path == "/api/artifacts":
                payload = artifacts_in_bbox(self._sim_audio,
                                            self._knowledge_registry, self._qs())
                self._json(200, payload); return
            if path == "/static/audio_overlay.js":
                self._serve_file("audio_overlay.js",
                                 content_type="application/javascript; charset=utf-8")
                return
        except Exception as exc:
            body = json.dumps({"error": str(exc)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return original_do_get(self)

    handler_class.do_GET = patched_do_get
