"""Agent batch hot path — packed snapshots + optional WebGPU-friendly layout.

Python ECS fallback until Rust ``bevy_ecs`` is on the gameplay loop.
"""
from __future__ import annotations

import base64
import struct
from typing import Any, Dict, List, Tuple

import numpy as np

# row, x, y, culture, action, gen
PACK_FORMAT = "<IffIII"
PACK_SIZE = struct.calcsize(PACK_FORMAT)


def pack_agents_binary(sim) -> bytes:
    """Dense binary blob for GPU instancing / fast client decode."""
    a = sim.agents
    n = int(a.n_active)
    if n == 0:
        return b""
    alive = np.flatnonzero(a.alive[:n])
    chunks: List[bytes] = []
    for row in alive:
        row = int(row)
        chunks.append(struct.pack(
            PACK_FORMAT,
            row,
            float(a.pos[row, 0]),
            float(a.pos[row, 1]),
            int(a.relations[row].culture_id),
            int(a.action[row]) if hasattr(a, "action") else 0,
            int(a.generation[row]),
        ))
    return b"".join(chunks)


def unpack_agents_binary(blob: bytes) -> List[Dict[str, Any]]:
    agents: List[Dict[str, Any]] = []
    if not blob:
        return agents
    nrec = len(blob) // PACK_SIZE
    for i in range(nrec):
        off = i * PACK_SIZE
        row, x, y, c, act, g = struct.unpack_from(PACK_FORMAT, blob, off)  # type: ignore[misc]
        agents.append({
            "row": int(row),
            "x": float(x),
            "y": float(y),
            "c": int(c),
            "a": int(act),
            "g": int(g),
        })
    return agents


def snapshot_agents_packed(sim) -> Dict[str, Any]:
    """API payload: base64 binary + count."""
    raw = pack_agents_binary(sim)
    return {
        "tick": int(sim.tick),
        "count": len(raw) // PACK_SIZE if raw else 0,
        "record_bytes": PACK_SIZE,
        "data_b64": base64.b64encode(raw).decode("ascii") if raw else "",
    }


def batch_alive_count(sim) -> int:
    a = sim.agents
    return int(np.sum(a.alive[: a.n_active]))


__all__ = [
    "PACK_FORMAT",
    "PACK_SIZE",
    "pack_agents_binary",
    "unpack_agents_binary",
    "snapshot_agents_packed",
    "batch_alive_count",
]
