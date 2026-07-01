"""Genesis Engine — Wave 66 endorheic depression & lake hydrology observer.

Read-only detection of the **lakes the terrain itself would hold**. The
substrate already routes water down the D8 network
(:mod:`engine.discharge_observer`, Wave 53 / :mod:`engine.river_discharge`,
Wave 64), and :mod:`engine.world_genesis` already marks **interior pits**
(``flow_dir == 255`` where ``best_drop <= 0`` above sea level) — closed-basin
bottoms with no downhill neighbour. But **nothing ever turns those pits into
lakes**: the discharge router treats an interior sink as water *leaving the
domain*, when physically the water **pools** there. This module is the missing
read: it computes, from the bare topography, where a closed depression would
fill to and how deep — the **depression-storage capacity** of the world, and
the emergent lakes and endorheic (terminal) basins that storage implies.

Algorithm — Priority-Flood (Barnes, Lehman & Mulla 2014)
--------------------------------------------------------

Priority-Flood (*Computers & Geosciences*, arXiv 1511.04463) is the optimal
depression-filling algorithm: flood the DEM **inward from its edges** using a
min-priority queue keyed by spill elevation. When a cell is first reached, its
**filled** height is ``max(own_elevation, level_it_was_reached_at)`` — the
lowest water level at which it connects to a free drain. The result:

* ``filled >= elev`` everywhere (filling only raises);
* ``filled == elev`` on every free drain (domain border **and** ocean cells,
  which are seeded as always-draining);
* ``depth = filled - elev`` is exactly the water a closed basin would hold if
  it filled to its lowest **sill** (spill point) — the depression-storage
  field, a standard DEM hydrology product.

Because the flood escapes each basin only over its lowest sill, **every cell of
one connected depression shares a single spill level**: the lake surface is
*flat* (water finds its level). That is the module's headline invariant.

What it measures (all emergent, classical hydrology)
----------------------------------------------------

1. **Filled surface** and the **depth field** ``filled - elev``.
2. **Lakes** — 8-connected components of ``depth > eps`` (land only). Per lake:
   area, surface (spill) elevation, bottom elevation, max/mean depth, impounded
   **volume** (m³), centroid.
3. **Endorheic classification** — a lake is *terminal* when it contains an
   interior D8 sink (the world's own routing dead-ends into it). This is the
   cross-check between two independent derivations (Priority-Flood sills vs.
   the ``flow_dir`` pits) and the seed of the salt story (an outlet-less lake
   concentrates salinity — cf. :mod:`engine.salt_evaporation` C15, not wired
   here).

The finite-volume partner — **Fill–Spill–Merge** (Barnes, Callaghan & Wickert,
*ESurf* 2021), which distributes the *actual* routed runoff (Wave 64) across
the depression hierarchy so lakes fill only as much as their inflow allows —
is deliberately **backlog (Wave 67)**: Priority-Flood supplies the *containers*
(max-extent lakes); FSM will later fill them with real water.

Observer contract (mirrors Waves 45 / 49 / 50 / 53 / 62 / 63)
-------------------------------------------------------------

- ``LakeConfig`` / ``Lake`` / ``LakeSnapshot`` / ``LakeHistory`` /
  ``LakeState`` dataclasses (frozen where they carry data).
- ``lakes_from_elevation`` / ``lakes_from_world`` — **pure**, no sim needed.
- ``observe_lakes(sim, cfg)`` — read-only, resolves the world, returns a snap.
- ``install_lake_observer(sim, cfg)`` — idempotent, wraps ``sim.step`` to
  snapshot every ``snapshot_every`` ticks.
- ``uninstall_lake_observer(sim)`` — restores ``sim.step``.
- ``lake_summary(sim)`` — diagnostic dict for dashboards.

Determinism
-----------

No RNG (numpy + ``heapq`` only). Priority-queue ties break by a monotonic
insertion counter, connected-component labelling is row-major, and the
signature is ``sha256`` of a canonical tuple — two runs on the same world seed
produce identical snapshots.

Stone-age compliance
--------------------

The observer never *declares* a lake — it reads the elevation the world already
eroded and reports where water would stand. No mutation of any world/sim array,
no new cross-language tell (``PY_TO_RUST`` unchanged — this is substrate
physics, not an agent capability).
"""
from __future__ import annotations

import hashlib
import heapq
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# D8 convention matches engine.world_genesis / engine.discharge_observer:
# 0..7 = E, SE, S, SW, W, NW, N, NE ; 255 = sink (ocean or interior pit).
_D8_DX = np.array([1, 1, 0, -1, -1, -1, 0, 1], dtype=np.int8)
_D8_DY = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=np.int8)
_D8_SINK = 255

# ADR-0005 pipeline tags (mirror discharge_observer / river_discharge).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LakeConfig:
    """Read-only knobs for the depression / lake observer."""
    snapshot_every: int = 64
    # A cell counts as submerged only when the terrain would hold at least this
    # much water over it — filters numerical fuzz and puddles below relief.
    depth_eps_m: float = 0.5
    # Discard lake components smaller than this many cells (spurious 1-px sills).
    min_lake_cells: int = 2
    top_lakes: int = 5
    default_sea_level_m: float = 0.0   # fallback if the world exposes none


@dataclass(frozen=True)
class Lake:
    """One emergent lake (connected closed-depression pool), read-only."""
    lake_id: int
    n_cells: int
    area_km2: float
    surface_elev_m: float       # spill elevation = flat lake surface
    bottom_elev_m: float        # deepest submerged terrain
    max_depth_m: float
    mean_depth_m: float
    volume_m3: float
    centroid_yx: Tuple[int, int]
    deepest_yx: Tuple[int, int]
    is_endorheic: bool          # contains an interior D8 sink (terminal basin)


@dataclass(frozen=True)
class LakeSnapshot:
    """Global + top-K lake snapshot at a given sim tick."""
    tick: int
    cell_km: float
    land_cells: int
    n_lakes: int
    n_lakes_considered: int
    n_endorheic: int
    total_lake_area_km2: float
    lake_area_fraction_land: float
    total_impounded_volume_m3: float
    max_lake_depth_m: float
    largest_lake_area_km2: float
    lakes_top: Tuple[Lake, ...]
    signature: str


@dataclass
class LakeHistory:
    snapshots: List[LakeSnapshot] = field(default_factory=list)


@dataclass
class LakeState:
    config: LakeConfig
    history: LakeHistory = field(default_factory=LakeHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# Pure algorithm — Priority-Flood depression fill
# ---------------------------------------------------------------------------

def _seed_mask(elev: np.ndarray, sea_level_m: float) -> np.ndarray:
    """Free-drain seed cells: the domain border **and** all ocean cells.

    Seeding ocean (``elev <= sea_level``) as always-draining means a land basin
    that spills into the sea is *not* impounded — only genuinely closed basins
    above sea level pool into lakes.
    """
    R0, R1 = elev.shape
    seed = np.zeros((R0, R1), dtype=bool)
    seed[0, :] = True
    seed[-1, :] = True
    seed[:, 0] = True
    seed[:, -1] = True
    seed |= (elev <= np.float64(sea_level_m))
    return seed


def priority_flood_fill(elev: np.ndarray,
                        seed_mask: Optional[np.ndarray] = None,
                        sea_level_m: float = 0.0) -> np.ndarray:
    """Priority-Flood filled surface (Barnes, Lehman & Mulla 2014).

    Floods inward from ``seed_mask`` (defaults to border ∪ ocean) with a min
    priority queue keyed on spill elevation. Returns ``filled`` (float64),
    ``filled >= elev`` everywhere and ``== elev`` on every seed / free drain.

    Deterministic: heap ties break by a monotonic insertion counter; the
    per-cell first discovery is via its minimal spill path (queue is processed
    in non-decreasing spill order), so results are reproducible and correct.
    """
    elev = np.asarray(elev, dtype=np.float64)
    if elev.ndim != 2:
        raise ValueError("elev must be a 2-D array")
    R0, R1 = elev.shape
    if seed_mask is None:
        seed_mask = _seed_mask(elev, sea_level_m)
    else:
        seed_mask = np.asarray(seed_mask, dtype=bool)
        if seed_mask.shape != elev.shape:
            raise ValueError("seed_mask must share shape with elev")

    filled = elev.copy()
    closed = np.zeros((R0, R1), dtype=bool)
    pq: List[Tuple[float, int, int, int]] = []
    seq = 0

    ys, xs = np.nonzero(seed_mask)
    for y, x in zip(ys.tolist(), xs.tolist()):
        if closed[y, x]:
            continue
        closed[y, x] = True
        heapq.heappush(pq, (float(elev[y, x]), seq, int(y), int(x)))
        seq += 1

    dys = _D8_DY.tolist()
    dxs = _D8_DX.tolist()
    while pq:
        level, _s, y, x = heapq.heappop(pq)
        for k in range(8):
            ny = y + dys[k]
            nx = x + dxs[k]
            if ny < 0 or ny >= R0 or nx < 0 or nx >= R1:
                continue
            if closed[ny, nx]:
                continue
            closed[ny, nx] = True
            ev = float(elev[ny, nx])
            nl = ev if ev > level else level
            filled[ny, nx] = nl
            heapq.heappush(pq, (nl, seq, ny, nx))
            seq += 1

    return filled


def _label_components(mask: np.ndarray) -> Tuple[np.ndarray, int]:
    """Row-major, 8-connected connected-component labelling (numpy-only).

    Returns ``(labels, n)`` where ``labels`` is int32 with ``0`` = background
    and ``1..n`` the components in row-major discovery order (deterministic).
    """
    R0, R1 = mask.shape
    labels = np.zeros((R0, R1), dtype=np.int32)
    n = 0
    dys = _D8_DY.tolist()
    dxs = _D8_DX.tolist()
    for y in range(R0):
        for x in range(R1):
            if not mask[y, x] or labels[y, x] != 0:
                continue
            n += 1
            labels[y, x] = n
            stack = [(y, x)]
            while stack:
                cy, cx = stack.pop()
                for k in range(8):
                    ny = cy + dys[k]
                    nx = cx + dxs[k]
                    if ny < 0 or ny >= R0 or nx < 0 or nx >= R1:
                        continue
                    if mask[ny, nx] and labels[ny, nx] == 0:
                        labels[ny, nx] = n
                        stack.append((ny, nx))
    return labels, n


# ---------------------------------------------------------------------------
# Pure core — lakes from an elevation field
# ---------------------------------------------------------------------------

def lakes_from_elevation(elev: np.ndarray,
                         *,
                         cell_km: float,
                         sea_level_m: float = 0.0,
                         flow_dir: Optional[np.ndarray] = None,
                         config: Optional[LakeConfig] = None,
                         ) -> Tuple[np.ndarray, np.ndarray, List[Lake]]:
    """Compute ``(filled, depth, lakes)`` from a bare elevation field.

    ``flow_dir`` (optional, the world's D8 field) enables the endorheic flag:
    a lake containing a ``255`` interior sink is a terminal basin. Pure /
    deterministic; no sim, no mutation.
    """
    cfg = config if config is not None else LakeConfig()
    elev = np.asarray(elev, dtype=np.float64)
    filled = priority_flood_fill(elev, sea_level_m=sea_level_m)
    depth = np.maximum(filled - elev, 0.0)

    land = elev > np.float64(sea_level_m)
    lake_mask = (depth > np.float64(cfg.depth_eps_m)) & land
    labels, n = _label_components(lake_mask)

    cell_area_m2 = (float(cell_km) * 1000.0) ** 2
    cell_area_km2 = float(cell_km) * float(cell_km)

    fd = None
    if flow_dir is not None:
        fd = np.asarray(flow_dir, dtype=np.uint8)
        if fd.shape != elev.shape:
            fd = None

    lakes: List[Lake] = []
    for lid in range(1, n + 1):
        comp = labels == lid
        n_cells = int(comp.sum())
        if n_cells < cfg.min_lake_cells:
            continue
        d = depth[comp]
        e = elev[comp]
        f = filled[comp]
        # Deepest submerged cell (emergent lake bottom / pour point).
        comp_depth = np.where(comp, depth, -1.0)
        flat = int(comp_depth.argmax())
        dy, dx = divmod(flat, elev.shape[1])
        ys, xs = np.nonzero(comp)
        cyx = (int(round(float(ys.mean()))), int(round(float(xs.mean()))))
        endorheic = bool(fd is not None and np.any(fd[comp] == _D8_SINK))

        lakes.append(Lake(
            lake_id=lid,
            n_cells=n_cells,
            area_km2=float(n_cells) * cell_area_km2,
            surface_elev_m=float(f.max()),   # flat surface: max == min == spill
            bottom_elev_m=float(e.min()),
            max_depth_m=float(d.max()),
            mean_depth_m=float(d.mean()),
            volume_m3=float(d.sum()) * cell_area_m2,
            centroid_yx=cyx,
            deepest_yx=(int(dy), int(dx)),
            is_endorheic=endorheic,
        ))

    return filled, depth, lakes


# ---------------------------------------------------------------------------
# World resolution (read-only) — mirrors discharge_observer
# ---------------------------------------------------------------------------

def _resolve_world(sim) -> Optional[Any]:
    """Return the :class:`GenesisWorld` attached to ``sim``, or ``None``."""
    ch = getattr(sim, "_chunk_hydrology_state", None)
    if ch is not None and getattr(ch, "anchor", None) is not None:
        w = getattr(ch.anchor, "world", None)
        if w is not None:
            return w
    boot = getattr(sim, "_genesis_bootstrap_state", None)
    if boot is not None:
        w = getattr(boot, "world", None)
        if w is not None:
            return w
        a = getattr(boot, "anchor", None)
        if a is not None and getattr(a, "world", None) is not None:
            return a.world
    streamer = getattr(sim, "streamer", None)
    if streamer is not None:
        genesis = getattr(streamer, "genesis", None)
        if genesis is not None and getattr(genesis, "world", None) is not None:
            return genesis.world
    anchor = getattr(sim, "_genesis_anchor", None)
    if anchor is not None and getattr(anchor, "world", None) is not None:
        return anchor.world
    return getattr(sim, "_genesis_world", None)


# ---------------------------------------------------------------------------
# Snapshot / signature
# ---------------------------------------------------------------------------

def _snapshot_signature(snap_seed: Tuple[Any, ...]) -> str:
    """sha256 of a canonical, language-neutral tuple representation."""
    return hashlib.sha256(repr(snap_seed).encode("utf-8")).hexdigest()


def lakes_from_world(world, config: Optional[LakeConfig] = None,
                     tick: int = 0) -> LakeSnapshot:
    """Pure read-only lake snapshot from a :class:`GenesisWorld`."""
    cfg = config if config is not None else LakeConfig()
    elev = np.asarray(world.elevation_m, dtype=np.float64)
    R = int(elev.shape[0])
    sea = float(getattr(getattr(world, "params", None), "sea_level_m",
                        cfg.default_sea_level_m))
    map_km = float(getattr(getattr(world, "params", None), "map_size_km",
                           float(R)))
    cell_km = map_km / float(R) if R else 1.0
    flow_dir = getattr(world, "flow_dir", None)

    filled, depth, lakes = lakes_from_elevation(
        elev, cell_km=cell_km, sea_level_m=sea,
        flow_dir=flow_dir, config=cfg)

    land_cells = int((elev > sea).sum())
    cell_area_km2 = cell_km * cell_km
    total_area = float(sum(lk.area_km2 for lk in lakes))
    total_volume = float(sum(lk.volume_m3 for lk in lakes))
    n_endorheic = int(sum(1 for lk in lakes if lk.is_endorheic))
    max_depth = float(max((lk.max_depth_m for lk in lakes), default=0.0))
    land_area_km2 = float(land_cells) * cell_area_km2
    area_frac = (total_area / land_area_km2) if land_area_km2 > 0 else 0.0

    ranked = sorted(lakes, key=lambda lk: (-lk.volume_m3, lk.lake_id))
    top = tuple(ranked[:cfg.top_lakes])
    largest_area = float(max((lk.area_km2 for lk in lakes), default=0.0))

    canonical = tuple(
        (lk.lake_id, lk.n_cells, round(lk.area_km2, 4),
         round(lk.surface_elev_m, 3), round(lk.bottom_elev_m, 3),
         round(lk.max_depth_m, 3), round(lk.mean_depth_m, 3),
         round(lk.volume_m3, 2), lk.centroid_yx, lk.deepest_yx,
         lk.is_endorheic)
        for lk in sorted(lakes, key=lambda lk: lk.lake_id)
    )
    sig = _snapshot_signature((
        int(tick), round(cell_km, 6), land_cells, len(lakes), n_endorheic,
        round(total_area, 4), round(area_frac, 6), round(total_volume, 2),
        round(max_depth, 3), round(largest_area, 4), canonical,
    ))

    return LakeSnapshot(
        tick=int(tick),
        cell_km=cell_km,
        land_cells=land_cells,
        n_lakes=len(lakes),
        n_lakes_considered=len(lakes),
        n_endorheic=n_endorheic,
        total_lake_area_km2=total_area,
        lake_area_fraction_land=float(area_frac),
        total_impounded_volume_m3=total_volume,
        max_lake_depth_m=max_depth,
        largest_lake_area_km2=largest_area,
        lakes_top=top,
        signature=sig,
    )


def observe_lakes(sim, config: Optional[LakeConfig] = None
                  ) -> Optional[LakeSnapshot]:
    """Pure read-only lake snapshot for ``sim``. ``None`` if no world wired."""
    cfg = config if config is not None else LakeConfig()
    world = _resolve_world(sim)
    if world is None:
        return None
    try:
        tick = int(sim.tick)
    except Exception:
        tick = 0
    return lakes_from_world(world, cfg, tick=tick)


# ---------------------------------------------------------------------------
# Install / uninstall (mirrors wave 53 / 62 / 63)
# ---------------------------------------------------------------------------

def install_lake_observer(sim, config: Optional[LakeConfig] = None
                          ) -> LakeState:
    """Idempotent installer. Wraps ``sim.step`` once to capture a snapshot
    every ``cfg.snapshot_every`` ticks."""
    cfg = config if config is not None else LakeConfig()
    existing: Optional[LakeState] = getattr(sim, "_lake_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = LakeState(config=cfg)
    sim._lake_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_lakes(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._lake_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._lake_wrapped = True
    return state


def uninstall_lake_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_lake_state", None)
    if state is None:
        return False
    original = getattr(sim, "_lake_original_step", None)
    if original is not None:
        sim.step = original
        del sim._lake_original_step
    sim._lake_wrapped = False
    del sim._lake_state
    return True


def lake_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards (does not mutate sim)."""
    state: Optional[LakeState] = getattr(sim, "_lake_state", None)
    if state is None:
        return {"installed": False}
    snaps = state.history.snapshots
    last = snaps[-1] if snaps else None
    return {
        "installed": True,
        "n_snapshots": len(snaps),
        "snapshot_every": state.config.snapshot_every,
        "last_signature": (last.signature if last is not None else None),
        "last_tick": (last.tick if last is not None else None),
        "n_lakes": (last.n_lakes if last is not None else None),
        "n_endorheic": (last.n_endorheic if last is not None else None),
        "total_impounded_volume_m3": (last.total_impounded_volume_m3
                                      if last is not None else None),
        "total_lake_area_km2": (last.total_lake_area_km2
                                if last is not None else None),
        "max_lake_depth_m": (last.max_lake_depth_m
                             if last is not None else None),
    }


__all__ = [
    "LakeConfig",
    "Lake",
    "LakeSnapshot",
    "LakeHistory",
    "LakeState",
    "priority_flood_fill",
    "lakes_from_elevation",
    "lakes_from_world",
    "observe_lakes",
    "install_lake_observer",
    "uninstall_lake_observer",
    "lake_summary",
]
