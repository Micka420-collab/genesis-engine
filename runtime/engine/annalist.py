"""Annalist (Phase 4 — vocalize/competition/group_formed events)."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.agent import AgentRegistry, DeathCause


class EventKind(IntEnum):
    BIRTH = 1
    DEATH = 2
    INNOVATION = 3
    CONFLICT = 4
    FOUNDING = 5
    CATASTROPHE = 6
    TRADE = 7
    VOCALIZATION = 8
    BUILD = 9
    SHARE = 10
    MATING = 11
    GROUP_FORMED = 12
    COMPETITION = 13
    GROUP_DISSOLVED = 14


@dataclass
class Event:
    event_id: str
    sim_id: str
    tick: int
    kind: str
    participants: List[str]
    location: Tuple[float, float, float]
    metadata: dict

    def to_dict(self):
        return {"event_id": self.event_id, "sim_id": self.sim_id, "tick": self.tick,
                "kind": self.kind, "participants": self.participants,
                "location": list(self.location), "metadata": self.metadata}


class JsonlJournal:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._f = open(path, "a", buffering=1)
    def append(self, events):
        for e in events:
            self._f.write(json.dumps(e.to_dict(), separators=(",", ":")) + "\n")
    def close(self):
        try:
            self._f.flush(); self._f.close()
        except Exception:
            pass


@dataclass
class LineageMap:
    children: Dict[int, List[int]] = field(default_factory=dict)
    parents: Dict[int, List[int]] = field(default_factory=dict)
    def record_birth(self, child, parent_a, parent_b):
        ps = [p for p in (parent_a, parent_b) if p is not None]
        self.parents[child] = ps
        for p in ps:
            self.children.setdefault(p, []).append(child)
    def descendant_count(self, row):
        seen = set(); stack = [row]; out = 0
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for c in self.children.get(cur, []):
                out += 1; stack.append(c)
        return out


@dataclass
class Metrics:
    tick: List[int] = field(default_factory=list)
    population: List[int] = field(default_factory=list)
    births_cum: List[int] = field(default_factory=list)
    deaths_cum: List[int] = field(default_factory=list)
    avg_hunger: List[float] = field(default_factory=list)
    avg_thirst: List[float] = field(default_factory=list)
    avg_vitality: List[float] = field(default_factory=list)
    fights_cum: List[int] = field(default_factory=list)
    shares_cum: List[int] = field(default_factory=list)
    matings_cum: List[int] = field(default_factory=list)
    avg_generation: List[float] = field(default_factory=list)
    avg_affinity: List[float] = field(default_factory=list)


class Annalist:
    def __init__(self, sim_id, journal_path=None):
        self.sim_id = sim_id
        self.journal = JsonlJournal(journal_path) if journal_path else None
        self.lineage = LineageMap()
        self.metrics = Metrics()
        self.cum_births = 0
        self.cum_foundings = 0
        self.cum_deaths = 0
        self.cum_fights = 0
        self.cum_shares = 0
        self.cum_matings = 0
        self.cum_vocalizations = 0
        self.cum_competitions = 0
        self.cum_groups_formed = 0
        self.cum_groups_dissolved = 0
        self._distinct_lex_signatures = set()
        self.events_emitted = 0
        self._start_ts = time.monotonic()

    def wall_clock_s(self) -> float:
        """Seconds elapsed since this Annalist (and its sim) was constructed."""
        return float(time.monotonic() - self._start_ts)

    def close(self):
        if self.journal:
            self.journal.close()

    def record_tick(self, tick, agents, births, deaths, raw_events,
                    foundings=None):
        out = []
        for row_tuple in (foundings or []):
            row = int(row_tuple[0])
            self.cum_foundings += 1
            pos = tuple(agents.pos[row].tolist())
            out.append(self._event("founding", tick, [str(agents.uuid[row])], pos,
                                   {"generation": int(agents.generation[row]),
                                    "emergent": bool(row_tuple[1]) if len(row_tuple) > 1 else False}))
        for child, pa, pb in births:
            self.cum_births += 1
            self.lineage.record_birth(child, pa, pb)
            pos = tuple(agents.pos[child].tolist())
            participants = [str(agents.uuid[child])]
            if pa is not None: participants.append(str(agents.uuid[pa]))
            if pb is not None: participants.append(str(agents.uuid[pb]))
            out.append(self._event("birth", tick, participants, pos,
                                   {"generation": int(agents.generation[child])}))
        for row, cause in deaths:
            self.cum_deaths += 1
            pos = tuple(agents.pos[row].tolist())
            out.append(self._event("death", tick, [str(agents.uuid[row])], pos,
                                   {"cause": DeathCause(cause).name,
                                    "generation": int(agents.generation[row]),
                                    "age_ticks": int(tick - agents.born_tick[row]),
                                    "offspring_count": int(agents.offspring_count[row])}))
        for raw in raw_events:
            kind = raw.get("kind")
            if kind == "fight":
                self.cum_fights += 1
                a = raw.get("attacker"); b = raw.get("victim")
                if a is None or b is None:
                    continue
                pos = tuple(((agents.pos[a] + agents.pos[b]) * 0.5).tolist())
                out.append(self._event("conflict", tick,
                                       [str(agents.uuid[a]), str(agents.uuid[b])],
                                       pos, {"damage": float(raw.get("damage", 0))}))
            elif kind == "share":
                self.cum_shares += 1
                a = raw["from"]; b = raw["to"]
                pos = tuple(((agents.pos[a] + agents.pos[b]) * 0.5).tolist())
                out.append(self._event("share", tick,
                                       [str(agents.uuid[a]), str(agents.uuid[b])],
                                       pos, {"qty": float(raw.get("qty", 0))}))
            elif kind == "mating_success":
                self.cum_matings += 1
                a = raw["a"]; b = raw["b"]
                pos = tuple(((agents.pos[a] + agents.pos[b]) * 0.5).tolist())
                out.append(self._event("mating", tick,
                                       [str(agents.uuid[a]), str(agents.uuid[b])], pos, {}))
            elif kind == "emergent_origin":
                row = int(raw["row"])
                self.cum_foundings += 1
                pos = tuple(agents.pos[row].tolist())
                out.append(self._event("founding", tick, [str(agents.uuid[row])], pos,
                                       {"emergent": True, "substrate": float(raw.get("substrate", 0)),
                                        "founder_index": int(raw.get("founder_index", 0))}))
            elif kind == "sapient_emergence":
                row = int(raw["row"])
                self.cum_foundings += 1
                pos = tuple(agents.pos[row].tolist())
                out.append(self._event("founding", tick, [str(agents.uuid[row])], pos,
                                       {"emergent": True, "from_species": raw.get("from_species"),
                                        "oxygen_pct": float(raw.get("oxygen_pct", 0))}))
            elif kind in ("protocell_division", "microbe_emergence"):
                out.append(self._event("innovation", tick, [], (0.0, 0.0, 0.0), raw))
            elif kind == "vocalize":
                self.cum_vocalizations += 1
                a = raw["from"]; b = raw["to"]
                lex_sig = int(raw.get("lex_sig", 0))
                self._distinct_lex_signatures.add(lex_sig)
                pos = tuple(((agents.pos[a] + agents.pos[b]) * 0.5).tolist())
                out.append(self._event("vocalization", tick,
                                       [str(agents.uuid[a]), str(agents.uuid[b])],
                                       pos, {"lex_sig": lex_sig}))
            elif kind == "competition":
                self.cum_competitions += 1
                a = raw["a"]; b = raw["b"]
                pos = tuple(((agents.pos[a] + agents.pos[b]) * 0.5).tolist())
                out.append(self._event("competition", tick,
                                       [str(agents.uuid[a]), str(agents.uuid[b])], pos, {}))
            elif kind == "group_formed":
                self.cum_groups_formed += 1
                gid = int(raw.get("group_id", 0))
                members = raw.get("members", [])
                size = int(raw.get("size", len(members)))
                cx, cy = raw.get("centroid", (0.0, 0.0))
                pos = (float(cx), float(cy), 0.0)
                p_uuids = [str(agents.uuid[m]) for m in members]
                out.append(self._event("group_formed", tick, p_uuids, pos,
                                       {"group_id": gid, "size": size,
                                        "lex_sig": int(raw.get("lex_sig", 0))}))
            elif kind == "group_dissolved":
                self.cum_groups_dissolved += 1
                gid = int(raw.get("group_id", 0))
                reason = str(raw.get("reason", "unknown"))
                out.append(self._event("group_dissolved", tick, [], (0.0, 0.0, 0.0),
                                       {"group_id": gid, "reason": reason}))
            elif kind == "catastrophe":
                out.append(self._event("catastrophe", tick, [], (0.0, 0.0, 0.0), {}))

        if self.journal:
            self.journal.append(out)
        self.events_emitted += len(out)

        alive_mask = agents.alive[:agents.n_active]
        n_alive = int(alive_mask.sum())
        avg_h = float(agents.hunger[:agents.n_active][alive_mask].mean()) if n_alive > 0 else 0.0
        avg_t = float(agents.thirst[:agents.n_active][alive_mask].mean()) if n_alive > 0 else 0.0
        avg_v = float(agents.vitality[:agents.n_active][alive_mask].mean()) if n_alive > 0 else 0.0
        avg_g = float(agents.generation[:agents.n_active][alive_mask].mean()) if n_alive > 0 else 0.0
        aff_vals = []
        for r in np.flatnonzero(alive_mask)[:50]:
            for v in agents.relations[int(r)].affinity.values():
                aff_vals.append(v)
        avg_aff = float(np.mean(aff_vals)) if aff_vals else 0.0
        self.metrics.tick.append(tick)
        self.metrics.population.append(n_alive)
        self.metrics.births_cum.append(self.cum_births)
        self.metrics.deaths_cum.append(self.cum_deaths)
        self.metrics.avg_hunger.append(avg_h)
        self.metrics.avg_thirst.append(avg_t)
        self.metrics.avg_vitality.append(avg_v)
        self.metrics.fights_cum.append(self.cum_fights)
        self.metrics.shares_cum.append(self.cum_shares)
        self.metrics.matings_cum.append(self.cum_matings)
        self.metrics.avg_generation.append(avg_g)
        self.metrics.avg_affinity.append(avg_aff)
        return out

    def _event(self, kind, tick, participants, location, metadata):
        return Event(event_id=str(uuid.uuid4()), sim_id=self.sim_id, tick=tick,
                     kind=kind, participants=participants,
                     location=tuple(location), metadata=metadata)

    def metrics_to_dict(self):
        return {
            "tick": self.metrics.tick, "population": self.metrics.population,
            "births_cum": self.metrics.births_cum, "deaths_cum": self.metrics.deaths_cum,
            "avg_hunger": self.metrics.avg_hunger, "avg_thirst": self.metrics.avg_thirst,
            "avg_vitality": self.metrics.avg_vitality,
            "fights_cum": self.metrics.fights_cum, "shares_cum": self.metrics.shares_cum,
            "matings_cum": self.metrics.matings_cum,
            "avg_generation": self.metrics.avg_generation,
            "avg_affinity": self.metrics.avg_affinity,
            "vocalizations_cum": int(self.cum_vocalizations),
            "competitions_cum": int(self.cum_competitions),
            "groups_formed_cum": int(self.cum_groups_formed),
            "groups_dissolved_cum": int(self.cum_groups_dissolved),
            "distinct_lex_signatures": len(self._distinct_lex_signatures),
            "events_emitted": int(self.events_emitted),
            "elapsed_s": time.monotonic() - self._start_ts,
        }
