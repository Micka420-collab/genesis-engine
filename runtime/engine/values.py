"""Valeurs morales + libre arbitre.

Chaque agent possède un vecteur de 7 valeurs (survie, famille, curiosité,
communauté, héritage, liberté, domination). Ces valeurs sont héritées de
ses parents avec mutation, modulent les décisions au-delà de l'utilité
réflexe, et peuvent évoluer au cours de la vie de l'agent en fonction de
ses expériences.

C'est le mécanisme qui permet à deux agents ayant des drives identiques
d'agir différemment — la couche de "libre arbitre" du Genesis Engine.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Tuple

import numpy as np


class ValueDim(IntEnum):
    SURVIVAL = 0      # ne pas mourir
    FAMILY = 1        # protéger / aider parents et enfants
    CURIOSITY = 2     # explorer / apprendre / inventer
    COMMUNITY = 3     # contribuer au groupe / coopérer
    LEGACY = 4        # transmettre / construire pour l'avenir
    FREEDOM = 5       # autonomie / refus de soumission
    DOMINANCE = 6     # contrôler les autres / hiérarchie


VALUE_NAMES = ["survival", "family", "curiosity", "community",
               "legacy", "freedom", "dominance"]


def value_bias_for_action(values: np.ndarray, action_name: str) -> float:
    """Retourne un facteur multiplicatif [0.5 .. 1.5] sur la confiance d'une action.

    Permet aux valeurs de biaiser le choix sans le déterminer entièrement.
    """
    v = values
    action_name = action_name.lower()
    if action_name in ("eat", "drink", "sleep", "seek_shelter", "flee"):
        return 0.6 + 0.9 * float(v[ValueDim.SURVIVAL])
    if action_name in ("share", "speak"):
        return 0.5 + 1.0 * float(v[ValueDim.COMMUNITY])
    if action_name == "mate":
        return 0.5 + 1.0 * float(v[ValueDim.FAMILY])
    if action_name == "fight":
        return 0.5 + 1.0 * float(v[ValueDim.DOMINANCE])
    if action_name in ("explore", "build", "invent", "craft"):
        return 0.5 + 1.0 * float(v[ValueDim.CURIOSITY]) + 0.3 * float(v[ValueDim.LEGACY])
    if action_name == "idle":
        return 0.8 + 0.4 * (1.0 - float(v[ValueDim.LEGACY]))   # legacy → not idle
    return 1.0


def free_will_override(values: np.ndarray, drive_strength: float,
                       situation: str, rng) -> Tuple[bool, str]:
    """Décide si l'agent ignore son utilité court terme au profit d'une valeur.

    Retourne (override?, raison) ; si True, l'appelant doit ignorer le
    pick utilitaire et choisir une action alignée avec la valeur dominante.

    Probabilité d'override = (1 - drive_strength) × valeur_dominante × 0.10.
    Donc on ne triche pas sur la survie quand elle est critique.
    """
    if drive_strength >= 0.85:
        return False, ""  # critical drive → no override
    dominant = int(np.argmax(values))
    strength = float(values[dominant])
    if strength < 0.18:
        return False, ""  # weak values don't override
    p = (1.0 - drive_strength) * strength * 0.10
    if rng.random() < p:
        return True, VALUE_NAMES[dominant]
    return False, ""


def evolve_value(values: np.ndarray, event_kind: str, magnitude: float = 0.01) -> None:
    """Lifetime adaptation: an event nudges the agent's value vector.

    e.g. losing a child → +family, +legacy ; being attacked → +survival, +dominance ;
    achieving an invention → +curiosity, +legacy.
    """
    delta = np.zeros_like(values)
    if event_kind == "lost_kin":
        delta[ValueDim.FAMILY] += magnitude
        delta[ValueDim.LEGACY] += magnitude
    elif event_kind == "attacked":
        delta[ValueDim.SURVIVAL] += magnitude
        delta[ValueDim.DOMINANCE] += magnitude * 0.5
    elif event_kind == "shared_with":
        delta[ValueDim.COMMUNITY] += magnitude
    elif event_kind == "betrayed":
        delta[ValueDim.FREEDOM] += magnitude
        delta[ValueDim.COMMUNITY] -= magnitude * 0.5
    elif event_kind == "invented":
        delta[ValueDim.CURIOSITY] += magnitude
        delta[ValueDim.LEGACY] += magnitude * 0.5
    elif event_kind == "rescued":
        delta[ValueDim.COMMUNITY] += magnitude
        delta[ValueDim.SURVIVAL] += magnitude * 0.3
    new = values + delta
    new = np.clip(new, 0.0, 1.0)
    s = new.sum()
    if s > 1e-6:
        new = new / s
    values[:] = new
