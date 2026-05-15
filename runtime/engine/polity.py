"""Genesis Engine — Phase 4 / Wave 9c : polity (État émergent).

A **polity** is a proto-government : a self-recognized association of
agents who share a territory, a set of adopted laws (from
:mod:`engine.writing`), a leader, and a treasury. Polities emerge
when enough agents co-located accept the same set of laws ; they
collapse when membership drops below the survival threshold.

What a polity does each tick
----------------------------
* **Leader election** — the agent with the highest *prestige score*
  (offspring count + authored inscriptions + age × cognitive bonus)
  inside the polity becomes leader. Deterministic tie-break via
  ``prf_rng`` on polity_id.
* **Taxation** — collects ``TAX_RATE`` × each member's ``inv_food``
  into the polity ``treasury_kcal`` (food calories pool). Real-world
  analogue: storehouse / granary tax of early Mesopotamian polities.
* **Redistribution** — when members are hungry above
  ``REDISTRIBUTE_HUNGER_THRESHOLD``, treasury food is doled out
  proportional to need. This is the "social contract" — agents pay
  in food when sated, draw out when starving.
* **Law enforcement** — for every adopted LAW (inscribed via
  :mod:`engine.writing`), polity tracks violations. The reference
  enforcement targets cholera-blocking laws like
  ``"no_relief_upstream"`` : penalises any member who relieves on
  a contaminated chunk by reducing their tax-share inversely.

Emergence trigger
-----------------
``maybe_emerge_polity(sim, state)`` is called per-tick. A new polity
is founded when:
  * ``>= POLITY_MIN_FOUNDERS`` agents are within
    ``POLITY_FOUNDING_RADIUS_M`` of each other
  * none of them are already in a polity
  * at least one shared LAW inscription is legible to all of them

Cross-module coupling
---------------------
* Reads ``writing.WritingState.culture_laws`` to discover laws.
* Reads / mutates ``sim.agents.inv_food`` for taxation +
  redistribution.
* Reads ``sim.agents.offspring_count`` for leader prestige.
* Reads ``physiology.PhysioFields.water_contamination`` to detect
  cholera-rule violations.

Determinism
-----------
All RNG via :func:`engine.core.prf_rng`. Polities are bit-stable
across runs with the same seed.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — society shapes agent
food allocation shapes survival shapes culture.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — composable
multi-step polity rollouts respecting taxation + redistribution
mass-balance.
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from engine.core import TICK_DT_S, prf_rng
from engine.world import CHUNK_SIDE_M, world_to_chunk


# ---------------------------------------------------------------------------
# Calibration constants
# ---------------------------------------------------------------------------

POLITY_MIN_FOUNDERS = 4                   # min agents needed to found
POLITY_FOUNDING_RADIUS_M = 200.0          # spatial cohesion (founders within)
POLITY_MEMBER_RADIUS_M = 500.0            # member range from leader
POLITY_DISBAND_MEMBERS = 2                # below this → polity collapses
TAX_RATE = 0.05                           # 5 % of inv_food per tick collected
REDISTRIBUTE_HUNGER_THRESHOLD = 0.55      # hunger above which member can claim
REDISTRIBUTE_KCAL_PER_HUNGER_UNIT = 1.0   # rough food density (kg → 1.0)
LEADER_RE_ELECT_INTERVAL_TICKS = 1000     # ~17 sim-minutes at accel=1500
KCAL_PER_KG_FOOD = 2500.0                 # Atwater average


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Polity:
    polity_id: int
    name: str
    leader_row: int
    leader_culture: int
    territory_chunks: Set[Tuple[int, int, int]] = field(default_factory=set)
    member_rows: Set[int] = field(default_factory=set)
    enforced_laws: Set[str] = field(default_factory=set)
    treasury_kcal: float = 0.0
    founded_tick: int = 0
    last_leader_election_tick: int = -1
    last_redistribution_tick: int = -1
    # Cumulative stats.
    tax_collected_kcal: float = 0.0
    distributed_kcal: float = 0.0
    violations: int = 0


@dataclass
class PolityState:
    polities: Dict[int, Polity] = field(default_factory=dict)
    next_id: int = 1
    chunk_to_polity: Dict[Tuple[int, int, int], int] = field(default_factory=dict)
    member_to_polity: Dict[int, int] = field(default_factory=dict)
    # Stats.
    polities_founded: int = 0
    polities_disbanded: int = 0
    leader_elections: int = 0
    last_total_treasury_kcal: float = 0.0
    last_global_members: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_culture(sim, row: int) -> int:
    cultures = getattr(sim.agents, "culture", None)
    if cultures is not None:
        try:
            return int(cultures[row])
        except Exception:
            return 0
    return 0


def _prestige_score(sim, row: int, writing_state=None) -> float:
    """Sum of demographic + cultural achievements for leader election.

    offspring_count + 0.5 × authored_inscriptions + age_factor
    + personality bonus (Wave 11: ambition × 5 + extraversion × 2).
    Ambition drives candidacy ; extraversion gives social visibility.
    """
    score = 0.0
    try:
        score += float(sim.agents.offspring_count[row])
    except Exception:
        pass
    if writing_state is not None:
        # Count inscriptions where author_culture == this agent's culture.
        culture = _agent_culture(sim, row)
        authored = sum(1 for ins in writing_state.inscriptions.values()
                       if ins.author_culture == culture)
        score += 0.5 * authored
    try:
        born = int(sim.agents.born_tick[row])
        accel = float(sim.cfg.drive_accel)
        age_ticks = max(0, sim.tick - born)
        age_yr = age_ticks * accel / (365.0 * 86400.0)
        score += min(20.0, age_yr * 0.1)  # cap age bonus
    except Exception:
        pass
    # Wave 11 — personality drives politics.
    try:
        ambition = float(sim.agents.ambition[row])
        extraversion = float(sim.agents.extraversion[row])
        score += 5.0 * ambition + 2.0 * extraversion
    except Exception:
        pass
    return score


def _alive(sim, row: int) -> bool:
    try:
        return bool(sim.agents.alive[row])
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Emergence
# ---------------------------------------------------------------------------

def maybe_emerge_polity(sim, state: PolityState) -> Optional[int]:
    """Look for a cluster of agents satisfying founding conditions and
    found a polity around them. Returns the polity_id when founded,
    else None.

    Cheap : O(n_active) per call. Returns at most one new polity per
    invocation to keep the dynamics gradual.
    """
    n = sim.agents.n_active
    if n < POLITY_MIN_FOUNDERS:
        return None
    alive_rows = np.flatnonzero(sim.agents.alive[:n])
    if alive_rows.size < POLITY_MIN_FOUNDERS:
        return None
    # Exclude agents already in a polity.
    free = [int(r) for r in alive_rows
            if int(r) not in state.member_to_polity]
    if len(free) < POLITY_MIN_FOUNDERS:
        return None
    # Try each free agent as a candidate seed ; find one with enough
    # neighbours inside the founding radius.
    for seed_row in free:
        sx = float(sim.agents.pos[seed_row, 0])
        sy = float(sim.agents.pos[seed_row, 1])
        cluster = []
        for r in free:
            dx = float(sim.agents.pos[r, 0]) - sx
            dy = float(sim.agents.pos[r, 1]) - sy
            if dx * dx + dy * dy <= POLITY_FOUNDING_RADIUS_M ** 2:
                cluster.append(r)
        if len(cluster) >= POLITY_MIN_FOUNDERS:
            # Check shared laws via writing state.
            writing_state = getattr(sim, "_writing_state", None)
            shared_laws: Set[str] = set()
            if writing_state is not None:
                # Use the founder's culture as the proxy.
                seed_culture = _agent_culture(sim, seed_row)
                shared_laws = set(writing_state.culture_laws.get(seed_culture, set()))
            # Found the polity (even without laws — laws can be adopted later).
            pol_id = state.next_id
            state.next_id += 1
            polity = Polity(
                polity_id=pol_id,
                name=f"polity_{pol_id}",
                leader_row=seed_row,
                leader_culture=_agent_culture(sim, seed_row),
                member_rows=set(cluster),
                enforced_laws=shared_laws,
                founded_tick=int(sim.tick),
            )
            for r in cluster:
                state.member_to_polity[r] = pol_id
                # Add the agent's chunk to territory.
                px = float(sim.agents.pos[r, 0])
                py = float(sim.agents.pos[r, 1])
                ch = world_to_chunk(px, py)
                polity.territory_chunks.add(ch)
                state.chunk_to_polity[ch] = pol_id
            state.polities[pol_id] = polity
            state.polities_founded += 1
            return pol_id
    return None


# ---------------------------------------------------------------------------
# Per-polity tick : leader, tax, redistribute, enforce
# ---------------------------------------------------------------------------

def _re_elect_leader(sim, polity: Polity, writing_state) -> None:
    if not polity.member_rows:
        return
    alive_members = [r for r in polity.member_rows if _alive(sim, r)]
    if not alive_members:
        return
    scored = [(r, _prestige_score(sim, r, writing_state))
              for r in alive_members]
    # prf_rng deterministic tie-break.
    rng = prf_rng(sim.cfg.seed,
                  ["polity", "elect", str(polity.polity_id)],
                  [int(sim.tick)])
    scored.sort(key=lambda kv: (-kv[1], rng.random()))
    new_leader = scored[0][0]
    if new_leader != polity.leader_row:
        polity.leader_row = new_leader
        polity.leader_culture = _agent_culture(sim, new_leader)
    polity.last_leader_election_tick = int(sim.tick)


def _tax(sim, polity: Polity) -> float:
    """Collect tax from each alive member's inv_food. Returns kcal collected.

    Wave 11 — per-agent compliance scales with agreeableness :
    ``compliance = 0.3 + 0.7 × agreeableness`` (range [0.3, 1.0]).
    A fully agreeable agent pays the nominal TAX_RATE ; a low-A agent
    only pays ~30 % of nominal (evasion / hoarding).
    """
    total = 0.0
    inv_food = getattr(sim.agents, "inv_food", None)
    if inv_food is None:
        return 0.0
    agreeableness = getattr(sim.agents, "agreeableness", None)
    for r in polity.member_rows:
        if not _alive(sim, r):
            continue
        food_kg = float(inv_food[r])
        if food_kg <= 0:
            continue
        if agreeableness is not None:
            compliance = 0.3 + 0.7 * float(agreeableness[r])
        else:
            compliance = 1.0
        levy_kg = food_kg * TAX_RATE * compliance
        inv_food[r] = food_kg - levy_kg
        total += levy_kg * KCAL_PER_KG_FOOD
    polity.treasury_kcal += total
    polity.tax_collected_kcal += total
    return total


def _redistribute(sim, polity: Polity) -> float:
    """Pour treasury food to hungry members proportional to hunger.
    Returns kcal distributed.

    Wave 11 — leader's ``conscientiousness`` shapes BOTH :

    * **share_fraction** of the treasury actually redistributed :
      ``0.30 + 0.70 × consc``. A leader low in conscientiousness
      hoards (~30 % out) ; a high-C leader empties the granaries
      (~100 % out) to feed the hungry.
    * **fairness exponent** for need weighting : ``weight = need ** (1/fairness)``
      with ``fairness = max(0.20, consc)``. consc=1 → linear (equal
      proportional share) ; consc→0 → power curve favouring the
      hungriest (winner-take-all).
    """
    if polity.treasury_kcal <= 0:
        return 0.0
    inv_food = getattr(sim.agents, "inv_food", None)
    hunger = getattr(sim.agents, "hunger", None)
    capacity = getattr(sim.agents, "inv_capacity_kg", None)
    if inv_food is None or hunger is None:
        return 0.0
    # Leader conscientiousness — shapes the redistribution curve.
    consc_attr = getattr(sim.agents, "conscientiousness", None)
    if consc_attr is not None and _alive(sim, polity.leader_row):
        consc = float(consc_attr[polity.leader_row])
    else:
        consc = 0.5
    share_fraction = 0.30 + 0.70 * consc
    fairness = max(0.20, consc)
    needy: List[Tuple[int, float]] = []
    weighted: List[Tuple[int, float, float]] = []
    total_weight = 0.0
    for r in polity.member_rows:
        if not _alive(sim, r):
            continue
        h = float(hunger[r])
        if h >= REDISTRIBUTE_HUNGER_THRESHOLD:
            need = h - REDISTRIBUTE_HUNGER_THRESHOLD
            w = need ** (1.0 / fairness) if need > 0 else 0.0
            needy.append((r, need))
            weighted.append((r, need, w))
            total_weight += w
    if not weighted or total_weight <= 0:
        return 0.0
    pool_kcal = polity.treasury_kcal * share_fraction
    distributed = 0.0
    for r, need, w in weighted:
        share_kcal = pool_kcal * (w / total_weight)
        share_kg = share_kcal / KCAL_PER_KG_FOOD
        # Capped by inventory headroom.
        if capacity is not None:
            cap = float(capacity[r])
            cur = float(inv_food[r])
            give_kg = min(share_kg, cap - cur)
        else:
            give_kg = share_kg
        give_kg = max(0.0, give_kg)
        if give_kg > 0:
            inv_food[r] = float(inv_food[r]) + give_kg
            distributed += give_kg * KCAL_PER_KG_FOOD
    polity.treasury_kcal = max(0.0, polity.treasury_kcal - distributed)
    polity.distributed_kcal += distributed
    polity.last_redistribution_tick = int(sim.tick)
    return distributed


def _enforce_laws(sim, polity: Polity) -> int:
    """Increment ``polity.violations`` when members break adopted laws.

    Reference rule : ``no_relief_upstream`` — if a member is on a
    chunk in ``water_contamination`` they personally contributed to.
    Cheap proxy : any member relief tick on a contaminated chunk.
    """
    if "no_relief_upstream" not in polity.enforced_laws:
        return 0
    physio = getattr(sim, "_physio_fields", None)
    if physio is None or not physio.water_contamination:
        return 0
    v = 0
    for r in polity.member_rows:
        if not _alive(sim, r):
            continue
        px = float(sim.agents.pos[r, 0])
        py = float(sim.agents.pos[r, 1])
        ch = world_to_chunk(px, py)
        cont = physio.water_contamination.get(ch, 0.0)
        # Heuristic : if the chunk is highly contaminated AND the member
        # bladder/bowel was recently relieved here, count a violation.
        if cont > 0.5:
            # Cheap proxy : if their bladder is now < 0.1, they just relieved.
            bladder = float(physio.bladder[r])
            if bladder < 0.10:
                v += 1
    polity.violations += v
    return v


def _disband_if_collapsed(state: PolityState, polity: Polity) -> bool:
    if len(polity.member_rows) < POLITY_DISBAND_MEMBERS:
        for r in polity.member_rows:
            state.member_to_polity.pop(r, None)
        for ch in polity.territory_chunks:
            if state.chunk_to_polity.get(ch) == polity.polity_id:
                state.chunk_to_polity.pop(ch, None)
        state.polities.pop(polity.polity_id, None)
        state.polities_disbanded += 1
        return True
    return False


# ---------------------------------------------------------------------------
# Per-tick driver
# ---------------------------------------------------------------------------

def tick_polity(sim, state: PolityState) -> None:
    """Run one tick of polity dynamics across all polities."""
    writing_state = getattr(sim, "_writing_state", None)
    total_treasury = 0.0
    total_members = 0
    # Iterate over a snapshot to allow disband mid-loop.
    for pid, polity in list(state.polities.items()):
        # Prune dead members.
        polity.member_rows = {r for r in polity.member_rows if _alive(sim, r)}
        if _disband_if_collapsed(state, polity):
            continue
        # Periodic leader re-election.
        if (sim.tick - polity.last_leader_election_tick
                >= LEADER_RE_ELECT_INTERVAL_TICKS):
            _re_elect_leader(sim, polity, writing_state)
            state.leader_elections += 1
        # Tax + redistribute + enforce.
        _tax(sim, polity)
        _redistribute(sim, polity)
        _enforce_laws(sim, polity)
        total_treasury += polity.treasury_kcal
        total_members += len(polity.member_rows)
        # Auto-adopt laws : copy current culture_laws of leader.
        if writing_state is not None:
            leader_culture = polity.leader_culture
            laws = writing_state.culture_laws.get(leader_culture, set())
            polity.enforced_laws.update(laws)
    state.last_total_treasury_kcal = total_treasury
    state.last_global_members = total_members
    # Attempt one emergence per tick if no recent polity formed.
    if len(state.polities) == 0 or (sim.tick % 100 == 0):
        maybe_emerge_polity(sim, state)


# ---------------------------------------------------------------------------
# Installer + reporter
# ---------------------------------------------------------------------------

def install_polity(sim) -> PolityState:
    """Idempotent installer. Wraps sim.step with the polity tick."""
    existing: Optional[PolityState] = getattr(sim, "_polity_state", None)
    if existing is not None:
        return existing
    state = PolityState()
    sim._polity_state = state
    orig_step = sim.step

    def wrapped_step():
        orig_step()
        tick_polity(sim, state)

    sim.step = wrapped_step
    return state


def found_polity(sim, state: PolityState, founder_row: int,
                 members: List[int], name: str = "") -> int:
    """Manually create a polity (test hook + future agent intent)."""
    pid = state.next_id
    state.next_id += 1
    polity = Polity(
        polity_id=pid,
        name=name or f"polity_{pid}",
        leader_row=founder_row,
        leader_culture=_agent_culture(sim, founder_row),
        member_rows=set(members) | {founder_row},
        founded_tick=int(sim.tick),
    )
    for r in polity.member_rows:
        state.member_to_polity[r] = pid
        px = float(sim.agents.pos[r, 0])
        py = float(sim.agents.pos[r, 1])
        ch = world_to_chunk(px, py)
        polity.territory_chunks.add(ch)
        state.chunk_to_polity[ch] = pid
    state.polities[pid] = polity
    state.polities_founded += 1
    return pid


def polity_state(sim) -> Dict[str, object]:
    state: Optional[PolityState] = getattr(sim, "_polity_state", None)
    if state is None:
        return {}
    polities_summary = [
        {"id": p.polity_id, "name": p.name,
         "leader_row": p.leader_row,
         "leader_culture": p.leader_culture,
         "n_members": len(p.member_rows),
         "n_chunks": len(p.territory_chunks),
         "n_laws": len(p.enforced_laws),
         "treasury_kcal": round(p.treasury_kcal, 1),
         "tax_collected_total": round(p.tax_collected_kcal, 1),
         "distributed_total": round(p.distributed_kcal, 1),
         "violations": p.violations,
         "founded_tick": p.founded_tick}
        for p in state.polities.values()
    ]
    return {
        "n_polities": len(state.polities),
        "polities": polities_summary,
        "polities_founded_total": state.polities_founded,
        "polities_disbanded_total": state.polities_disbanded,
        "leader_elections_total": state.leader_elections,
        "global_treasury_kcal": round(state.last_total_treasury_kcal, 1),
        "global_members": state.last_global_members,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_polity_state(sim, target_dir: str) -> bool:
    state: Optional[PolityState] = getattr(sim, "_polity_state", None)
    if state is None:
        return False
    payload = {
        "next_id": state.next_id,
        "polities_founded": state.polities_founded,
        "polities_disbanded": state.polities_disbanded,
        "leader_elections": state.leader_elections,
        "polities": [
            {"polity_id": p.polity_id, "name": p.name,
             "leader_row": p.leader_row, "leader_culture": p.leader_culture,
             "territory_chunks": [list(c) for c in p.territory_chunks],
             "member_rows": sorted(p.member_rows),
             "enforced_laws": sorted(p.enforced_laws),
             "treasury_kcal": p.treasury_kcal,
             "founded_tick": p.founded_tick,
             "last_leader_election_tick": p.last_leader_election_tick,
             "last_redistribution_tick": p.last_redistribution_tick,
             "tax_collected_kcal": p.tax_collected_kcal,
             "distributed_kcal": p.distributed_kcal,
             "violations": p.violations}
            for p in state.polities.values()
        ],
    }
    with open(os.path.join(target_dir, "polity.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_polity_state(sim, target_dir: str) -> bool:
    path = os.path.join(target_dir, "polity.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_polity(sim)
    state.next_id = int(payload.get("next_id", 1))
    state.polities_founded = int(payload.get("polities_founded", 0))
    state.polities_disbanded = int(payload.get("polities_disbanded", 0))
    state.leader_elections = int(payload.get("leader_elections", 0))
    state.polities.clear()
    state.chunk_to_polity.clear()
    state.member_to_polity.clear()
    for d in payload.get("polities", []):
        p = Polity(
            polity_id=int(d["polity_id"]),
            name=str(d["name"]),
            leader_row=int(d["leader_row"]),
            leader_culture=int(d["leader_culture"]),
            territory_chunks=set(tuple(c) for c in d.get("territory_chunks", [])),
            member_rows=set(int(r) for r in d.get("member_rows", [])),
            enforced_laws=set(d.get("enforced_laws", [])),
            treasury_kcal=float(d.get("treasury_kcal", 0.0)),
            founded_tick=int(d.get("founded_tick", 0)),
            last_leader_election_tick=int(d.get(
                "last_leader_election_tick", -1)),
            last_redistribution_tick=int(d.get(
                "last_redistribution_tick", -1)),
            tax_collected_kcal=float(d.get("tax_collected_kcal", 0.0)),
            distributed_kcal=float(d.get("distributed_kcal", 0.0)),
            violations=int(d.get("violations", 0)),
        )
        state.polities[p.polity_id] = p
        for r in p.member_rows:
            state.member_to_polity[r] = p.polity_id
        for ch in p.territory_chunks:
            state.chunk_to_polity[ch] = p.polity_id
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "Polity",
    "PolityState",
    "POLITY_MIN_FOUNDERS",
    "POLITY_FOUNDING_RADIUS_M",
    "TAX_RATE",
    "REDISTRIBUTE_HUNGER_THRESHOLD",
    "install_polity",
    "tick_polity",
    "maybe_emerge_polity",
    "found_polity",
    "polity_state",
    "save_polity_state",
    "load_polity_state",
]
