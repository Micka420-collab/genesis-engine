"""Macro settlement trade (Wave 30) coupled to agent social topology.

When Genesis bootstrap is present, builds settlements + road MST +
:class:`engine.trade_flow.TradeNetwork` once (refreshed periodically).
Agents are mapped to nearest macro sites; high inter-settlement flow
boosts :func:`engine.social_topology.propose_trade_edge` probability.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.road_network import build_road_network
from engine.settlement_emergence import SettlementCandidate, find_settlement_candidates
from engine.trade_flow import TradeConfig, TradeNetwork, compute_trade_flows, trade_summary


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


@dataclass
class CommerceEmergenceState:
    trade: Optional[TradeNetwork] = None
    settlements: List[SettlementCandidate] = field(default_factory=list)
    agent_to_settlement: Dict[int, int] = field(default_factory=dict)
    refresh_every: int = 400
    last_refresh_tick: int = -1
    refreshes: int = 0
    multihop_attenuation: float = 0.35
    multihop_max: int = 2


def install_commerce_emergence(sim, *, refresh_every: int = 400) -> CommerceEmergenceState:
    existing = getattr(sim, "_commerce_emergence", None)
    if existing is not None:
        return existing
    st = CommerceEmergenceState(refresh_every=max(50, int(refresh_every)))
    sim._commerce_emergence = st
    refresh_macro_trade(sim, st)
    return st


def _agent_macro_km(sim, row: int) -> tuple[float, float]:
    x_m = float(sim.agents.pos[row, 0])
    y_m = float(sim.agents.pos[row, 1])
    anchor = getattr(sim.streamer, "genesis", None)
    if anchor is not None:
        ox, oy = anchor.sim_origin_macro_km
        return ox + x_m / 1000.0, oy + y_m / 1000.0
    return x_m / 1000.0, y_m / 1000.0


def _map_agents_to_settlements(sim, st: CommerceEmergenceState) -> None:
    st.agent_to_settlement.clear()
    if not st.settlements:
        return
    n = sim.agents.n_active
    for row in range(n):
        if not sim.agents.alive[row]:
            continue
        ax, ay = _agent_macro_km(sim, row)
        best_i = -1
        best_d2 = float("inf")
        for i, c in enumerate(st.settlements):
            dx = float(c.macro_x_km) - ax
            dy = float(c.macro_y_km) - ay
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                best_i = i
        if best_i >= 0:
            st.agent_to_settlement[row] = best_i


def refresh_macro_trade(sim, st: CommerceEmergenceState) -> bool:
    """Rebuild trade network from bootstrapped Genesis world."""
    try:
        from engine.genesis_bootstrap import bootstrap_state
    except ImportError:
        return False
    bs = bootstrap_state(sim)
    if bs is None or bs.world is None:
        return False
    world = bs.world
    seed = int(sim.cfg.seed) & 0xFFFFFFFFFFFFFFFF
    settlements = find_settlement_candidates(
        world,
        n_candidates=8,
        min_spacing_km=120.0,
        seed=seed ^ 0x7A4E30,
    )
    if len(settlements) < 2:
        return False
    network = build_road_network(world, settlements)
    trade = compute_trade_flows(
        settlements, world, network, TradeConfig(max_flow_volume=100.0),
    )
    st.settlements = settlements
    st.trade = trade
    st.last_refresh_tick = sim.tick
    st.refreshes += 1
    _map_agents_to_settlements(sim, st)
    return True


def macro_trade_flow_between(st: CommerceEmergenceState, a: int, b: int) -> float:
    if st.trade is None:
        return 0.0
    ia = st.agent_to_settlement.get(a)
    ib = st.agent_to_settlement.get(b)
    if ia is None or ib is None or ia == ib:
        return 0.0
    flows = st.trade.flows
    direct = float(flows[ia, ib])
    if direct > 0.0:
        return direct
    n = int(flows.shape[0])
    atten = float(st.multihop_attenuation)
    best = 0.0
    # 1-hop via intermediate settlement k.
    for k in range(n):
        if k == ia or k == ib:
            continue
        leg1 = float(flows[ia, k])
        leg2 = float(flows[k, ib])
        if leg1 > 0.0 and leg2 > 0.0:
            via = math.sqrt(leg1 * leg2) * atten
            if via > best:
                best = via
    if best > 0.0 or int(st.multihop_max) < 2:
        return best
    # 2-hop ia → j → k → ib (sparse, capped scans).
    atten2 = atten * atten
    for j in range(n):
        if j == ia or j == ib:
            continue
        f_ij = float(flows[ia, j])
        if f_ij <= 0.0:
            continue
        for k in range(n):
            if k in (ia, ib, j):
                continue
            f_jk = float(flows[j, k])
            f_kb = float(flows[k, ib])
            if f_jk > 0.0 and f_kb > 0.0:
                via = (f_ij * f_jk * f_kb) ** (1.0 / 3.0) * atten2
                if via > best:
                    best = via
    return best


def tick_commerce_emergence(sim) -> None:
    st: Optional[CommerceEmergenceState] = getattr(sim, "_commerce_emergence", None)
    if st is None:
        return
    if st.refresh_every > 0 and sim.tick > 0 and sim.tick % st.refresh_every == 0:
        refresh_macro_trade(sim, st)
    elif sim.tick % 25 == 0:
        _map_agents_to_settlements(sim, st)


def commerce_emergence_snapshot(sim) -> Dict[str, object]:
    st: Optional[CommerceEmergenceState] = getattr(sim, "_commerce_emergence", None)
    if st is None or st.trade is None:
        return {"installed": False}
    summary = trade_summary(st.settlements, st.trade)
    return {
        "installed": True,
        "n_settlements": len(st.settlements),
        "agents_mapped": len(st.agent_to_settlement),
        "refreshes": st.refreshes,
        "last_refresh_tick": st.last_refresh_tick,
        "multihop_attenuation": st.multihop_attenuation,
        "trade": summary,
    }


__all__ = [
    "CommerceEmergenceState",
    "install_commerce_emergence",
    "refresh_macro_trade",
    "macro_trade_flow_between",
    "tick_commerce_emergence",
    "commerce_emergence_snapshot",
]
