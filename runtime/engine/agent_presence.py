"""Présence humaine — posture, démarche, outil (visuel + API).

Les agents ne sont pas des points : état dérivé de action, vitesse, drives
pour le rendu « vrais humains » sans script civilisationnel.
"""
from __future__ import annotations

import math
from typing import Any, Dict

from engine.agent import ActionKind, DriveKind

# Postures exposées au client
POSTURE_IDLE = "idle"
POSTURE_WALK = "walk"
POSTURE_RUN = "run"
POSTURE_BUILD = "build"
POSTURE_SMELT = "smelt"
POSTURE_PLANT = "plant"
POSTURE_FORAGE = "forage"
POSTURE_CARRY = "carry"
POSTURE_REST = "rest"

# Teintes peau (culture → variation déterministe)
_SKIN_BASE = [
    (255, 220, 185),
    (235, 195, 160),
    (210, 170, 130),
    (185, 145, 110),
    (160, 120, 90),
]


def _skin_tone(culture_id: int, row: int) -> tuple[int, int, int]:
    i = (int(culture_id) * 3 + int(row)) % len(_SKIN_BASE)
    return _SKIN_BASE[i]


def human_presence(sim, row: int) -> Dict[str, Any]:
    """Snapshot présence pour un agent vivant."""
    a = sim.agents
    act = int(a.action[row]) if hasattr(a, "action") else 0
    vx = float(a.vel[row, 0])
    vy = float(a.vel[row, 1])
    speed = math.hypot(vx, vy)
    heading = math.atan2(vy, vx) if speed > 0.08 else 0.0

    hunger = float(a.hunger[row])
    thirst = float(a.thirst[row])
    thermal = float(a.thermal[row])
    fatigue = float(getattr(a, "fatigue", [0])[row]) if hasattr(a, "fatigue") else 0.0

    posture = POSTURE_IDLE
    tool = None
    activity = "observe"

    if act == int(ActionKind.BUILD):
        posture = POSTURE_BUILD
        tool = "hammer"
        activity = "build"
    elif act == int(ActionKind.SMELT):
        posture = POSTURE_SMELT
        tool = "fire"
        activity = "smelt"
    elif act == int(ActionKind.PLANT):
        posture = POSTURE_PLANT
        tool = "seed"
        activity = "plant"
    elif act == int(ActionKind.FORAGE) or act == int(ActionKind.EAT):
        posture = POSTURE_FORAGE
        tool = "hands"
        activity = "forage"
    elif act == int(ActionKind.SLEEP):
        posture = POSTURE_REST
        activity = "rest"
    elif act == int(ActionKind.WALK_TO) or act == int(ActionKind.EXPLORE):
        posture = POSTURE_RUN if speed > 1.8 else POSTURE_WALK
        activity = "walk"
    elif speed > 0.35:
        posture = POSTURE_WALK
        activity = "walk"
    elif hunger > 0.65 or thirst > 0.65:
        posture = POSTURE_CARRY
        activity = "need"
    elif thermal > 0.55:
        posture = POSTURE_REST
        activity = "cold"

    gait_phase = (int(sim.tick) * 0.15 + row * 0.31) % (2 * math.pi)
    cid = int(a.relations[row].culture_id)
    skin = _skin_tone(cid, row)

    return {
        "row": int(row),
        "posture": posture,
        "activity": activity,
        "tool": tool,
        "heading": round(heading, 4),
        "speed": round(speed, 3),
        "gait_phase": round(gait_phase, 4),
        "skin": list(skin),
        "culture": cid,
        "stress": round(max(hunger, thirst, thermal, fatigue), 3),
    }


def enrich_lite_agent(sim, agent_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Ajoute champs présence à un agent lite."""
    row = int(agent_dict.get("row", 0))
    if not sim.agents.alive[row]:
        return agent_dict
    pres = human_presence(sim, row)
    agent_dict["posture"] = pres["posture"]
    agent_dict["activity"] = pres["activity"]
    agent_dict["tool"] = pres["tool"]
    agent_dict["skin"] = pres["skin"]
    agent_dict["gait"] = pres["gait_phase"]
    if "heading" not in agent_dict and pres["heading"]:
        agent_dict["heading"] = pres["heading"]
    return agent_dict


__all__ = [
    "human_presence",
    "enrich_lite_agent",
    "POSTURE_BUILD",
    "POSTURE_WALK",
]
