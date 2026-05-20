"""Genesis Engine — Wave 35 emergent machine discovery.

**Règle invariante du projet** : rien n'est scripté. Les machines (roue,
levier, watermill, métier à tisser…) **émergent** d'une combinaison libre
de composants — artefacts pré-inventés (:mod:`engine.invention`) et masses
de matériau brut — par *fingerprinting déterministe*.

Pattern (calqué sur :mod:`engine.building_discovery`)
-----------------------------------------------------

  1. Un agent appelle :func:`try_assemble_machine` avec une liste de
     :class:`MachineComponent`. Aucune table de recettes : il choisit
     librement ce qu'il assemble.
  2. Le fingerprint est calculé :

         (n_components, dominant_material, mass_bucket,
          sorted(function_kinds))

     La fonction agrégée est l'union des ``Artifact.function`` portés par
     les composants de type ``'artifact'``, plus les éventuelles
     ``intended_function_kinds`` que l'agent vise.
  3. Si la culture connaît déjà ce fingerprint → reconnaissance (compte
     comme tentative, pas comme nouvelle invention).
  4. Sinon → **nouvelle machine** : nom auto-généré CVCV via
     :func:`engine.core.prf_rng`, keyé sur ``(seed, culture, fp_hash)``.
     Deux cultures isolées qui tombent sur le même fingerprint reçoivent
     des noms différents (Lascaux/Altamira).
  5. Test de stabilité statique simplifié : ratio masse/footprint vs.
     un seuil conservateur. Le ``Machine.is_static_stable`` est posé en
     conséquence ; la machine est enregistrée même si instable, mais sa
     fonction effective sera dégradée (réservé Wave 36+).

Ce que ce module ne fait PAS
----------------------------
* Il **n'énumère** pas de recettes (wheel = ..., lever = ...).
* Il **ne sait pas** ce qu'est une roue ; il sait juste que telle
  composition a un fingerprint, et qu'on lui donne un nom.
* Il ne wrappe **pas** ``sim.step`` : la découverte de machines est
  ``event-driven``, déclenchée par la cognition (Wave 36 wiring).

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"``
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"``
"""
from __future__ import annotations

# Taxonomy — see ADR-0005 (capability axes).
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from engine.core import prf_rng
from engine.invention import Artifact, FunctionKind, InventionRegistry


# ---------------------------------------------------------------------------
# Mass-bucket discretization
# ---------------------------------------------------------------------------
# Six buckets : <0.5 kg, [0.5, 5), [5, 20), [20, 100), [100, 500), >=500.
# This is intentionally coarse so two cultures that assemble "approximately
# the same heavy stone-and-wood thing" land on the same fingerprint.
MASS_BUCKETS_KG: Tuple[float, ...] = (0.5, 5.0, 20.0, 100.0, 500.0)


def mass_bucket(mass_kg: float) -> int:
    """Discrete mass class index in [0..len(MASS_BUCKETS_KG)]."""
    if mass_kg <= 0.0:
        return 0
    for i, b in enumerate(MASS_BUCKETS_KG):
        if mass_kg < b:
            return i
    return len(MASS_BUCKETS_KG)


# Conservative kg/m² loading ceiling: above this, the assembly collapses.
# Stone over a 1 m² footprint at typical heights ≈ 200 kg/m² ; this 1000
# kg/m² ceiling lets normal machines through while rejecting "5 tons on
# the head of a pin".
STATIC_STRESS_CEILING_KG_PER_M2: float = 1000.0


# Minimum number of components to constitute a machine (vs. a single tool).
MIN_COMPONENTS_FOR_MACHINE: int = 2


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MachineComponent:
    """One ingredient of an assembly attempt.

    ``kind`` is either ``'artifact'`` (then ``id_or_name`` is the
    artifact id as a string, e.g. ``"7"``) or ``'material'`` (then
    ``id_or_name`` is the material name, e.g. ``"wood"``).
    """
    kind: str           # 'artifact' | 'material'
    id_or_name: str     # artifact_id (as str) or material name
    mass_kg: float


@dataclass
class Machine:
    """A composite machine that a culture has named."""
    machine_id: str                       # auto-generated CVCV name
    fingerprint: Tuple                    # deterministic signature
    components: List[MachineComponent]
    function_kinds: List[int]             # union of component functions
    dominant_material: str
    total_mass_kg: float
    culture_id: int
    inventor_row: int
    tick_created: int
    is_static_stable: bool


@dataclass
class MachineRegistry:
    """All machines discovered by every culture in the simulation."""
    machines: Dict[str, Machine] = field(default_factory=dict)
    machines_by_culture: Dict[int, List[str]] = field(default_factory=dict)
    # (culture_id, fingerprint) → machine_id : a fingerprint can map to
    # different names in different cultures.
    fingerprint_to_id: Dict[Tuple, str] = field(default_factory=dict)
    inventor_credit: Dict[int, int] = field(default_factory=dict)
    n_total_attempted: int = 0
    n_total_invented: int = 0


@dataclass
class MachineEmergenceState:
    """Attached to ``sim._machine_state`` (see :func:`install_machine_emergence`)."""
    registry: MachineRegistry = field(default_factory=MachineRegistry)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_culture(sim, row: int) -> int:
    """Return the agent's culture id, or 0 if not tracked."""
    cultures = getattr(sim.agents, "culture", None)
    if cultures is not None:
        try:
            return int(cultures[row])
        except Exception:
            return 0
    return 0


def _component_material_name(c: MachineComponent,
                              invention: Optional[InventionRegistry]) -> Optional[str]:
    """Best-effort: extract a textual material label from a component.

    * ``kind == 'material'`` → the material name is in ``id_or_name``.
    * ``kind == 'artifact'`` → look up the artifact in ``invention`` and
      use its ``primary_material.name``. Returns ``None`` if the artifact
      can't be found.
    """
    if c.kind == "material":
        return str(c.id_or_name)
    if c.kind == "artifact" and invention is not None:
        try:
            art_id = int(c.id_or_name)
        except (TypeError, ValueError):
            return None
        art = invention.artifacts.get(art_id)
        if art is None:
            return None
        # MATERIALS[primary_material].name lives in invention's universe.
        from engine.materials import MATERIALS
        m = MATERIALS.get(art.primary_material)
        return m.name if m is not None else None
    return None


def _component_functions(c: MachineComponent,
                          invention: Optional[InventionRegistry]) -> List[int]:
    """Return the function ids carried by an artifact component, or []."""
    if c.kind != "artifact" or invention is None:
        return []
    try:
        art_id = int(c.id_or_name)
    except (TypeError, ValueError):
        return []
    art = invention.artifacts.get(art_id)
    if art is None:
        return []
    return [int(art.function)]


# ---------------------------------------------------------------------------
# Fingerprint + auto-naming
# ---------------------------------------------------------------------------

def compute_machine_fingerprint(
    components: List[MachineComponent],
    function_kinds: List[int],
    invention: Optional[InventionRegistry] = None,
) -> Tuple:
    """Pure deterministic fingerprint.

    Shape::

        (n_components, dominant_material, mass_bucket, sorted_fn_tuple)

    The dominant material is the material name carrying the highest
    aggregate mass across the components. Mass bucket is the bucket of
    the *total* assembly mass. Function kinds are deduped and sorted.
    """
    n = len(components)
    # Aggregate mass per material name.
    mass_by_mat: Dict[str, float] = {}
    total_mass = 0.0
    for c in components:
        name = _component_material_name(c, invention) or "_unknown"
        mass_by_mat[name] = mass_by_mat.get(name, 0.0) + float(c.mass_kg)
        total_mass += float(c.mass_kg)
    if mass_by_mat:
        # Tie-break alphabetically for full determinism.
        dominant = sorted(mass_by_mat.items(),
                          key=lambda kv: (-kv[1], kv[0]))[0][0]
    else:
        dominant = "_unknown"
    bucket = mass_bucket(total_mass)
    fn_tuple = tuple(sorted(set(int(f) for f in function_kinds)))
    return (n, dominant, bucket, fn_tuple)


def auto_name_machine(
    world_seed: int,
    culture_id: int,
    fingerprint: Tuple,
) -> str:
    """Deterministic CVCV-CVCV pseudo-word naming via :func:`prf_rng`.

    Pattern: two consonant-vowel pairs (4 letters). Two cultures that
    stumble on the same fingerprint produce *different* names because
    ``culture_id`` participates in the PRF input.
    """
    # Repr() yields a deterministic string for tuple-of-primitives.
    fp_key = repr(fingerprint)
    rng = prf_rng(int(world_seed),
                  ["machine_emergence", "name", fp_key],
                  [int(culture_id)])
    consonants = "kmnprstvgdlbz"
    vowels = "aeiou"
    name = "".join((
        consonants[int(rng.random() * len(consonants))],
        vowels[int(rng.random() * len(vowels))],
        consonants[int(rng.random() * len(consonants))],
        vowels[int(rng.random() * len(vowels))],
    ))
    return name


# ---------------------------------------------------------------------------
# Static-stability proxy
# ---------------------------------------------------------------------------

def _is_static_stable(total_mass_kg: float, n_components: int) -> bool:
    """Crude statics: kg/m² over a sqrt(n_components)·0.5 m footprint.

    Returns True if the assembly's mass-loading stays under
    ``STATIC_STRESS_CEILING_KG_PER_M2``. This is intentionally a proxy:
    Wave 36+ will wire :mod:`engine.statics` for voxelised machines.
    """
    side = math.sqrt(max(1, n_components)) * 0.5
    footprint_m2 = max(side * side, 0.25)
    return (total_mass_kg / footprint_m2) < STATIC_STRESS_CEILING_KG_PER_M2


# ---------------------------------------------------------------------------
# Public API — installer + try_assemble + state
# ---------------------------------------------------------------------------

def install_machine_emergence(sim) -> MachineEmergenceState:
    """Idempotent installer.

    Attaches ``sim._machine_state``. Does **not** wrap ``sim.step`` —
    machines are event-driven, the cognition layer (Wave 36+) will call
    :func:`try_assemble_machine` directly when an agent decides to build.
    """
    existing: Optional[MachineEmergenceState] = getattr(
        sim, "_machine_state", None)
    if existing is not None:
        return existing
    state = MachineEmergenceState()
    sim._machine_state = state
    return state


def uninstall_machine_emergence(sim) -> bool:
    """Detach the state if present. Returns True if anything was removed."""
    if hasattr(sim, "_machine_state"):
        try:
            delattr(sim, "_machine_state")
            return True
        except Exception:
            return False
    return False


def try_assemble_machine(
    sim,
    row: int,
    components: List[MachineComponent],
    intended_function_kinds: Optional[List[int]] = None,
) -> Tuple[bool, str, Optional[Machine]]:
    """Attempt an assembly. Returns ``(success, reason, machine_or_None)``.

    Pipeline:

      1. Validate component count (>= :data:`MIN_COMPONENTS_FOR_MACHINE`).
      2. Collect aggregate function kinds (artifact components + intended).
      3. Compute the deterministic fingerprint.
      4. Per-culture lookup: known fingerprint → reuse the existing
         ``Machine`` (success, ``reason='recognized'``, no new invention
         counted).
         New fingerprint → register a fresh :class:`Machine` with an
         auto-generated CVCV name and credit the inventor.

    The function increments ``n_total_attempted`` on every call (success
    or not). It increments ``n_total_invented`` only when a brand-new
    fingerprint is created in the calling agent's culture.

    The static-stability flag is set per ``_is_static_stable``: it does
    **not** gate registration (a wobbly machine still gets a name) but
    is exposed so callers can decide whether to use it.
    """
    state = install_machine_emergence(sim)
    reg = state.registry
    reg.n_total_attempted += 1

    if not components or len(components) < MIN_COMPONENTS_FOR_MACHINE:
        return (False,
                f"too_few_components:{len(components or [])}<"
                f"{MIN_COMPONENTS_FOR_MACHINE}",
                None)

    invention: Optional[InventionRegistry] = getattr(
        sim, "_invention_registry", None)

    # Aggregate functions.
    fn_set: set = set()
    if intended_function_kinds:
        for f in intended_function_kinds:
            fn_set.add(int(f))
    for c in components:
        for f in _component_functions(c, invention):
            fn_set.add(int(f))
    fn_list = sorted(fn_set)

    # Fingerprint.
    fp = compute_machine_fingerprint(components, fn_list, invention=invention)

    culture = _agent_culture(sim, row)
    key = (int(culture), fp)
    if key in reg.fingerprint_to_id:
        mid = reg.fingerprint_to_id[key]
        machine = reg.machines.get(mid)
        if machine is not None:
            return (True, "recognized", machine)
        # If the registry is corrupted, fall through and re-create.

    # New machine!
    world_seed = int(getattr(sim.cfg, "seed", 0))
    name = auto_name_machine(world_seed, culture, fp)
    # Ensure global uniqueness when two cultures happen to coin the
    # same syllables by appending a culture suffix on collision.
    if name in reg.machines:
        name = f"{name}_{int(culture)}"

    # Total mass + dominant material — recomputed from components.
    total_mass = float(sum(c.mass_kg for c in components))
    dominant = fp[1]
    stable = _is_static_stable(total_mass, len(components))

    machine = Machine(
        machine_id=name,
        fingerprint=fp,
        components=list(components),
        function_kinds=fn_list,
        dominant_material=str(dominant),
        total_mass_kg=total_mass,
        culture_id=int(culture),
        inventor_row=int(row),
        tick_created=int(getattr(sim, "tick", 0)),
        is_static_stable=stable,
    )
    reg.machines[name] = machine
    reg.machines_by_culture.setdefault(int(culture), []).append(name)
    reg.fingerprint_to_id[key] = name
    reg.inventor_credit[int(row)] = reg.inventor_credit.get(int(row), 0) + 1
    reg.n_total_invented += 1
    return (True, "invented", machine)


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def machine_emergence_state(sim) -> Dict[str, object]:
    """Read-only snapshot suitable for dashboards / smoke output."""
    state: Optional[MachineEmergenceState] = getattr(
        sim, "_machine_state", None)
    if state is None:
        return {}
    reg = state.registry
    # Top inventors (row, credit) sorted by descending credit.
    top_inventors = sorted(reg.inventor_credit.items(),
                            key=lambda kv: -kv[1])[:5]
    by_culture: Dict[str, List[Dict[str, object]]] = {}
    for cul, names in reg.machines_by_culture.items():
        by_culture[str(cul)] = [
            {
                "name": n,
                "fingerprint": list(reg.machines[n].fingerprint) if n in reg.machines else [],
                "dominant_material": reg.machines[n].dominant_material if n in reg.machines else "",
                "total_mass_kg": reg.machines[n].total_mass_kg if n in reg.machines else 0.0,
                "is_static_stable": reg.machines[n].is_static_stable if n in reg.machines else False,
                "function_kinds": list(reg.machines[n].function_kinds) if n in reg.machines else [],
            }
            for n in names
        ]
    return {
        "n_total_attempted": reg.n_total_attempted,
        "n_total_invented": reg.n_total_invented,
        "n_machines": len(reg.machines),
        "n_cultures_with_machines": len(reg.machines_by_culture),
        "by_culture": by_culture,
        "top_inventors": [{"row": r, "credit": c} for r, c in top_inventors],
    }


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "MASS_BUCKETS_KG",
    "STATIC_STRESS_CEILING_KG_PER_M2",
    "MIN_COMPONENTS_FOR_MACHINE",
    "MachineComponent",
    "Machine",
    "MachineRegistry",
    "MachineEmergenceState",
    "mass_bucket",
    "compute_machine_fingerprint",
    "auto_name_machine",
    "install_machine_emergence",
    "uninstall_machine_emergence",
    "try_assemble_machine",
    "machine_emergence_state",
]
