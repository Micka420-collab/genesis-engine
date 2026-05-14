"""God Observer — a non-invasive divine avatar for Genesis Engine.

The GodObserver is an entity that exists outside the agent registry. It can
hover over the world, optionally manifest visibly to agents, and trigger
miraculous interventions that are journaled separately from natural events.

Design principles
-----------------
- Zero changes to the existing `AgentRegistry` schema. The avatar is its own
  object and the perception pipeline opts in to seeing it.
- Visibility is per-agent (a set of rows), with a global default toggle.
- Interventions are logged to `GodInterventionLog`, a stream distinct from
  the annalist's natural-event journal.
- Witnessed miracles are appended to `raw_events` so they flow through the
  annalist like any other in-world event, but with kind='miracle_witnessed'.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import numpy as np

try:
    # Optional — used only by the perception filter when god is visible.
    from engine.cognition import PerceivedTarget
except Exception:  # pragma: no cover — keeps the module importable standalone
    PerceivedTarget = None  # type: ignore


DIVINE_PERCEPTION_RADIUS_M = 120.0


# ---------------------------------------------------------------------------
# GodObserver
# ---------------------------------------------------------------------------

def _default_pos() -> np.ndarray:
    return np.zeros(3, dtype=np.float32)


@dataclass
class GodObserver:
    """A single divine spectator hovering above the simulated world."""
    pos: np.ndarray = field(default_factory=_default_pos)
    heading: float = 0.0
    visible: bool = False
    elevation_m: float = 200.0
    speed_ms: float = 0.0
    selected_power: str = "observe"
    intervention_count: int = 0
    visible_to_agents: Set[int] = field(default_factory=set)

    # -- movement --------------------------------------------------------
    def teleport(self, x: float, y: float, z: Optional[float] = None) -> None:
        """Move instantly to (x, y, z). z defaults to current elevation."""
        if z is None:
            z = float(self.elevation_m)
        self.pos = np.array([float(x), float(y), float(z)], dtype=np.float32)
        self.elevation_m = float(z)

    # -- visibility ------------------------------------------------------
    def set_visible(self, visible: bool) -> None:
        self.visible = bool(visible)
        if not self.visible:
            # When god hides, drop per-agent visibility too.
            self.visible_to_agents.clear()

    def reveal_to(self, row: int) -> None:
        """Make god visible to a specific agent regardless of global flag."""
        self.visible_to_agents.add(int(row))

    def hide_from(self, row: int) -> None:
        self.visible_to_agents.discard(int(row))

    def is_visible_to_row(self, row: int) -> bool:
        if int(row) in self.visible_to_agents:
            return True
        return bool(self.visible)

    # -- interventions ---------------------------------------------------
    def increment_intervention(self) -> int:
        self.intervention_count += 1
        return self.intervention_count

    # -- serialization ---------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pos": [float(self.pos[0]), float(self.pos[1]), float(self.pos[2])],
            "heading": float(self.heading),
            "visible": bool(self.visible),
            "elevation_m": float(self.elevation_m),
            "speed_ms": float(self.speed_ms),
            "selected_power": str(self.selected_power),
            "intervention_count": int(self.intervention_count),
            "visible_to_agents": sorted(int(r) for r in self.visible_to_agents),
        }


# ---------------------------------------------------------------------------
# Perception filter
# ---------------------------------------------------------------------------

def filter_god_from_perception(
    god: GodObserver,
    perception_dict: Dict[str, Any],
    *,
    row: Optional[int] = None,
    agent_pos: Optional[np.ndarray] = None,
    radius_m: float = DIVINE_PERCEPTION_RADIUS_M,
) -> Dict[str, Any]:
    """Sanitize / enrich a `nearest` perception dict for a given agent row.

    Behaviour
    ---------
    - If god is not visible to this row, scrub any divine entries from the
      perception dict (defensive — nothing should be writing them, but other
      systems may probe it).
    - If god IS visible to this row AND within radius of the agent, inject a
      `nearest['divine']` PerceivedTarget pointing at god.pos.
    """
    if perception_dict is None:
        return perception_dict

    nearest = perception_dict.get("nearest") if "nearest" in perception_dict else perception_dict

    visible = god.is_visible_to_row(row) if row is not None else bool(god.visible)

    if not visible:
        # Remove any leftover divine target — keep perception purely natural.
        if isinstance(nearest, dict) and "divine" in nearest:
            nearest.pop("divine", None)
        return perception_dict

    # Visible: compute distance and inject if in range.
    if agent_pos is None or PerceivedTarget is None:
        return perception_dict

    gx, gy = float(god.pos[0]), float(god.pos[1])
    ax, ay = float(agent_pos[0]), float(agent_pos[1])
    dist = float(np.hypot(gx - ax, gy - ay))
    if dist > radius_m:
        if isinstance(nearest, dict):
            nearest.pop("divine", None)
        return perception_dict

    if isinstance(nearest, dict):
        nearest["divine"] = PerceivedTarget(
            kind="divine", x=gx, y=gy, distance=dist, qty=1.0, other_row=None
        )
    return perception_dict


# ---------------------------------------------------------------------------
# MiracleWitness
# ---------------------------------------------------------------------------

class MiracleWitness:
    """Records which agents have witnessed which miracles.

    Witness records are emitted into `raw_events` so the annalist picks them
    up alongside births, deaths, and other natural events — they remain
    first-class history, distinct from the god intervention log (which records
    the *cause* rather than the *witnessing*).
    """

    def __init__(self) -> None:
        # row -> list of (miracle_kind, tick_or_none)
        self._witnessed: Dict[int, List[Dict[str, Any]]] = {}

    def __call__(
        self,
        agent_row: int,
        miracle_kind: str,
        pos: Any,
        *,
        tick: Optional[int] = None,
    ) -> Dict[str, Any]:
        rec = {
            "kind": "miracle_witnessed",
            "row": int(agent_row),
            "miracle": str(miracle_kind),
            "pos": [float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) > 2 else 0.0],
        }
        if tick is not None:
            rec["tick"] = int(tick)
        self._witnessed.setdefault(int(agent_row), []).append(
            {"miracle": str(miracle_kind), "tick": tick}
        )
        return rec

    def witnesses_for(self, row: int) -> List[Dict[str, Any]]:
        return list(self._witnessed.get(int(row), ()))

    def total_witnessed(self) -> int:
        return sum(len(v) for v in self._witnessed.values())


# ---------------------------------------------------------------------------
# GodInterventionLog
# ---------------------------------------------------------------------------

@dataclass
class GodIntervention:
    kind: str
    payload: Dict[str, Any]
    ts: float
    tick: Optional[int] = None
    seq: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": int(self.seq),
            "kind": str(self.kind),
            "ts": float(self.ts),
            "tick": None if self.tick is None else int(self.tick),
            "payload": self.payload,
        }


class GodInterventionLog:
    """Journal of god actions, kept distinct from the natural-event annalist."""

    def __init__(self, cap: int = 10_000) -> None:
        self._entries: List[GodIntervention] = []
        self._cap = int(cap)
        self._seq = 0

    def __len__(self) -> int:
        return len(self._entries)

    def append(
        self,
        kind: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        tick: Optional[int] = None,
    ) -> GodIntervention:
        self._seq += 1
        entry = GodIntervention(
            kind=str(kind),
            payload=dict(payload or {}),
            ts=time.time(),
            tick=tick,
            seq=self._seq,
        )
        self._entries.append(entry)
        if len(self._entries) > self._cap:
            # Drop oldest entries; keep the journal bounded.
            overflow = len(self._entries) - self._cap
            self._entries = self._entries[overflow:]
        return entry

    def recent(self, n: int = 50) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries[-int(n):]]

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e.to_dict(), separators=(",", ":")) for e in self._entries)

    def write_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for e in self._entries:
                f.write(json.dumps(e.to_dict(), separators=(",", ":")))
                f.write("\n")
