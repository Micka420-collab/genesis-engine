"""Hydrology observables for dashboard / Earth Console."""
from __future__ import annotations

from typing import Any, Dict


def hydrology_snapshot(sim) -> Dict[str, Any]:
    """Cross-chunk + macro river state (read-only)."""
    em = getattr(sim, "_emergence", None)
    ch = getattr(sim, "_chunk_hydrology_state", None)
    out: Dict[str, Any] = {
        "tick": int(sim.tick),
        "chunks_cached": len(getattr(sim.streamer, "cache", {}) or {}),
    }
    if em is not None:
        out["cross_chunk"] = {
            "mode": str(em.hydrology_mode),
            "ticks_active": int(em.hydrology_ticks),
            "pairs_exchanged": int(em.hydrology_pairs_exchanged),
            "enabled": bool(em.hydrology_cross_chunk),
        }
    if ch is not None:
        out["macro_rivers"] = {
            "chunks_processed": int(ch.chunks_processed),
            "chunks_with_river": int(ch.chunks_with_river),
            "cells_painted": int(ch.total_cells_painted),
            "threshold": float(ch.flow_acc_threshold),
        }
    return out


__all__ = ["hydrology_snapshot"]
