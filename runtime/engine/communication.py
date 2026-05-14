"""Parole, écoute, propagation sonore réaliste.

Chaque acte de parole (Utterance) est émis à une position, avec une intensité
en dB. L'audibilité décroît selon la loi inverse du carré : 6 dB par
doublement de distance. Sous le seuil de 10 dB l'utterance n'est plus
audible.

L'utilisateur (god avatar) ou un agent sélectionné peut "écouter" — le
serveur retourne les utterances audibles à sa position.

Le contenu d'une utterance est structuré (greeting / warning / teach /
request / name / myth / agreement / refusal) plutôt qu'en langage naturel,
parce que les agents n'ont pas encore de cognition LLM. La signature
lexicale (16-D) est convertie en pseudo-phonèmes pour affichage humain.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Intensités calées sur la réalité (Wikipedia: Sound pressure level)
# ---------------------------------------------------------------------------

WHISPER_DB = 32.0     # whisper at 1 m
SPEAK_DB = 60.0       # normal conversation at 1 m
SHOUT_DB = 85.0       # shouting at 1 m
REFERENCE_DISTANCE_M = 1.0
AUDIBILITY_THRESHOLD_DB = 32.0  # outdoor ambient noise floor    # below this we cannot hear the utterance
HEAR_RADIUS_HARD_CAP_M = 100.0    # never propagate beyond this


class UtteranceKind(IntEnum):
    GREETING = 0     # bonjour / salutation
    WARNING = 1      # alerte (prédateur, danger)
    TEACH = 2        # transmission de savoir
    REQUEST = 3      # demande d'aide / nourriture
    NAME = 4         # appel par nom (de l'autre ou de soi)
    MYTH = 5         # narration / récit
    AGREEMENT = 6    # acquiescement
    REFUSAL = 7      # refus
    QUESTION = 8     # question
    LAMENT = 9       # plainte / chagrin
    SONG = 10        # chant rituel
    PRAYER = 11      # prière (apparait après MIRACLE_WITNESSED)


class SpeechVolume(IntEnum):
    WHISPER = 0
    SPEAK = 1
    SHOUT = 2


VOLUME_DB = {
    SpeechVolume.WHISPER: WHISPER_DB,
    SpeechVolume.SPEAK: SPEAK_DB,
    SpeechVolume.SHOUT: SHOUT_DB,
}


@dataclass
class Utterance:
    """Acte de parole émis à un instant donné."""
    utterance_id: int
    speaker_row: int
    pos: Tuple[float, float, float]
    tick: int
    kind: UtteranceKind
    volume: SpeechVolume
    intensity_db_at_ref: float       # niveau à 1 m
    lex_sig: int                     # signature phonologique du locuteur
    payload: dict = field(default_factory=dict)  # données spécifiques au kind
    ttl_ticks: int = 4               # combien de ticks l'utterance reste "live"


def propagated_intensity_db(intensity_at_ref: float, distance_m: float) -> float:
    """Loi de propagation : -6 dB par doublement (inverse du carré)."""
    if distance_m <= REFERENCE_DISTANCE_M:
        return intensity_at_ref
    return intensity_at_ref - 20.0 * math.log10(distance_m / REFERENCE_DISTANCE_M)


def hearing_radius_for(intensity_at_ref: float) -> float:
    """Distance max où l'utterance est audible (intensité >= seuil)."""
    db_drop = intensity_at_ref - AUDIBILITY_THRESHOLD_DB
    if db_drop <= 0:
        return 0.0
    r = REFERENCE_DISTANCE_M * (10.0 ** (db_drop / 20.0))
    return min(r, HEAR_RADIUS_HARD_CAP_M)


@dataclass
class SoundField:
    """Champ sonore global : queue d'utterances avec expiration par TTL."""
    utterances: List[Utterance] = field(default_factory=list)
    _next_id: int = 1
    keep_history: List[Utterance] = field(default_factory=list)  # cap'd
    history_cap: int = 4096

    def emit(self, speaker_row: int, pos: Tuple[float, float, float],
             tick: int, kind: UtteranceKind, volume: SpeechVolume,
             lex_sig: int, payload: Optional[dict] = None,
             ttl_ticks: int = 4) -> Utterance:
        u = Utterance(
            utterance_id=self._next_id, speaker_row=speaker_row, pos=pos,
            tick=tick, kind=kind, volume=volume,
            intensity_db_at_ref=VOLUME_DB[volume],
            lex_sig=int(lex_sig), payload=payload or {}, ttl_ticks=ttl_ticks)
        self._next_id += 1
        self.utterances.append(u)
        return u

    def tick(self, current_tick: int) -> None:
        """Expire les utterances arrivées en fin de TTL."""
        alive = []
        for u in self.utterances:
            if current_tick - u.tick <= u.ttl_ticks:
                alive.append(u)
            else:
                # Move to history (bounded)
                self.keep_history.append(u)
                if len(self.keep_history) > self.history_cap:
                    self.keep_history.pop(0)
        self.utterances = alive

    def audible_at(self, x: float, y: float,
                   listener_hearing_db: float = AUDIBILITY_THRESHOLD_DB
                   ) -> List[Tuple[Utterance, float]]:
        """Retourne les utterances audibles à (x, y) avec leur dB perçus."""
        out: List[Tuple[Utterance, float]] = []
        for u in self.utterances:
            dx = u.pos[0] - x; dy = u.pos[1] - y
            d = math.sqrt(dx * dx + dy * dy)
            perceived = propagated_intensity_db(u.intensity_db_at_ref, d)
            if perceived >= listener_hearing_db:
                out.append((u, perceived))
        out.sort(key=lambda t: -t[1])
        return out

    def history_around(self, x: float, y: float, max_distance_m: float = 30.0,
                       n: int = 30) -> List[Utterance]:
        """Récupère les n dernières utterances proches du point (x, y)."""
        out: List[Utterance] = []
        for u in reversed(self.keep_history):
            dx = u.pos[0] - x; dy = u.pos[1] - y
            if dx * dx + dy * dy <= max_distance_m * max_distance_m:
                out.append(u)
                if len(out) >= n:
                    break
        return out


# ---------------------------------------------------------------------------
# Encodage phonologique : 16-D lexicon -> pseudo-phonèmes pour affichage humain
# ---------------------------------------------------------------------------

# Voyelles et consonnes simples calées sur PHOIBLE (les phonèmes les plus
# fréquents toutes langues confondues).
VOWELS = ["a", "i", "u", "e", "o", "ə"]
CONSONANTS = ["k", "t", "n", "m", "p", "s", "l", "r", "h", "j", "w", "ŋ"]


def lexicon_to_phonemes(lex_vector: np.ndarray, n_syllables: int = 3) -> str:
    """Convertit un vecteur lexical en syllabes prononçables pour affichage."""
    arr = np.clip(lex_vector, 0.0, 1.0)
    sylls = []
    for s in range(n_syllables):
        idx = s * 4
        # Consonne d'attaque
        c_idx = int(arr[idx % len(arr)] * len(CONSONANTS)) % len(CONSONANTS)
        # Voyelle
        v_idx = int(arr[(idx + 1) % len(arr)] * len(VOWELS)) % len(VOWELS)
        sylls.append(CONSONANTS[c_idx] + VOWELS[v_idx])
    return "".join(sylls)


# ---------------------------------------------------------------------------
# Helpers pour le tick loop
# ---------------------------------------------------------------------------

KIND_LABELS = {
    UtteranceKind.GREETING: "salutation",
    UtteranceKind.WARNING: "alerte",
    UtteranceKind.TEACH: "enseignement",
    UtteranceKind.REQUEST: "demande",
    UtteranceKind.NAME: "appel",
    UtteranceKind.MYTH: "récit",
    UtteranceKind.AGREEMENT: "accord",
    UtteranceKind.REFUSAL: "refus",
    UtteranceKind.QUESTION: "question",
    UtteranceKind.LAMENT: "plainte",
    UtteranceKind.SONG: "chant",
    UtteranceKind.PRAYER: "prière",
}


def utterance_to_dict(u: Utterance, perceived_db: Optional[float] = None,
                      lex_vector: Optional[np.ndarray] = None) -> dict:
    """Pour exposition JSON via /api/audio."""
    d = {
        "utterance_id": u.utterance_id,
        "speaker_row": u.speaker_row,
        "pos": list(u.pos),
        "tick": u.tick,
        "kind": KIND_LABELS.get(u.kind, str(u.kind)),
        "kind_id": int(u.kind),
        "volume": int(u.volume),
        "intensity_db": float(u.intensity_db_at_ref),
        "payload": u.payload,
    }
    if perceived_db is not None:
        d["perceived_db"] = float(perceived_db)
    if lex_vector is not None:
        d["phonemes"] = lexicon_to_phonemes(lex_vector)
    return d
