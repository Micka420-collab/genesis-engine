"""Bilateral resource exchange along TRADE social edges.

Complements :mod:`engine.social_topology` link formation with actual
inventory transfers (food ↔ stone/metal) when agents are in range.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from engine.social_topology import EdgeKind


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

TRADE_RANGE_M = 30.0
TRADE_TICK_INTERVAL = 10
TRANSFER_LOSS = 0.05
BASE_TRANSFER_KG = 0.04


def _craft_stock(agents, row: int) -> float:
    total = float(agents.inv_stone[row]) + float(agents.inv_metal[row])
    for fld in ("inv_copper", "inv_tin", "inv_bronze"):
        arr = getattr(agents, fld, None)
        if arr is not None:
            total += float(arr[row])
    return total


def _wood_stock(agents, row: int) -> float:
    return float(agents.inv_wood[row])


def _transfer_amount(
    edge_weight: float,
    macro_flow: float,
    available: float,
) -> float:
    scale = (1.0 + float(edge_weight)) * (1.0 + float(macro_flow) / 100.0)
    return min(available * 0.12, BASE_TRANSFER_KG * scale)


def execute_bilateral_trade(
    sim,
    a: int,
    b: int,
    *,
    edge_weight: float = 0.5,
    macro_flow: float = 0.0,
) -> Optional[Dict[str, float]]:
    """Move goods along complementarity; returns transfer dict or None."""
    agents = sim.agents
    if not agents.alive[a] or not agents.alive[b]:
        return None

    food_a = float(agents.inv_food[a])
    food_b = float(agents.inv_food[b])
    water_a = float(agents.inv_water[a])
    water_b = float(agents.inv_water[b])
    craft_a = _craft_stock(agents, a)
    craft_b = _craft_stock(agents, b)
    wood_a = _wood_stock(agents, a)
    wood_b = _wood_stock(agents, b)

    out: Dict[str, float] = {}

    def _move_field(donor: int, recv: int, field: str, key: str,
                    min_avail: float) -> None:
        arr = getattr(agents, field)
        avail = float(arr[donor])
        if avail < min_avail:
            return
        amt = _transfer_amount(edge_weight, macro_flow, avail)
        if amt <= 1e-6:
            return
        delivered = amt * (1.0 - TRANSFER_LOSS)
        arr[donor] = max(0.0, avail - amt)
        arr[recv] = float(arr[recv]) + delivered
        out[key] = round(delivered, 5)

    if food_a > 0.3 and craft_b > 0.08 and food_b < 0.6:
        _move_field(a, b, "inv_food", "food_a_to_b", 0.25)
    if food_b > 0.3 and craft_a > 0.08 and food_a < 0.6:
        _move_field(b, a, "inv_food", "food_b_to_a", 0.25)
    if craft_a > 0.15 and food_b > 0.2 and craft_b < 0.2:
        _move_field(a, b, "inv_stone", "stone_a_to_b", 0.08)
    if craft_b > 0.15 and food_a > 0.2 and craft_a < 0.2:
        _move_field(b, a, "inv_stone", "stone_b_to_a", 0.08)
    if water_a > 0.35 and water_b < 0.2:
        _move_field(a, b, "inv_water", "water_a_to_b", 0.3)
    if water_b > 0.35 and water_a < 0.2:
        _move_field(b, a, "inv_water", "water_b_to_a", 0.3)
    if wood_a > 0.18 and food_b > 0.15 and wood_b < 0.12:
        _move_field(a, b, "inv_wood", "wood_a_to_b", 0.15)
    if wood_b > 0.18 and food_a > 0.15 and wood_a < 0.12:
        _move_field(b, a, "inv_wood", "wood_b_to_a", 0.15)

    return out if out else None


def tick_trade_exchanges(sim, st) -> List[dict]:
    """Run transfers on all TRADE edges within range (called from social tick)."""
    if sim.tick % TRADE_TICK_INTERVAL != 0:
        return []

    events: List[dict] = []
    n = sim.agents.n_active
    ce = getattr(sim, "_commerce_emergence", None)

    for (a, b), edge in list(st.edges.items()):
        if edge.kind != EdgeKind.TRADE:
            continue
        if a >= n or b >= n or not sim.agents.alive[a] or not sim.agents.alive[b]:
            continue
        px, py = float(sim.agents.pos[a, 0]), float(sim.agents.pos[a, 1])
        dist = math.hypot(
            float(sim.agents.pos[b, 0]) - px,
            float(sim.agents.pos[b, 1]) - py,
        )
        if dist > TRADE_RANGE_M:
            continue

        macro_flow = 0.0
        if ce is not None:
            from engine.commerce_emergence import macro_trade_flow_between

            macro_flow = macro_trade_flow_between(ce, a, b)

        xfer = execute_bilateral_trade(
            sim, a, b, edge_weight=edge.weight, macro_flow=macro_flow,
        )
        if not xfer:
            continue

        goods = sum(xfer.values())
        st.trade_goods_kg = getattr(st, "trade_goods_kg", 0.0) + goods
        st.trade_transfers = getattr(st, "trade_transfers", 0) + 1

        events.append({
            "kind": "trade_transfer",
            "a": a,
            "b": b,
            "distance_m": round(dist, 2),
            "macro_flow": round(macro_flow, 3),
            "goods_kg": round(goods, 4),
            "legs": xfer,
        })

    return events


__all__ = [
    "TRADE_RANGE_M",
    "execute_bilateral_trade",
    "tick_trade_exchanges",
]
