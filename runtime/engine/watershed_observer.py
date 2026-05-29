"""Genesis Engine — Wave 49 watershed / Strahler stream order observer.

Read-only quantification of the emergent drainage network built by
:mod:`engine.world_genesis` (D8 ``flow_dir`` + ``flow_acc`` + ``river_mask``
+ ``watershed_id``). No mutation, no RNG, no ontology imposed on the
landscape: every metric is computed from the topology already present in
the macro world.

Three families of measures, all classical fluvial geomorphology:

1. **Strahler stream order** — recursive ordering of the river network
   (Horton-Strahler, 1957). A headwater is order 1. When two streams of
   equal order *k* merge, the downstream segment becomes order *k+1*;
   when a higher-order stream is joined by a lower-order tributary the
   higher order is retained.

2. **Drainage density** ``Dd = L_river / A_basin`` (km / km²). Direct
   proxy for runoff efficiency. A humid basin has Dd ~ 2-5 km/km², an
   arid one ~ 0.5.

3. **Horton ratios** computed across the whole map :
   - **Bifurcation ratio** ``Rb = N_k / N_{k+1}`` (count of streams of
     order *k* vs *k+1*). Natural networks fall in 3-5.
   - **Length ratio** ``Rl = L̄_{k+1} / L̄_k``. Natural networks ~ 1.5-3.

A **basin** is whatever ``world.watershed_id`` says it is — the observer
neither labels nor merges basins.

Observer contract (mirrors Waves 39 / 40 / 45)
----------------------------------------------

- ``WatershedConfig`` / ``WatershedSnapshot`` / ``WatershedHistory`` /
  ``WatershedState`` dataclasses.
- ``observe_watersheds(sim, cfg)`` — **read-only**, returns a snapshot.
- ``install_watershed_observer(sim, cfg)`` — idempotent, wraps
  ``sim.step`` so a snapshot is captured every ``snapshot_every`` ticks.
- ``uninstall_watershed_observer(sim)`` — restores the original
  ``sim.step``.
- ``watershed_summary(sim)`` — diagnostic dict for dashboards.

Determinism
-----------

No RNG. The signature is ``sha256`` of a canonical tuple built from
sorted basin stats and the integer stream-order histogram, so two runs
with the same world seed produce identical snapshot streams.

Stone-age compliance
--------------------

The observer never declares basins, rivers, watersheds — only reads what
the D8 flow graph emergent from elevation already encodes. No script
fixes Strahler orders. No mutation of any world or sim array.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# D8 convention matches engine.world_genesis (do NOT redefine differently).
_D8_DX = np.array([1, 1, 0, -1, -1, -1, 0, 1], dtype=np.int8)
_D8_DY = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=np.int8)
_D8_LEN = np.array([1.0, math.sqrt(2.0), 1.0, math.sqrt(2.0),
                    1.0, math.sqrt(2.0), 1.0, math.sqrt(2.0)],
                   dtype=np.float32)
_D8_SINK = 255  # convention used by world_genesis flow_dir


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WatershedConfig:
    """Read-only knobs for the watershed observer."""
    snapshot_every: int = 64
    min_basin_cells: int = 4
    top_basins: int = 5
    max_strahler_order: int = 12  # hard cap, anything above is folded


@dataclass(frozen=True)
class BasinStats:
    """Per-basin emergent statistics (read-only)."""
    basin_id: int
    n_cells: int
    n_river_cells: int
    area_km2: float
    river_length_km: float
    drainage_density: float            # km / km²
    max_strahler: int
    outlet_yx: Tuple[int, int]
    mean_elev_m: float
    min_elev_m: float
    max_elev_m: float
    hypsometric_integral: float        # (mean - min) / (max - min) ∈ [0, 1]


@dataclass(frozen=True)
class WatershedSnapshot:
    """Global + top-K basin snapshot at a given sim tick."""
    tick: int
    map_area_km2: float
    cell_km: float
    n_basins_total: int
    n_basins_considered: int
    total_river_cells: int
    total_river_length_km: float
    global_drainage_density: float
    bifurcation_ratio: float
    length_ratio: float
    stream_order_counts: Dict[int, int]
    basins_top: Tuple[BasinStats, ...]
    signature: str


@dataclass
class WatershedHistory:
    snapshots: List[WatershedSnapshot] = field(default_factory=list)


@dataclass
class WatershedState:
    config: WatershedConfig
    history: WatershedHistory = field(default_factory=WatershedHistory)
    wrapped: bool = False
    last_world_seed: Optional[int] = None


# ---------------------------------------------------------------------------
# World access (read-only)
# ---------------------------------------------------------------------------

def _resolve_world(sim) -> Optional[Any]:
    """Return the :class:`GenesisWorld` attached to ``sim``, or ``None``.

    Tries (in order) :

    1. ``sim._chunk_hydrology_state.anchor.world`` (Wave 18 install path).
    2. ``sim._genesis_bootstrap_state.world`` (canonical bootstrap path).
    3. ``sim._genesis_bootstrap_state.anchor.world`` (bootstrap fallback).
    4. ``sim.streamer.genesis.world`` (streamer-level anchor).
    5. ``sim._genesis_anchor.world`` / ``sim._genesis_world`` (legacy).
    """
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
# Pure-function geomorphology
# ---------------------------------------------------------------------------

def compute_strahler_order(flow_dir: np.ndarray,
                            river_mask: np.ndarray,
                            *,
                            max_order: int = 12) -> np.ndarray:
    """Strahler stream order for every river cell.

    Returns an int32 array of the same shape as ``flow_dir`` with
    ``order[y, x] == 0`` for non-river cells and ``order[y, x] >= 1``
    for river cells. Topological order is enforced via Kahn's algorithm
    on the D8 downstream graph restricted to river cells.

    Parameters
    ----------
    flow_dir
        ``(R, R)`` uint8 D8 direction (0..7), ``255`` = sink/ocean.
    river_mask
        ``(R, R)`` bool, True where the cell is a river.
    max_order
        Hard cap for safety (network shouldn't exceed log₂(N_headwaters)).

    Notes
    -----
    Bit-deterministic : processes cells in row-major order on every
    queue iteration, so two runs with identical inputs produce
    identical orders.
    """
    if flow_dir.shape != river_mask.shape:
        raise ValueError("flow_dir and river_mask must share shape")
    R0, R1 = flow_dir.shape
    order = np.zeros((R0, R1), dtype=np.int32)

    if not bool(river_mask.any()):
        return order

    # Build upstream count per river cell (in-degree of the river DAG).
    in_count = np.zeros((R0, R1), dtype=np.int32)
    rivers = np.argwhere(river_mask)
    for y, x in rivers:
        fd = int(flow_dir[y, x])
        if fd == _D8_SINK:
            continue
        ny = int(y) + int(_D8_DY[fd])
        nx = int(x) + int(_D8_DX[fd])
        if 0 <= ny < R0 and 0 <= nx < R1 and bool(river_mask[ny, nx]):
            in_count[ny, nx] += 1

    # Kahn topological queue : start with headwaters (in_count == 0 ∧ river).
    # Children list for fast traversal.
    children_max = np.zeros((R0, R1), dtype=np.int32)
    children_max_count = np.zeros((R0, R1), dtype=np.int32)
    remaining = in_count.copy()

    # Queue starts with every river cell with no upstream river input.
    queue: List[Tuple[int, int]] = []
    for y, x in rivers:
        if remaining[y, x] == 0:
            queue.append((int(y), int(x)))
            order[y, x] = 1

    head_idx = 0
    while head_idx < len(queue):
        y, x = queue[head_idx]
        head_idx += 1
        my_order = int(order[y, x])
        fd = int(flow_dir[y, x])
        if fd == _D8_SINK:
            continue
        ny = y + int(_D8_DY[fd])
        nx = x + int(_D8_DX[fd])
        if not (0 <= ny < R0 and 0 <= nx < R1):
            continue
        if not bool(river_mask[ny, nx]):
            continue

        prev_max = int(children_max[ny, nx])
        prev_max_count = int(children_max_count[ny, nx])
        if my_order > prev_max:
            children_max[ny, nx] = my_order
            children_max_count[ny, nx] = 1
        elif my_order == prev_max:
            children_max_count[ny, nx] = prev_max_count + 1

        remaining[ny, nx] -= 1
        if remaining[ny, nx] == 0:
            # All upstreams processed → resolve order for (ny, nx).
            max_up = int(children_max[ny, nx])
            cnt_max = int(children_max_count[ny, nx])
            if cnt_max >= 2:
                resolved = max_up + 1
            else:
                resolved = max_up
            order[ny, nx] = min(max(resolved, 1), int(max_order))
            queue.append((ny, nx))

    return order


def compute_horton_ratios(stream_order: np.ndarray,
                           flow_dir: np.ndarray,
                           river_mask: np.ndarray,
                           cell_km: float,
                           ) -> Tuple[float, float, Dict[int, int],
                                       Dict[int, float]]:
    """Horton bifurcation + length ratios from the Strahler order field.

    Returns
    -------
    Rb : float
        Bifurcation ratio averaged over consecutive orders (0.0 if
        fewer than two non-empty orders exist).
    Rl : float
        Length ratio averaged over consecutive orders (0.0 if fewer than
        two non-empty orders exist).
    counts : dict[int, int]
        Number of cells with stream order *k*, for *k ≥ 1*.
    lengths : dict[int, float]
        Total river length (km) per stream order *k*.
    """
    counts: Dict[int, int] = {}
    lengths: Dict[int, float] = {}
    R0, R1 = flow_dir.shape

    # Count + length accumulation. Length contribution of a river cell is the
    # D8 length of the segment going to its downstream neighbour (if any).
    rivers = np.argwhere(river_mask)
    for y, x in rivers:
        k = int(stream_order[y, x])
        if k <= 0:
            continue
        counts[k] = counts.get(k, 0) + 1
        fd = int(flow_dir[y, x])
        if fd != _D8_SINK:
            seg_len_km = float(_D8_LEN[fd]) * float(cell_km)
            lengths[k] = lengths.get(k, 0.0) + seg_len_km

    sorted_orders = sorted(counts.keys())
    if len(sorted_orders) < 2:
        return 0.0, 0.0, counts, lengths

    rb_terms: List[float] = []
    rl_terms: List[float] = []
    for k_lo, k_hi in zip(sorted_orders[:-1], sorted_orders[1:]):
        n_lo = counts.get(k_lo, 0)
        n_hi = counts.get(k_hi, 0)
        if n_hi > 0:
            rb_terms.append(n_lo / n_hi)
        l_lo = lengths.get(k_lo, 0.0)
        l_hi = lengths.get(k_hi, 0.0)
        # Mean length per stream of order k ≈ L_k / N_k (cell-count proxy).
        mean_lo = l_lo / max(n_lo, 1)
        mean_hi = l_hi / max(n_hi, 1)
        if mean_lo > 0.0:
            rl_terms.append(mean_hi / mean_lo)

    rb = float(sum(rb_terms) / len(rb_terms)) if rb_terms else 0.0
    rl = float(sum(rl_terms) / len(rl_terms)) if rl_terms else 0.0
    return rb, rl, counts, lengths


def _basin_stats(world,
                  stream_order: np.ndarray,
                  cell_km: float,
                  basin_id: int) -> Optional[BasinStats]:
    """Compute one basin's stats. Returns ``None`` if the basin is empty
    (or all its cells are ocean)."""
    mask = (world.watershed_id == basin_id)
    n_cells = int(mask.sum())
    if n_cells == 0:
        return None

    river_mask_in = mask & world.river_mask
    n_river_cells = int(river_mask_in.sum())

    area_km2 = float(n_cells) * float(cell_km) * float(cell_km)
    # River length: sum of D8 segment lengths for the cells in basin.
    river_length_km = 0.0
    if n_river_cells > 0:
        ys, xs = np.where(river_mask_in)
        for y, x in zip(ys.tolist(), xs.tolist()):
            fd = int(world.flow_dir[y, x])
            if fd != _D8_SINK:
                river_length_km += float(_D8_LEN[fd]) * float(cell_km)
    drainage_density = (river_length_km / area_km2) if area_km2 > 0 else 0.0

    # Outlet = highest flow_acc river cell in this basin (or first non-river
    # if none have river status — basin without rivers is still a basin).
    if n_river_cells > 0:
        acc_in = np.where(river_mask_in, world.flow_acc, -1.0)
    else:
        acc_in = np.where(mask, world.flow_acc, -1.0)
    flat = int(acc_in.argmax())
    oy, ox = divmod(flat, acc_in.shape[1])
    outlet_yx = (int(oy), int(ox))

    # Strahler max within this basin.
    if n_river_cells > 0:
        max_strahler = int(stream_order[river_mask_in].max())
    else:
        max_strahler = 0

    elev_in = world.elevation_m[mask]
    mean_e = float(elev_in.mean())
    min_e = float(elev_in.min())
    max_e = float(elev_in.max())
    span = max_e - min_e
    hypso = float((mean_e - min_e) / span) if span > 1e-6 else 0.0

    return BasinStats(
        basin_id=int(basin_id),
        n_cells=n_cells,
        n_river_cells=n_river_cells,
        area_km2=area_km2,
        river_length_km=float(river_length_km),
        drainage_density=float(drainage_density),
        max_strahler=max_strahler,
        outlet_yx=outlet_yx,
        mean_elev_m=mean_e,
        min_elev_m=min_e,
        max_elev_m=max_e,
        hypsometric_integral=hypso,
    )


# ---------------------------------------------------------------------------
# Snapshot / signature
# ---------------------------------------------------------------------------

def _snapshot_signature(snap_seed: Tuple[Any, ...]) -> str:
    """sha256 of a canonical, language-neutral tuple representation."""
    canonical = repr(snap_seed).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def observe_watersheds(sim, config: Optional[WatershedConfig] = None
                       ) -> Optional[WatershedSnapshot]:
    """Pure read-only snapshot of the watershed network.

    Returns ``None`` if no :class:`GenesisWorld` is wired to ``sim`` (the
    observer is meaningless without macro hydrology).
    """
    cfg = config if config is not None else WatershedConfig()
    world = _resolve_world(sim)
    if world is None:
        return None

    flow_dir = np.asarray(world.flow_dir, dtype=np.uint8)
    river_mask = np.asarray(world.river_mask, dtype=bool)
    watershed_id = np.asarray(world.watershed_id, dtype=np.int32)

    R = int(flow_dir.shape[0])
    cell_km = float(world.params.map_size_km) / float(R)
    map_area_km2 = float(R * R) * cell_km * cell_km

    stream_order = compute_strahler_order(
        flow_dir, river_mask, max_order=cfg.max_strahler_order)

    rb, rl, order_counts_raw, _order_lengths = compute_horton_ratios(
        stream_order, flow_dir, river_mask, cell_km)

    # Total river length (sum of D8 segment lengths for every river cell).
    total_river_cells = int(river_mask.sum())
    total_river_length_km = 0.0
    if total_river_cells > 0:
        ys, xs = np.where(river_mask)
        for y, x in zip(ys.tolist(), xs.tolist()):
            fd = int(flow_dir[y, x])
            if fd != _D8_SINK:
                total_river_length_km += float(_D8_LEN[fd]) * cell_km

    global_dd = (total_river_length_km / map_area_km2
                 ) if map_area_km2 > 0 else 0.0

    # Enumerate basins (positive ids only — -1 is ocean).
    unique_ids = np.unique(watershed_id)
    valid_ids = [int(i) for i in unique_ids.tolist() if i >= 0]
    n_basins_total = len(valid_ids)

    basin_stats: List[BasinStats] = []
    for bid in valid_ids:
        bs = _basin_stats(world, stream_order, cell_km, bid)
        if bs is None or bs.n_cells < cfg.min_basin_cells:
            continue
        basin_stats.append(bs)

    n_basins_considered = len(basin_stats)
    # Sort by area descending for the top-K view; tie-break by basin_id.
    basin_stats.sort(key=lambda b: (-b.area_km2, b.basin_id))
    top_basins = tuple(basin_stats[:cfg.top_basins])

    # Canonical signature material — sorted by basin_id so dict ordering
    # never leaks into the hash.
    canonical_basins = tuple(
        (b.basin_id, b.n_cells, b.n_river_cells,
         round(b.area_km2, 4), round(b.river_length_km, 4),
         round(b.drainage_density, 6), b.max_strahler,
         b.outlet_yx, round(b.mean_elev_m, 3),
         round(b.min_elev_m, 3), round(b.max_elev_m, 3),
         round(b.hypsometric_integral, 6))
        for b in sorted(basin_stats, key=lambda b: b.basin_id)
    )
    canonical_orders = tuple(sorted(order_counts_raw.items()))
    sig = _snapshot_signature((
        int(sim.tick), round(map_area_km2, 4), round(cell_km, 6),
        n_basins_total, n_basins_considered,
        total_river_cells, round(total_river_length_km, 4),
        round(global_dd, 6), round(rb, 6), round(rl, 6),
        canonical_orders, canonical_basins,
    ))

    return WatershedSnapshot(
        tick=int(sim.tick),
        map_area_km2=map_area_km2,
        cell_km=cell_km,
        n_basins_total=n_basins_total,
        n_basins_considered=n_basins_considered,
        total_river_cells=total_river_cells,
        total_river_length_km=float(total_river_length_km),
        global_drainage_density=float(global_dd),
        bifurcation_ratio=float(rb),
        length_ratio=float(rl),
        stream_order_counts=dict(sorted(order_counts_raw.items())),
        basins_top=top_basins,
        signature=sig,
    )


# ---------------------------------------------------------------------------
# Install / uninstall (mirrors wave 39 / 40 / 45)
# ---------------------------------------------------------------------------

def install_watershed_observer(sim,
                                config: Optional[WatershedConfig] = None
                                ) -> WatershedState:
    """Idempotent installer. Wraps ``sim.step`` once to capture snapshots
    every ``cfg.snapshot_every`` ticks."""
    cfg = config if config is not None else WatershedConfig()
    existing: Optional[WatershedState] = getattr(
        sim, "_watershed_state", None)
    if existing is not None:
        # Update config on re-install; do not wrap step a second time.
        existing.config = cfg
        return existing

    state = WatershedState(config=cfg)
    sim._watershed_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_watersheds(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._watershed_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._watershed_wrapped = True
    return state


def uninstall_watershed_observer(sim) -> bool:
    """Restore the original ``sim.step``. Returns ``True`` if anything was
    uninstalled."""
    state = getattr(sim, "_watershed_state", None)
    if state is None:
        return False
    original = getattr(sim, "_watershed_original_step", None)
    if original is not None:
        sim.step = original
        del sim._watershed_original_step
    sim._watershed_wrapped = False
    del sim._watershed_state
    return True


def watershed_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards (does not mutate sim)."""
    state: Optional[WatershedState] = getattr(sim, "_watershed_state", None)
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
        "n_basins_total": (last.n_basins_total if last is not None else None),
        "n_basins_considered": (last.n_basins_considered
                                  if last is not None else None),
        "global_drainage_density": (last.global_drainage_density
                                      if last is not None else None),
        "bifurcation_ratio": (last.bifurcation_ratio
                                if last is not None else None),
        "length_ratio": (last.length_ratio if last is not None else None),
        "stream_order_counts": (last.stream_order_counts
                                  if last is not None else None),
    }


__all__ = [
    "WatershedConfig",
    "BasinStats",
    "WatershedSnapshot",
    "WatershedHistory",
    "WatershedState",
    "compute_strahler_order",
    "compute_horton_ratios",
    "observe_watersheds",
    "install_watershed_observer",
    "uninstall_watershed_observer",
    "watershed_summary",
]
