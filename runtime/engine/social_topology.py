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
    _next_topology_id: int = 1


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


def tick_social_topology(sim, st: SocialTopologyState) -> List[dict]:
    """Diffuse affinity along edges; emit topology events."""
    events: List[dict] = []
    n = sim.agents.n_active
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
    "social_topology_snapshot",
]
