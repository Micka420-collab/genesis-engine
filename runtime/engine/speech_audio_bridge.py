"""Pont vocalize → SoundField — écoute des agents en Earth Console.

Les événements ``vocalize`` (cognition / 5cd) sont convertis en
:class:`~engine.communication.Utterance` audibles via ``/api/audio``.
Le lexique 16-D de chaque locuteur dérive légèrement à chaque parole
(langage émergent par culture).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

PIPELINE_LAYER = "Genesis-L2 Cognition"
WORLD_MODEL_CAPABILITY = "paper-L3 Communicator"

from engine.communication import (
    KIND_LABELS,
    SoundField,
    SpeechVolume,
    UtteranceKind,
    lexicon_to_phonemes,
)
from engine.knowledge_artifacts import KnowledgeRegistry


def _infer_kind(sim, row: int, lex_sig: int) -> UtteranceKind:
    """Intent de parole dérivé de l'état agent (pas de script narratif)."""
    agents = sim.agents
    kinds = list(UtteranceKind)
    base = int(lex_sig) % len(kinds)
    try:
        act = int(agents.action[row])
        from engine.agent import ActionKind
        if act == int(ActionKind.BUILD):
            return UtteranceKind.TEACH
        if act == int(ActionKind.FORAGE):
            return UtteranceKind.REQUEST
        if act == int(ActionKind.FIGHT):
            return UtteranceKind.WARNING
    except Exception:
        pass
    if hasattr(agents, "stress"):
        try:
            if float(agents.stress[row]) > 0.7:
                return UtteranceKind.LAMENT
        except Exception:
            pass
    if hasattr(agents, "emotions"):
        try:
            emo = int(np.argmax(agents.emotions[row]))
            if emo == 0:
                return UtteranceKind.GREETING
            if emo >= 4:
                return UtteranceKind.WARNING
        except Exception:
            pass
    return kinds[base]


def _drift_lexicon(sim, row: int, target: Optional[int], lex_sig: int) -> None:
    """Légère dérive du vecteur lexical (proto-langage par culture)."""
    agents = sim.agents
    if getattr(agents, "lexicon", None) is None:
        return
    rng = np.random.default_rng(
        (int(lex_sig) * 7919 + int(sim.tick) * 17 + int(row) * 31) & 0xFFFFFFFF
    )
    delta = (rng.random(16, dtype=np.float32) - 0.5) * 0.04
    agents.lexicon[row] = np.clip(agents.lexicon[row] + delta, 0.0, 1.0)
    if target is not None and 0 <= target < agents.n_active:
        blend = 0.012
        agents.lexicon[row] = np.clip(
            agents.lexicon[row] * (1.0 - blend) + agents.lexicon[target] * blend,
            0.0, 1.0,
        )


def emit_vocalize(sim, tick: int, agents, raw: dict) -> None:
    """Convertit un raw_event ``vocalize`` en utterance audible."""
    sf: Optional[SoundField] = getattr(sim, "sound_field", None)
    if sf is None:
        return
    row = int(raw.get("from", -1))
    target = raw.get("to")
    tgt = int(target) if target is not None else None
    if row < 0 or row >= agents.n_active or not bool(agents.alive[row]):
        return
    lex_sig = int(raw.get("lex_sig", (row * 17 + tick) & 0xFFFF))
    _drift_lexicon(sim, row, tgt, lex_sig)
    kind = _infer_kind(sim, row, lex_sig)
    vol = SpeechVolume.SPEAK
    if hasattr(agents, "stress"):
        try:
            if float(agents.stress[row]) > 0.85:
                vol = SpeechVolume.SHOUT
        except Exception:
            pass
    pos = tuple(float(x) for x in agents.pos[row].tolist())
    payload = {"to_row": tgt, "lex_sig": lex_sig}
    if tgt is not None and 0 <= tgt < agents.n_active:
        payload["target_name_hint"] = int(tgt)
    sf.emit(
        speaker_row=row,
        pos=pos,
        tick=int(tick),
        kind=kind,
        volume=vol,
        lex_sig=lex_sig,
        payload=payload,
        ttl_ticks=6,
    )


def languages_snapshot(sim) -> Dict[str, Any]:
    """Lexiques moyens par culture — proto-langages émergents."""
    agents = sim.agents
    n = int(getattr(agents, "n_active", 0))
    buckets: Dict[int, List[np.ndarray]] = {}
    for row in range(n):
        if not bool(agents.alive[row]):
            continue
        cid = int(agents.culture_id[row]) if hasattr(agents, "culture_id") else 0
        if getattr(agents, "lexicon", None) is None:
            continue
        buckets.setdefault(cid, []).append(agents.lexicon[row].copy())
    cultures: List[Dict[str, Any]] = []
    for cid, vecs in sorted(buckets.items()):
        mean_lex = np.mean(np.stack(vecs, axis=0), axis=0)
        cultures.append({
            "culture_id": int(cid),
            "speakers": len(vecs),
            "phonemes": lexicon_to_phonemes(mean_lex, n_syllables=4),
            "lexicon_mean": [round(float(x), 4) for x in mean_lex[:8]],
        })
    sf = getattr(sim, "sound_field", None)
    live = len(sf.utterances) if sf else 0
    hist = len(sf.keep_history) if sf else 0
    return {
        "tick": int(getattr(sim, "tick", 0)),
        "n_cultures": len(cultures),
        "cultures": cultures,
        "live_utterances": live,
        "history_utterances": hist,
        "kind_labels": {int(k): v for k, v in KIND_LABELS.items()},
    }


def install_speech_audio(sim) -> Dict[str, Any]:
    """Idempotent — branche vocalize → sound_field + expire TTL."""
    if getattr(sim, "_speech_audio_installed", False):
        return {"skipped": True}
    sf = getattr(sim, "sound_field", None)
    if sf is None:
        sf = SoundField()
        sim.sound_field = sf
    if not hasattr(sim, "knowledge_registry"):
        sim.knowledge_registry = KnowledgeRegistry()

    ann = sim.annalist
    _orig_record = ann.record_tick

    def _patched_record(tick, agents, births, deaths, raw_events, foundings=None):
        for raw in raw_events or []:
            if raw.get("kind") == "vocalize":
                emit_vocalize(sim, tick, agents, raw)
        sf.tick(int(tick))
        return _orig_record(tick, agents, births, deaths, raw_events, foundings)

    ann.record_tick = _patched_record  # type: ignore[method-assign]
    sim._speech_audio_installed = True
    return {"speech_audio": True, "sound_field": True}


__all__ = [
    "emit_vocalize",
    "install_speech_audio",
    "languages_snapshot",
]
