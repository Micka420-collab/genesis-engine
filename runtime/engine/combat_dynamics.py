"""Genesis Engine — Wave 38 combat dynamics + emergent weapons.

Resolves combat between agents using **weapons emerging from Wave 35
machines** (`engine.machine_emergence`) and inflicts realistic wounds
via **Wave 34 anatomy** (`engine.anatomy`).

Architecture émergente
----------------------

Aucune recipe "epée = X". Les armes sont **classifiées** depuis les
machines existantes par leur signature matérielle :

```
WeaponKind:
    UNARMED (default fallback)
    CLUB    : dominant=stone, ≥2 components, mass 5-30 kg     → BRUISE
    BLADE   : dominant=metal, ≥2 components, mass 0.5-3 kg    → CUT
    SPEAR   : wood + metal components, mass 1-5 kg            → CUT
    BOW     : wood-dominated, ≥3 components, mass 1-3 kg      → CUT (distant)
```

La classification se fait par **examination de la machine**, pas par
nom. Une culture nomme sa machine `malo`, l'autre `kura`, mais si
elles ont la même signature matérielle, c'est la même classe d'arme.

Résolution combat
-----------------

```
resolve_combat(sim, attacker_row, defender_row, rng):
    weapon_a = best_weapon_for_agent(sim, attacker_row)
    weapon_d = best_weapon_for_agent(sim, defender_row)

    hit_p_a = 0.6 × accuracy_a × (1 + 0.5×aggression_a)
    if rng_hit_a < hit_p_a:
        dmg_a_to_d = weapon_a.base_damage × (1 + 0.3×strength_a)
        body_part_struck = sample_part_by_weapon(weapon_a, rng)
        inflict_wound(defender, body_part_struck, weapon_a.wound_kind,
                      severity=dmg_a_to_d)

    hit_p_d = 0.4 × accuracy_d × (1 + 0.5×aggression_d)
    (defender riposte if alive)
        same logic, smaller bonus (defender disadvantage)

    polity_check (optional) : if same polity, no damage
```

Le système couple naturellement avec Wave 34 → wounds → bleeding →
death by hemorrhage si l'agent ne soigne pas.

Pas de mort instantanée. Pas de "HP". On utilise le système anatomique
réel : un combat brutal inflige des wounds qui peuvent saigner et tuer
sur des heures/jours, pas en 1 tick.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


# ---------------------------------------------------------------------------
# Weapon taxonomy
# ---------------------------------------------------------------------------

class WeaponKind(IntEnum):
    UNARMED = 0
    CLUB = 1
    BLADE = 2
    SPEAR = 3
    BOW = 4


N_WEAPON_KINDS = 5

WEAPON_KIND_NAMES = (
    "unarmed", "club", "blade", "spear", "bow",
)


@dataclass
class WeaponProfile:
    """Caractéristiques d'une arme classifiée depuis une machine."""
    machine_name: str
    kind: int                  # WeaponKind
    base_damage: float         # severity 0-1 par hit réussi
    primary_wound_kind: int    # WoundKind enum value
    accuracy: float            # multiplicateur de probabilité de hit [0.5, 1.5]
    typical_body_parts: Tuple[int, ...] = ()  # parts visées (poids égal)


# Damage profiles by weapon kind (calibrated brutally).
WEAPON_DAMAGE_TABLE = {
    int(WeaponKind.UNARMED): {
        "base_damage": 0.06,
        "primary_wound_kind": 1,   # BRUISE
        "accuracy": 0.7,
        "body_parts": (0, 1, 1, 4, 5),  # head + torso×2 + hands
    },
    int(WeaponKind.CLUB): {
        "base_damage": 0.22,
        "primary_wound_kind": 1,   # BRUISE
        "accuracy": 0.8,
        "body_parts": (0, 0, 1, 1, 2, 3),  # head×2 + torso×2 + arms
    },
    int(WeaponKind.BLADE): {
        "base_damage": 0.30,
        "primary_wound_kind": 0,   # CUT
        "accuracy": 0.9,
        "body_parts": (1, 1, 1, 2, 3, 4, 5),
    },
    int(WeaponKind.SPEAR): {
        "base_damage": 0.26,
        "primary_wound_kind": 0,   # CUT (piercing approximated as CUT)
        "accuracy": 1.0,
        "body_parts": (0, 1, 1, 1),   # head + torso heavily
    },
    int(WeaponKind.BOW): {
        "base_damage": 0.20,
        "primary_wound_kind": 0,   # CUT (arrow puncture)
        "accuracy": 0.85,
        "body_parts": (1, 1, 2, 3, 6, 7),  # torso + limbs (ranged spread)
    },
}


def _classify_machine_as_weapon(machine) -> int:
    """Heuristique : classer une machine selon son matériel dominant +
    masse + nombre de components + combinaison de matériaux présents.

    On examine d'abord les **combinaisons** (metal + wood → spear,
    indépendamment du dominant) avant les classifications mono-matériau.

    Retourne un WeaponKind value. Renvoie UNARMED pour les machines
    qui ne ressemblent à aucune arme connue.
    """
    try:
        dom = machine.dominant_material
        mass = float(machine.total_mass_kg)
        components = machine.components
        n_comp = len(components)
        materials_present = {
            getattr(c, "id_or_name", "") for c in components
            if getattr(c, "kind", "") == "material"
        }
    except AttributeError:
        return int(WeaponKind.UNARMED)

    # SPEAR : metal + wood combination (point + shaft), 2-3 components,
    # mass légère à moyenne. Cohérent avec spear / javelot / lance.
    if ("metal" in materials_present and "wood" in materials_present
            and 0.5 <= mass <= 6.0 and 2 <= n_comp <= 3):
        return int(WeaponKind.SPEAR)

    # BOW : wood-dominated, 3+ components, masse faible (corde + manche
    # + flèches).
    if dom == "wood" and n_comp >= 3 and 1.0 <= mass <= 3.0:
        return int(WeaponKind.BOW)

    # BLADE : metal-dominant, masse faible (épée, hache courte, couteau).
    if dom == "metal" and 0.3 <= mass <= 4.0:
        return int(WeaponKind.BLADE)

    # CLUB : stone-dominant OU wood-only lourd (massue, hache de pierre).
    if dom == "stone":
        return int(WeaponKind.CLUB)
    if dom == "wood":
        return int(WeaponKind.CLUB)

    # metal très lourd (>4 kg) → blade lourde mais on garde BLADE.
    if dom == "metal":
        return int(WeaponKind.BLADE)

    return int(WeaponKind.UNARMED)


def weapon_profile_from_machine(machine) -> WeaponProfile:
    """Construit un WeaponProfile depuis une Machine de Wave 35."""
    kind = _classify_machine_as_weapon(machine)
    spec = WEAPON_DAMAGE_TABLE[kind]
    return WeaponProfile(
        machine_name=getattr(machine, "machine_id", "?"),
        kind=kind,
        base_damage=float(spec["base_damage"]),
        primary_wound_kind=int(spec["primary_wound_kind"]),
        accuracy=float(spec["accuracy"]),
        typical_body_parts=tuple(int(p) for p in spec["body_parts"]),
    )


def unarmed_profile() -> WeaponProfile:
    """Profile par défaut quand l'agent n'a pas d'arme."""
    spec = WEAPON_DAMAGE_TABLE[int(WeaponKind.UNARMED)]
    return WeaponProfile(
        machine_name="(unarmed)",
        kind=int(WeaponKind.UNARMED),
        base_damage=float(spec["base_damage"]),
        primary_wound_kind=int(spec["primary_wound_kind"]),
        accuracy=float(spec["accuracy"]),
        typical_body_parts=tuple(int(p) for p in spec["body_parts"]),
    )


def best_weapon_for_agent(sim, row: int) -> WeaponProfile:
    """Cherche dans le MachineRegistry les machines accessibles à
    l'agent (= toutes celles de sa culture) et choisit la meilleure
    selon base_damage × accuracy.

    Pas de notion d'"inventaire d'arme" pour l'instant — toute machine
    inventée dans la culture est considérée comme accessible par tout
    membre. À raffiner Wave 38b si besoin.

    Renvoie ``unarmed_profile()`` si aucune machine n'est une arme.
    """
    state = getattr(sim, "_machine_state", None)
    if state is None:
        return unarmed_profile()
    registry = getattr(state, "registry", state)
    machines = list(getattr(registry, "machines", {}).values())
    if not machines:
        return unarmed_profile()

    # Determine agent's culture (lives on the per-agent SocialRelations).
    culture = 0
    try:
        culture = int(sim.agents.relations[row].culture_id)
    except (AttributeError, IndexError, TypeError):
        pass

    # Filter to machines invented in this culture (or all if culture lookup fails).
    candidates = [m for m in machines
                    if getattr(m, "culture_id", -1) == culture
                    or getattr(m, "culture_id", -1) == -1]
    if not candidates:
        candidates = machines

    best_profile = unarmed_profile()
    best_score = best_profile.base_damage * best_profile.accuracy
    for m in candidates:
        prof = weapon_profile_from_machine(m)
        score = prof.base_damage * prof.accuracy
        if score > best_score:
            best_score = score
            best_profile = prof
    return best_profile


# ---------------------------------------------------------------------------
# Combat resolution
# ---------------------------------------------------------------------------

@dataclass
class CombatExchange:
    """Result of one A→B (and optional B→A counter) combat exchange."""
    tick: int
    attacker_row: int
    defender_row: int
    attacker_weapon: WeaponProfile
    defender_weapon: WeaponProfile
    attacker_hit: bool = False
    defender_counter_hit: bool = False
    attacker_dealt_severity: float = 0.0
    defender_dealt_severity: float = 0.0
    attacker_body_part_struck: int = -1
    defender_body_part_struck: int = -1
    same_polity_skipped: bool = False


@dataclass
class CombatState:
    """Per-sim cumulative combat stats."""
    n_exchanges_total: int = 0
    n_hits_total: int = 0
    n_kills_via_bleed: int = 0
    n_same_polity_skipped: int = 0
    by_weapon: Dict[int, int] = field(default_factory=dict)


def _get_personality(sim, row: int, attr: str, default: float = 0.5) -> float:
    """Lit un trait Big-Five sur l'agent. Renvoie default si absent."""
    try:
        arr = getattr(sim.agents, attr, None)
        if arr is None:
            return default
        v = float(arr[row])
        return max(0.0, min(1.0, v))
    except (AttributeError, IndexError, TypeError, ValueError):
        return default


def _same_polity(sim, a: int, b: int) -> bool:
    """Optionnel : check si A et B sont dans la même polity (Wave 9c).

    Si polity n'est pas installé, renvoie False (combat autorisé).
    """
    state = getattr(sim, "_polity_state", None)
    if state is None:
        return False
    polity_of_row = getattr(state, "polity_of_row", None)
    if polity_of_row is None:
        return False
    try:
        pa = int(polity_of_row[a]) if a < len(polity_of_row) else -1
        pb = int(polity_of_row[b]) if b < len(polity_of_row) else -1
        return pa >= 0 and pa == pb
    except (TypeError, ValueError):
        return False


def resolve_combat(sim,
                     attacker_row: int,
                     defender_row: int,
                     *,
                     skip_same_polity: bool = True
                     ) -> CombatExchange:
    """Resolve one combat exchange between two agents.

    1. Picks the best weapon for each side from Wave 35 machine registry.
    2. Skips if both in same polity (Wave 9c) and skip_same_polity=True.
    3. Rolls attack hit via prf_rng. If hit, inflicts wound via anatomy.
    4. Defender counter-attacks (smaller hit chance).
    5. Returns CombatExchange diagnostic record.

    Pure function w.r.t. RNG : same (seed, tick, a, b) → same outcome.
    """
    weapon_a = best_weapon_for_agent(sim, attacker_row)
    weapon_d = best_weapon_for_agent(sim, defender_row)
    exchange = CombatExchange(
        tick=int(sim.tick),
        attacker_row=int(attacker_row),
        defender_row=int(defender_row),
        attacker_weapon=weapon_a,
        defender_weapon=weapon_d,
    )

    # Same polity skip.
    if skip_same_polity and _same_polity(sim, attacker_row, defender_row):
        exchange.same_polity_skipped = True
        return exchange

    # Both must be alive.
    try:
        if not (bool(sim.agents.alive[attacker_row])
                and bool(sim.agents.alive[defender_row])):
            return exchange
    except (AttributeError, IndexError):
        return exchange

    seed = int(sim.cfg.seed)
    tick = int(sim.tick)

    # Attacker rolls hit.
    agg_a = _get_personality(sim, attacker_row, "aggression", 0.5)
    str_a = _get_personality(sim, attacker_row, "strength", 0.5)
    rng_hit_a = prf_rng(seed, ["combat", "hit_a"],
                          [tick, attacker_row, defender_row])
    hit_p_a = 0.6 * weapon_a.accuracy * (1.0 + 0.5 * agg_a)
    if float(rng_hit_a.random()) < hit_p_a:
        exchange.attacker_hit = True
        # Damage = base × (1 + 0.3×strength) × randomness
        rng_dmg_a = prf_rng(seed, ["combat", "dmg_a"],
                              [tick, attacker_row, defender_row])
        dmg_a = (weapon_a.base_damage
                  * (1.0 + 0.3 * str_a)
                  * (0.6 + 0.8 * float(rng_dmg_a.random())))
        # Pick body part.
        if weapon_a.typical_body_parts:
            rng_part = prf_rng(seed, ["combat", "part_a"],
                                 [tick, attacker_row, defender_row])
            idx = int(rng_part.integers(0, len(weapon_a.typical_body_parts)))
            part = int(weapon_a.typical_body_parts[idx])
        else:
            part = 1  # torso
        exchange.attacker_dealt_severity = float(dmg_a)
        exchange.attacker_body_part_struck = part
        _apply_wound_to_anatomy(
            sim, defender_row, part, weapon_a.primary_wound_kind, dmg_a)

    # Defender counter (smaller hit chance, only if alive).
    try:
        if not bool(sim.agents.alive[defender_row]):
            return exchange
    except (AttributeError, IndexError):
        return exchange
    agg_d = _get_personality(sim, defender_row, "aggression", 0.5)
    str_d = _get_personality(sim, defender_row, "strength", 0.5)
    rng_hit_d = prf_rng(seed, ["combat", "hit_d"],
                          [tick, attacker_row, defender_row])
    hit_p_d = 0.4 * weapon_d.accuracy * (1.0 + 0.5 * agg_d)
    if float(rng_hit_d.random()) < hit_p_d:
        exchange.defender_counter_hit = True
        rng_dmg_d = prf_rng(seed, ["combat", "dmg_d"],
                              [tick, attacker_row, defender_row])
        dmg_d = (weapon_d.base_damage
                  * (1.0 + 0.3 * str_d)
                  * (0.6 + 0.8 * float(rng_dmg_d.random())))
        if weapon_d.typical_body_parts:
            rng_part = prf_rng(seed, ["combat", "part_d"],
                                 [tick, attacker_row, defender_row])
            idx = int(rng_part.integers(0, len(weapon_d.typical_body_parts)))
            part = int(weapon_d.typical_body_parts[idx])
        else:
            part = 1
        exchange.defender_dealt_severity = float(dmg_d)
        exchange.defender_body_part_struck = part
        _apply_wound_to_anatomy(
            sim, attacker_row, part, weapon_d.primary_wound_kind, dmg_d)

    return exchange


def _apply_wound_to_anatomy(sim, row: int, part: int, kind: int,
                              severity: float) -> None:
    """Inflict a wound via engine.anatomy if installed, else no-op."""
    try:
        from engine.anatomy import inflict_wound
        fields = getattr(sim, "_anatomy_fields", None)
        if fields is None:
            return
        inflict_wound(fields, row, part, kind, severity)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sim integration (wrapper on apply_decision for FIGHT)
# ---------------------------------------------------------------------------

_COMBAT_DISPATCH: Dict[int, Tuple[object, CombatState]] = {}


def _combat_global_wrapper(agents, row, decision, streamer, tick):
    """Stacked wrapper on apply_decision.

    Hooks ActionKind.FIGHT : the decision must have `target_row`
    set to an integer (defender index). When the inner handler runs
    FIGHT, the wrapper intercepts to call resolve_combat instead of
    (or in addition to) the legacy hit logic.
    """
    import engine.cognition as _cog
    from engine.agent import ActionKind

    inner = getattr(_cog, "_combat_inner_apply_decision", None)
    if inner is None:
        return None
    pair = _COMBAT_DISPATCH.get(id(agents))
    if pair is None:
        return inner(agents, row, decision, streamer, tick)
    sim, state = pair

    # Delegate first (lets other modules + native handler do their work).
    events = inner(agents, row, decision, streamer, tick)

    if int(decision.action) == int(ActionKind.FIGHT):
        try:
            target = getattr(decision, "target_row", -1)
            if target is None:
                target = -1
            target = int(target)
            if 0 <= target < sim.agents.n_active and target != row:
                ex = resolve_combat(sim, row, target,
                                      skip_same_polity=False)
                state.n_exchanges_total += 1
                if ex.attacker_hit:
                    state.n_hits_total += 1
                if ex.defender_counter_hit:
                    state.n_hits_total += 1
                if ex.same_polity_skipped:
                    state.n_same_polity_skipped += 1
                state.by_weapon[int(ex.attacker_weapon.kind)] = (
                    state.by_weapon.get(int(ex.attacker_weapon.kind), 0) + 1)
        except Exception:
            pass

    return events


def install_combat_dynamics(sim) -> CombatState:
    """Idempotent installer. Stacks wrapper above apply_decision."""
    state: Optional[CombatState] = getattr(sim, "_combat_state", None)
    if state is None:
        state = CombatState()
        sim._combat_state = state
    _COMBAT_DISPATCH[id(sim.agents)] = (sim, state)

    import engine.cognition as _cog
    import engine.sim as _sim_mod
    if getattr(_cog, "_combat_inner_apply_decision", None) is None:
        _cog._combat_inner_apply_decision = _cog.apply_decision
        _cog.apply_decision = _combat_global_wrapper
        if hasattr(_sim_mod, "apply_decision"):
            _sim_mod.apply_decision = _combat_global_wrapper
    return state


def uninstall_combat_dynamics(sim) -> bool:
    """Restore previous apply_decision and detach state."""
    import engine.cognition as _cog
    import engine.sim as _sim_mod
    _COMBAT_DISPATCH.pop(id(sim.agents), None)
    inner = getattr(_cog, "_combat_inner_apply_decision", None)
    if inner is None:
        return False
    _cog.apply_decision = inner
    _cog._combat_inner_apply_decision = None
    if hasattr(_sim_mod, "apply_decision"):
        _sim_mod.apply_decision = inner
    if hasattr(sim, "_combat_state"):
        delattr(sim, "_combat_state")
    return True


def combat_state(sim) -> Dict[str, object]:
    """Diagnostic dict."""
    state: Optional[CombatState] = getattr(sim, "_combat_state", None)
    if state is None:
        return {"installed": False}
    return {
        "installed": True,
        "n_exchanges_total": state.n_exchanges_total,
        "n_hits_total": state.n_hits_total,
        "n_same_polity_skipped": state.n_same_polity_skipped,
        "by_weapon_kind": {WEAPON_KIND_NAMES[k]: c
                             for k, c in state.by_weapon.items() if c > 0},
    }


__all__ = [
    "WeaponKind", "N_WEAPON_KINDS", "WEAPON_KIND_NAMES",
    "WeaponProfile", "WEAPON_DAMAGE_TABLE",
    "CombatExchange", "CombatState",
    "weapon_profile_from_machine", "unarmed_profile",
    "best_weapon_for_agent",
    "resolve_combat",
    "install_combat_dynamics", "uninstall_combat_dynamics",
    "combat_state",
]
