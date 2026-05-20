"""Social layer — topologies relationnelles ouvertes (graphe arbitraire).

Au-delà de ``group_id`` et ``affinity`` scalaire : nœuds = agents,
arêtes typées (kin, trade, alliance, feud, mentorship, …), sous-graphes
nommés (clans, guildes, marchés) sans template imposé.

ADR-0005: Genesis-L4 Feedback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Set, Tuple

import math

import numpy as np

from engine.core import prf_rng


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


class EdgeKind(IntEnum):
    UNSPECIFIED = 0
    KIN = 1
    ALLIANCE = 2
    TRADE = 3
    FEUD = 4
    MENTOR = 5
    SUBORDINATION = 6
    CUSTOM = 7


@dataclass
class SocialEdge:
    a: int
    b: int
    kind: EdgeKind
    weight: float = 0.0
    metadata: Dict[str, float] = field(default_factory=dict)

    def key(self) -> Tuple[int, int]:
        return (min(self.a, self.b), max(self.a, self.b))


@dataclass
class NamedTopology:
    """Sous-graphe arbitraire (clan, guilde, réseau commercial…)."""
    topology_id: int
    name: str
    members: Set[int] = field(default_factory=set)
    edge_kinds: Set[int] = field(default_factory=set)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class SocialTopologyState:
    edges: Dict[Tuple[int, int], SocialEdge] = field(default_factory=dict)
    topologies: Dict[int, NamedTopology] = field(default_factory=dict)
    trade_volume: float = 0.0
    trade_transfers: int = 0
    trade_goods_kg: float = 0.0
    alliances_formed: int = 0
    _next_topology_id: int = 1


# Gravity / XTENT-style trade probability: P ~ (M_i * M_j) / d^beta
TRADE_GRAVITY_BETA = 2.0
TRADE_MIN_DISTANCE_M = 1.0
ALLIANCE_AFFINITY_THRESHOLD = 0.55
ALLIANCE_TICKS_REQUIRED = 40


def install_social_topology(sim) -> SocialTopologyState:
    existing = getattr(sim, "_social_topology", None)
    if existing is not None:
        return existing
    st = SocialTopologyState()
    sim._social_topology = st
    _seed_from_affinity(sim, st)
    if not getattr(sim, "_social_topology_step_patched", False):
        sim._social_topology_step_patched = True
        orig = sim.step

        def wrapped():
            stats = orig()
            tick_social_topology(sim, st)
            return stats

        sim.step = wrapped
    return st


def _seed_from_affinity(sim, st: SocialTopologyState) -> None:
    """Bootstrap edges from existing SocialRelations.affinity."""
    n = sim.agents.n_active
    for row in range(n):
        if not sim.agents.alive[row]:
            continue
        rel = sim.agents.relations[row]
        for other, aff in rel.affinity.items():
            if other >= n or not sim.agents.alive[other]:
                continue
            if aff > 0.25:
                add_edge(st, row, other, EdgeKind.ALLIANCE, weight=aff)
            elif aff < -0.15:
                add_edge(st, row, other, EdgeKind.FEUD, weight=-aff)


def add_edge(st: SocialTopologyState, a: int, b: int,
             kind: EdgeKind, weight: float = 0.0,
             **metadata: float) -> SocialEdge:
    e = SocialEdge(a=a, b=b, kind=kind, weight=weight, metadata=dict(metadata))
    st.edges[e.key()] = e
    return e


def remove_edge(st: SocialTopologyState, a: int, b: int) -> None:
    st.edges.pop((min(a, b), max(a, b)), None)


def create_topology(st: SocialTopologyState, name: str,
                    members: Optional[Set[int]] = None,
                    edge_kinds: Optional[Set[EdgeKind]] = None) -> NamedTopology:
    tid = st._next_topology_id
    st._next_topology_id += 1
    topo = NamedTopology(
        topology_id=tid,
        name=name,
        members=set(members or []),
        edge_kinds=set(int(k) for k in (edge_kinds or [])),
    )
    st.topologies[tid] = topo
    return topo


def neighbors(st: SocialTopologyState, row: int,
              kind_filter: Optional[EdgeKind] = None) -> List[int]:
    out = []
    for (a, b), e in st.edges.items():
        if kind_filter is not None and e.kind != kind_filter:
            continue
        if a == row:
            out.append(b)
        elif b == row:
            out.append(a)
    return out


def gravity_trade_probability(
    mass_a: float,
    mass_b: float,
    distance_m: float,
    *,
    beta: float = TRADE_GRAVITY_BETA,
) -> float:
    """Inter-settlement trade link probability (JASSS gravity / XTENT family)."""
    d = max(TRADE_MIN_DISTANCE_M, float(distance_m))
    m = max(0.1, float(mass_a)) * max(0.1, float(mass_b))
    return min(1.0, m / (d ** beta))


def _agent_trade_mass(agents, row: int) -> float:
    total = float(agents.mass_kg[row])
    for fld in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal",
                "inv_copper", "inv_tin", "inv_bronze"):
        arr = getattr(agents, fld, None)
        if arr is not None:
            total += float(arr[row])
    return total


def propose_trade_edge(sim, st: SocialTopologyState, a: int, b: int) -> bool:
    """Create TRADE edge when gravity model + complementary surplus."""
    if a == b or not sim.agents.alive[a] or not sim.agents.alive[b]:
        return False
    px, py = float(sim.agents.pos[a, 0]), float(sim.agents.pos[a, 1])
    ox, oy = float(sim.agents.pos[b, 0]), float(sim.agents.pos[b, 1])
    dist = math.hypot(ox - px, oy - py)
    p = gravity_trade_probability(
        _agent_trade_mass(sim.agents, a),
        _agent_trade_mass(sim.agents, b),
        dist,
    )
    threshold = 0.02
    ce = getattr(sim, "_commerce_emergence", None)
    if ce is not None:
        from engine.commerce_emergence import macro_trade_flow_between

        flow = macro_trade_flow_between(ce, a, b)
        if flow > 0.0:
            p = min(1.0, p + flow / 100.0)
            threshold = 0.01
    # Complementarity: one has food surplus, other has stone/metal.
    food_a = float(sim.agents.inv_food[a])
    food_b = float(sim.agents.inv_food[b])
    craft_a = float(sim.agents.inv_stone[a]) + float(sim.agents.inv_metal[a])
    craft_b = float(sim.agents.inv_stone[b]) + float(sim.agents.inv_metal[b])
    complementary = (food_a > 0.2 and craft_b > 0.1) or (food_b > 0.2 and craft_a > 0.1)
    if not complementary or p < threshold:
        return False
    add_edge(st, a, b, EdgeKind.TRADE, weight=p)
    st.trade_volume += p
    return True


def tick_social_topology(sim, st: SocialTopologyState) -> List[dict]:
    """Diffuse affinity along edges; gravity trade; alliance formation."""
    events: List[dict] = []
    n = sim.agents.n_active

    # Emergent trade links among co-located agents (sparse scan).
    if sim.tick % 5 == 0:
        for row in range(n):
            if not sim.agents.alive[row]:
                continue
            px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
            for other in range(n):
                if other == row or not sim.agents.alive[other]:
                    continue
                d = math.hypot(
                    float(sim.agents.pos[other, 0]) - px,
                    float(sim.agents.pos[other, 1]) - py,
                )
                if d > 25.0:
                    continue
                key = (min(row, other), max(row, other))
                if key in st.edges:
                    continue
                if propose_trade_edge(sim, st, row, other):
                    events.append({
                        "kind": "trade_link_formed",
                        "a": row,
                        "b": other,
                        "distance_m": round(d, 2),
                    })

    for (a, b), e in list(st.edges.items()):
        if a >= n or b >= n:
            continue
        if not sim.agents.alive[a] or not sim.agents.alive[b]:
            continue
        delta = 0.001 * e.weight
        if e.kind == EdgeKind.FEUD:
            delta = -abs(delta)
        sim.agents.relations[a].update_affinity(b, delta)
        sim.agents.relations[b].update_affinity(a, delta)

    # Alliance crystallization after sustained positive affinity.
    if sim.tick % 20 == 0:
        for row in range(n):
            if not sim.agents.alive[row]:
                continue
            for other, aff in sim.agents.relations[row].affinity.items():
                if other >= n or not sim.agents.alive[other]:
                    continue
                if aff < ALLIANCE_AFFINITY_THRESHOLD:
                    continue
                key = (min(row, other), max(row, other))
                if key in st.edges and st.edges[key].kind == EdgeKind.ALLIANCE:
                    continue
                if aff >= ALLIANCE_AFFINITY_THRESHOLD:
                    add_edge(st, row, other, EdgeKind.ALLIANCE, weight=aff)
                    st.alliances_formed += 1
                    events.append({
                        "kind": "alliance_formed",
                        "a": row,
                        "b": other,
                        "weight": round(aff, 3),
                    })

    for topo in st.topologies.values():
        if len(topo.members) < 2:
            continue
        members = [m for m in topo.members if m < n and sim.agents.alive[m]]
        if len(members) >= 3 and sim.tick % 100 == 0:
                    events.append({
                        "kind": "topology_cohesion",
                        "topology_id": topo.topology_id,
                        "name": topo.name,
                        "size": len(members),
                    })

    from engine.trade_exchange import tick_trade_exchanges
    events.extend(tick_trade_exchanges(sim, st))

    return events


def social_topology_snapshot(sim) -> Dict[str, object]:
    st: Optional[SocialTopologyState] = getattr(sim, "_social_topology", None)
    if st is None:
        return {}
    kinds: Dict[str, int] = {}
    for e in st.edges.values():
        kinds[e.kind.name] = kinds.get(e.kind.name, 0) + 1
    return {
        "edges": len(st.edges),
        "topologies": len(st.topologies),
        "edges_by_kind": kinds,
        "topology_names": [t.name for t in st.topologies.values()],
        "trade_volume": round(st.trade_volume, 4),
        "trade_transfers": int(getattr(st, "trade_transfers", 0)),
        "trade_goods_kg": round(float(getattr(st, "trade_goods_kg", 0.0)), 4),
        "alliances_formed": st.alliances_formed,
    }


__all__ = [
    "EdgeKind",
    "SocialEdge",
    "NamedTopology",
    "SocialTopologyState",
    "install_social_topology",
    "add_edge",
    "create_topology",
    "neighbors",
    "gravity_trade_probability",
    "propose_trade_edge",
    "social_topology_snapshot",
]
