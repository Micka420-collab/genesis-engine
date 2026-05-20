"""Enrich experiment artifacts after a ``run.py`` session."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _journal_trade_count(journal_path: Optional[str]) -> int:
    if not journal_path or not Path(journal_path).is_file():
        return 0
    count = 0
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("kind") == "trade":
                count += 1
    return count


def _jsonl_line_count(path: Optional[str]) -> int:
    if not path or not Path(path).is_file():
        return 0
    with open(path, encoding="utf-8") as fh:
        return sum(1 for ln in fh if ln.strip())


def enrich_run_summary(sim, summary: Dict[str, Any]) -> Dict[str, Any]:
    """Attach snapshots, journal stats, and stack diagnostics."""
    out = dict(summary)
    snap = sim.snapshot()

    if snap.get("emergence"):
        out.setdefault("emergence", snap["emergence"])
    if snap.get("life_emergence"):
        out["life_emergence"] = snap["life_emergence"]
    if snap.get("knowledge_layers"):
        out["knowledge_layers"] = snap["knowledge_layers"]

    journal = out.get("journal")
    out["journal_stats"] = {
        "trade_events": _journal_trade_count(journal),
        "annalist_cum_trades": int(getattr(sim.annalist, "cum_trades", 0)),
    }

    observe_jsonl = out.get("observe_jsonl")
    if observe_jsonl:
        out["observe_stats"] = {
            "jsonl_lines": _jsonl_line_count(observe_jsonl),
            "path": observe_jsonl,
        }

    stack_notes: List[str] = []
    if getattr(sim, "_genesis_bootstrap_state", None) is not None:
        stack_notes.append("genesis")
    if getattr(sim, "_rust_worldgraph", None) is not None:
        stack_notes.append("rust_worldgraph")
    if getattr(sim, "_commerce_emergence", None) is not None:
        stack_notes.append("macro_commerce")
    if getattr(sim, "_5cd_installed", False):
        stack_notes.append("5cd")
    out["stack_active"] = stack_notes

    out["report_schema"] = "genesis.run_report/v1"
    return out


__all__ = ["enrich_run_summary"]
