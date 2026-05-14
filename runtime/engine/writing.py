"""Genesis Engine — Phase 4 / Wave 9b : writing.

Writing turns cultures into accumulating knowledge systems. Without
writing, every craft recipe (Wave 1/2 :class:`MaterialRegistry`), every
seed (:mod:`engine.agriculture`), every law (future :mod:`engine.polity`)
must be re-discovered each generation. With writing, knowledge survives
the death of its inventor.

Content types
-------------
* ``RECIPE`` — a reference to a SynthesizedMaterial (material_id +
  name). Reading adds it to the reader's culture's MaterialRegistry.
* ``SEED`` — a clade name from :mod:`engine.plant_catalog`. Reading
  adds it to the reader's culture's seed_library in
  :mod:`engine.agriculture`.
* ``LAW`` — short free-text rule (consumed later by polity).
* ``LEXICON`` — phonemic vocabulary entry (consumed later by Phase 4
  language work).

Physical substrates (coupled with material_aging)
------------------------------------------------
Each :class:`Inscription` is bound to a :class:`MaterialInstance` from
``engine.material_aging``. The inscription is readable as long as the
host material's ``integrity`` > 0.10. When the material decays past
that threshold, the inscription becomes ``illegible`` and disappears
from future scans.

Real-world calibration of substrate longevity (annual fractional
loss factor reused from material_aging.ANNUAL_LOSS_FRACTION × the
exposure mode):

  - ``ceramic`` (fired clay tablet) — humid air 0.08 %/yr → ~6000 yr
    real, matches Sumerian cuneiform survival.
  - ``stone_granite`` (rock inscription) — 0.005 %/yr → effectively
    immortal.
  - ``wood`` (carved log) — 18 %/yr → ~10 yr useful life.
  - ``leather`` (parchment) — 20 %/yr → ~5 yr (worse than papyrus,
    realistic for raw skin without tanning practice).

Cultures with **maintenance practices** (varnish, drying) — already
modelled in material_aging.MAINTENANCE_FACTORS — protect their
written record automatically.

Reading mechanic
----------------
``read_inscription(sim, state, row, inscription_id)`` :
  1. Checks that the inscription's MaterialInstance has integrity > 0.10.
  2. Resolves the reader's culture id.
  3. Dispatches by content_type :
     - RECIPE → push the material into the culture's registry slot.
     - SEED   → ``agriculture.discover_seed``.
     - LAW    → cumulated in ``culture_laws`` set (future polity hook).
     - LEXICON → cumulated in ``culture_lexicon`` set.
  4. Logs a ``ReadEvent``.

Determinism
-----------
Pure deterministic. Reading is event-driven, not RNG-gated. The only
RNG could be future "literacy roll" which is not in this sprint.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — knowledge ↔ material
substrate ↔ culture.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — composable
multi-step knowledge transmission respecting physical decay laws.
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

import json
import os
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Enums + classes
# ---------------------------------------------------------------------------

class InscriptionType(IntEnum):
    RECIPE = 0
    SEED = 1
    LAW = 2
    LEXICON = 3


# Minimum host integrity for an inscription to remain legible.
LEGIBLE_INTEGRITY_THRESHOLD = 0.10


@dataclass
class Inscription:
    """One written record bound to a physical MaterialInstance."""
    inscription_id: int
    instance_id: int                    # → material_aging.MaterialInstance.instance_id
    content_type: int                   # InscriptionType
    content_key: str                    # material_id (str), clade name, law text key, etc.
    author_culture: int
    created_tick: int
    times_read: int = 0
    illegible: bool = False


@dataclass
class ReadEvent:
    inscription_id: int
    reader_row: int
    reader_culture: int
    tick: int
    outcome: str                        # "new_knowledge" | "already_known" | "illegible"


@dataclass
class WritingState:
    """Attached to ``sim._writing_state``."""
    inscriptions: Dict[int, Inscription] = field(default_factory=dict)
    next_inscription_id: int = 1
    # Per-culture knowledge stores. Recipes + seeds are also tracked in
    # their authoritative registries (MaterialRegistry, AgricultureState)
    # but we duplicate here so the writing module is self-contained for
    # querying / persistence purposes.
    culture_recipes: Dict[int, Set[str]] = field(default_factory=dict)
    culture_seeds: Dict[int, Set[str]] = field(default_factory=dict)
    culture_laws: Dict[int, Set[str]] = field(default_factory=dict)
    culture_lexicon: Dict[int, Set[str]] = field(default_factory=dict)
    # Audit log of every read event (recent tail).
    read_events: List[ReadEvent] = field(default_factory=list)
    # Cumulative stats.
    inscribe_events: int = 0
    successful_reads: int = 0
    illegible_attempts: int = 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install_writing(sim) -> WritingState:
    """Idempotent installer. No step wrapper — writing is event-driven
    only (no per-tick processing beyond inheriting decay from
    material_aging which the caller already ticks).
    """
    existing: Optional[WritingState] = getattr(sim, "_writing_state", None)
    if existing is not None:
        return existing
    state = WritingState()
    sim._writing_state = state
    return state


def _agent_culture(sim, row: int) -> int:
    cultures = getattr(sim.agents, "culture", None)
    if cultures is not None:
        try:
            return int(cultures[row])
        except Exception:
            return 0
    return 0


def _aging_instance(sim, instance_id: int):
    """Lookup a MaterialInstance from sim._aging_registry. None if missing."""
    reg = getattr(sim, "_aging_registry", None)
    if reg is None:
        return None
    return reg.instance(instance_id)


def inscribe(
    sim,
    state: WritingState,
    instance_id: int,
    content_type: int,
    content_key: str,
    author_culture: int,
) -> Tuple[Optional[int], str]:
    """Author a new inscription onto an existing physical material.

    Returns ``(inscription_id, "")`` on success ; ``(None, reason)`` on
    failure (e.g. instance missing, instance already destroyed).
    """
    inst = _aging_instance(sim, instance_id)
    if inst is None:
        return None, "no_material_instance"
    if inst.destroyed or inst.integrity < LEGIBLE_INTEGRITY_THRESHOLD:
        return None, "host_unusable"
    iid = state.next_inscription_id
    state.next_inscription_id += 1
    insc = Inscription(
        inscription_id=iid,
        instance_id=instance_id,
        content_type=content_type,
        content_key=content_key,
        author_culture=author_culture,
        created_tick=int(sim.tick),
    )
    state.inscriptions[iid] = insc
    state.inscribe_events += 1
    # Author's culture automatically knows what they wrote.
    _store_in_culture(state, author_culture, content_type, content_key)
    return iid, ""


def _store_in_culture(state: WritingState, culture: int,
                      content_type: int, content_key: str) -> bool:
    """Add ``content_key`` to the appropriate per-culture set.

    Returns ``True`` if newly added (the reader gains knowledge), ``False``
    if it was already known.
    """
    bucket = {
        int(InscriptionType.RECIPE):  state.culture_recipes,
        int(InscriptionType.SEED):    state.culture_seeds,
        int(InscriptionType.LAW):     state.culture_laws,
        int(InscriptionType.LEXICON): state.culture_lexicon,
    }.get(content_type)
    if bucket is None:
        return False
    s = bucket.setdefault(culture, set())
    if content_key in s:
        return False
    s.add(content_key)
    return True


def _check_legibility(sim, state: WritingState,
                      inscription: Inscription) -> bool:
    """Recompute legibility from the host material's current integrity."""
    if inscription.illegible:
        return False
    inst = _aging_instance(sim, inscription.instance_id)
    if inst is None or inst.destroyed:
        inscription.illegible = True
        return False
    if inst.integrity < LEGIBLE_INTEGRITY_THRESHOLD:
        inscription.illegible = True
        return False
    return True


def read_inscription(
    sim,
    state: WritingState,
    row: int,
    inscription_id: int,
) -> Tuple[bool, str]:
    """Have agent ``row`` read the inscription. Returns (success, outcome).

    Outcomes :
      ``new_knowledge``  — the reader's culture gained new info
      ``already_known``  — the reader's culture already had it
      ``illegible``      — host material decayed past the threshold
    """
    insc = state.inscriptions.get(inscription_id)
    if insc is None:
        return False, "no_inscription"
    if not _check_legibility(sim, state, insc):
        state.illegible_attempts += 1
        state.read_events.append(ReadEvent(
            inscription_id=inscription_id,
            reader_row=row,
            reader_culture=_agent_culture(sim, row),
            tick=int(sim.tick),
            outcome="illegible",
        ))
        return False, "illegible"
    insc.times_read += 1
    reader_culture = _agent_culture(sim, row)
    is_new = _store_in_culture(state, reader_culture,
                               insc.content_type, insc.content_key)
    outcome = "new_knowledge" if is_new else "already_known"
    state.successful_reads += 1
    # Side-effect : push knowledge into the authoritative registries.
    # We call this on EVERY successful read (not only "new_knowledge")
    # so that downstream registries (agriculture, material_synthesis)
    # which may have been installed AFTER the first read still receive
    # the knowledge. The downstream APIs are themselves idempotent.
    _propagate_to_authoritative(sim, insc.content_type,
                                insc.content_key, reader_culture)
    state.read_events.append(ReadEvent(
        inscription_id=inscription_id,
        reader_row=row,
        reader_culture=reader_culture,
        tick=int(sim.tick),
        outcome=outcome,
    ))
    # Keep log bounded.
    if len(state.read_events) > 1000:
        state.read_events = state.read_events[-1000:]
    return True, outcome


def _propagate_to_authoritative(sim, content_type: int,
                                content_key: str, culture: int) -> None:
    """Forward new knowledge gained from reading to the canonical
    registry — agriculture's seed_library or material_synthesis registry.
    """
    if content_type == int(InscriptionType.SEED):
        try:
            from engine.agriculture import discover_seed
            ag_state = getattr(sim, "_ag_state", None)
            if ag_state is not None:
                discover_seed(ag_state, culture, content_key)
        except Exception:
            pass
    elif content_type == int(InscriptionType.RECIPE):
        reg = getattr(sim, "_material_registry", None)
        if reg is None:
            return
        # content_key encodes either an int material_id or a name.
        try:
            mid = int(content_key)
            reg._culture_known.setdefault(culture, set()).add(mid)
        except ValueError:
            named_id = reg._by_name.get(content_key)
            if named_id is not None:
                reg._culture_known.setdefault(culture, set()).add(named_id)


# ---------------------------------------------------------------------------
# Reporter + persistence
# ---------------------------------------------------------------------------

def writing_state(sim) -> Dict[str, object]:
    """Snapshot for ``/api/writing_state``."""
    state: Optional[WritingState] = getattr(sim, "_writing_state", None)
    if state is None:
        return {}
    # Refresh legibility before counting.
    legible = 0
    illegible = 0
    by_type: Dict[str, int] = {}
    type_name = {int(t): t.name for t in InscriptionType}
    for insc in state.inscriptions.values():
        if _check_legibility(sim, state, insc):
            legible += 1
            name = type_name.get(insc.content_type, str(insc.content_type))
            by_type[name] = by_type.get(name, 0) + 1
        else:
            illegible += 1
    return {
        "inscriptions_total": len(state.inscriptions),
        "legible": legible,
        "illegible": illegible,
        "by_content_type": by_type,
        "inscribe_events": state.inscribe_events,
        "successful_reads": state.successful_reads,
        "illegible_attempts": state.illegible_attempts,
        "cultures_with_recipes": sorted(state.culture_recipes.keys()),
        "cultures_with_seeds": sorted(state.culture_seeds.keys()),
        "cultures_with_laws": sorted(state.culture_laws.keys()),
        "recent_reads_tail": [
            {"inscription_id": e.inscription_id, "tick": e.tick,
             "reader_culture": e.reader_culture, "outcome": e.outcome}
            for e in state.read_events[-10:]
        ],
    }


def save_writing_state(sim, target_dir: str) -> bool:
    state: Optional[WritingState] = getattr(sim, "_writing_state", None)
    if state is None:
        return False
    payload = {
        "next_inscription_id": state.next_inscription_id,
        "inscribe_events": state.inscribe_events,
        "successful_reads": state.successful_reads,
        "illegible_attempts": state.illegible_attempts,
        "inscriptions": [
            {"inscription_id": i.inscription_id,
             "instance_id": i.instance_id,
             "content_type": i.content_type,
             "content_key": i.content_key,
             "author_culture": i.author_culture,
             "created_tick": i.created_tick,
             "times_read": i.times_read,
             "illegible": i.illegible}
            for i in state.inscriptions.values()
        ],
        "culture_recipes": {str(k): sorted(v)
                            for k, v in state.culture_recipes.items()},
        "culture_seeds": {str(k): sorted(v)
                          for k, v in state.culture_seeds.items()},
        "culture_laws": {str(k): sorted(v)
                         for k, v in state.culture_laws.items()},
        "culture_lexicon": {str(k): sorted(v)
                            for k, v in state.culture_lexicon.items()},
        "read_events_tail": [
            {"inscription_id": e.inscription_id, "reader_row": e.reader_row,
             "reader_culture": e.reader_culture, "tick": e.tick,
             "outcome": e.outcome}
            for e in state.read_events[-100:]
        ],
    }
    with open(os.path.join(target_dir, "writing.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_writing_state(sim, target_dir: str) -> bool:
    path = os.path.join(target_dir, "writing.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_writing(sim)
    state.next_inscription_id = int(payload.get("next_inscription_id", 1))
    state.inscribe_events = int(payload.get("inscribe_events", 0))
    state.successful_reads = int(payload.get("successful_reads", 0))
    state.illegible_attempts = int(payload.get("illegible_attempts", 0))
    state.inscriptions.clear()
    for d in payload.get("inscriptions", []):
        insc = Inscription(
            inscription_id=int(d["inscription_id"]),
            instance_id=int(d["instance_id"]),
            content_type=int(d["content_type"]),
            content_key=str(d["content_key"]),
            author_culture=int(d["author_culture"]),
            created_tick=int(d["created_tick"]),
            times_read=int(d.get("times_read", 0)),
            illegible=bool(d.get("illegible", False)),
        )
        state.inscriptions[insc.inscription_id] = insc
    state.culture_recipes = {int(k): set(v)
                             for k, v in payload.get("culture_recipes", {}).items()}
    state.culture_seeds = {int(k): set(v)
                           for k, v in payload.get("culture_seeds", {}).items()}
    state.culture_laws = {int(k): set(v)
                          for k, v in payload.get("culture_laws", {}).items()}
    state.culture_lexicon = {int(k): set(v)
                             for k, v in payload.get("culture_lexicon", {}).items()}
    state.read_events = [
        ReadEvent(
            inscription_id=int(d["inscription_id"]),
            reader_row=int(d["reader_row"]),
            reader_culture=int(d["reader_culture"]),
            tick=int(d["tick"]),
            outcome=str(d.get("outcome", "")),
        )
        for d in payload.get("read_events_tail", [])
    ]
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "InscriptionType",
    "Inscription",
    "ReadEvent",
    "WritingState",
    "LEGIBLE_INTEGRITY_THRESHOLD",
    "install_writing",
    "inscribe",
    "read_inscription",
    "writing_state",
    "save_writing_state",
    "load_writing_state",
]
