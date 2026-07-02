"""Genesis Engine — Wave 67 Fill–Spill–Merge finite-volume lake filling.

Wave 66 (:mod:`engine.lake_hydrology`, Priority-Flood) answered *where the
terrain could hold a lake and how big at most* — the **containers**: for every
closed depression, its spill (sill) elevation and its maximum impounded volume,
the depression-storage field. But a container is only the **cup**. Priority-Flood
fills every basin to the brim by construction; it says nothing about whether the
world actually delivers enough water to fill it. A vast desert playa and a full
alpine tarn look identical to Priority-Flood.

This module is the missing volume balance — the finite-volume partner promised in
the Wave 66 docstring and carried on the roadmap as **Wave 67**. It pours the
*actual* routed runoff (Wave 64 :mod:`engine.river_discharge` /
:mod:`engine.discharge_observer` — the mass-conserving LTI routing of a
climate-driven runoff balance down the D8 graph) into those containers and lets
each fill **only as far as its inflow allows**. The result is the emergent
spectrum Priority-Flood could not see:

* **full lakes** — inflow ≥ capacity: the cup brims and **spills** (overflow
  volume is reported; cascading the spill to the downstream basin is Wave 68);
* **partial lakes** — inflow fills the cup part-way to a level strictly below the
  sill (a smaller, shallower, real lake);
* **playas / salt pans** — a *terminal* (endorheic) basin whose inflow is a small
  fraction of its capacity: little standing water, and because an outlet-less
  basin loses water only to evaporation, its dissolved load **concentrates**
  (the salinity-concentration cue, ∝ capacity / water — the physical seed of the
  salt story, cf. :mod:`engine.salt_evaporation` C15, *not* wired here);
* **dry basins** — negligible inflow: the cup stays empty.

Algorithm — Fill–Spill–Merge (Barnes, Callaghan & Wickert, *ESurf* 2021)
------------------------------------------------------------------------

FSM (`rbarnes.org/sci/2020_barnes_fsm.pdf`) routes water through a **depression
hierarchy**: runoff fills a depression, which overflows (**spills**) into its
neighbour, and when a depression and its neighbour both fill they **merge** and
share a single surface. This module implements the *fill* and *spill-detection*
core over the Priority-Flood containers, with the **merge** already baked in by
construction: Priority-Flood escapes each basin only over its **lowest sill**, so
a bowl-inside-a-bowl is already one connected container at the outer sill (Wave 66
step 4 — "nested basins MERGE"). Each container is therefore an *already-merged*
depression, and FSM here reduces to the exact finite-volume fill of that merged
container:

Given a container's cell elevations ``e_i`` (all ≤ its sill ``S``), a cell area
``A``, and a delivered water volume ``V`` (= ``min(inflow, capacity)``), find the
flat water level ``h ∈ [min e_i, S]`` such that ``Σ_i max(h − e_i, 0)·A = V``.
This is the container's **hypsometric fill** — solved exactly and deterministically
by sorting the cell elevations and walking the piecewise-linear volume(level)
curve (:func:`_fill_level`). Water finds its level, so the partial surface is
**flat**, just like the Priority-Flood surface — only lower.

Inflow per basin
----------------

Discharge ``Q`` (m³/s) from :func:`engine.discharge_observer.route_runoff` is the
accumulated runoff routed to each cell; at a basin's interior D8 sink it equals
the whole basin's inflow **rate**. Multiplied by an accumulation window
(``fill_window_days``) it becomes an inflow **volume**. For a *terminal* container
(one holding ``flow_dir == 255`` interior sinks) inflow is the sum of ``Q`` over
its sinks; for a *throughflow* container (a river-crossed depression with no
interior sink) inflow is the peak ``Q`` traversing it — either way the basin fills
to ``min(inflow, capacity)``, so a real river holds its lake at the brim while a
starved closed basin becomes a playa. The window is the single physical knob: it
is *how much inflow the basins have received*, and the whole partial/full/playa
spectrum scales monotonically with it.

Observer contract (mirrors Wave 66 / 53 / 62 / 63)
--------------------------------------------------

- ``FSMConfig`` / ``FilledLake`` / ``FSMSnapshot`` / ``FSMHistory`` / ``FSMState``
  dataclasses (frozen where they carry data).
- ``fill_depressions`` — **pure**: containers + a discharge field → filled lakes.
- ``fsm_from_world`` — pure read of a :class:`GenesisWorld` (builds the routed
  discharge from its live climate via the discharge-observer SSOT).
- ``observe_fsm(sim, cfg)`` — read-only, resolves the world, returns a snap.
- ``install_fsm_observer`` / ``uninstall_fsm_observer`` — idempotent step wrap.
- ``fsm_summary(sim)`` — diagnostic dict for dashboards.

Determinism & stone-age compliance
-----------------------------------

No RNG: Priority-Flood + the deterministic Kahn routing + a row-major
component walk + an O(n) hypsometric solve; the signature is ``sha256`` of a
canonical tuple. Two runs on the same world seed produce identical snapshots.
The observer never *declares* a lake or a level — it reads the elevation the
world eroded and the runoff the world's climate produced, and reports where the
water would stand. No mutation of any world/sim array, no new cross-language
tell (``PY_TO_RUST`` unchanged — this is substrate physics, not an agent
capability).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.discharge_observer import (DischargeConfig, route_runoff,
                                       runoff_field_m3s)
from engine.lake_hydrology import (_D8_SINK, _label_components,
                                   priority_flood_fill)

# ADR-0005 pipeline tags (mirror lake_hydrology / discharge_observer).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FSMConfig:
    """Read-only knobs for the finite-volume Fill–Spill–Merge observer."""
    snapshot_every: int = 64
    # Accumulation window: how much routed inflow the basins have received. The
    # whole full/partial/playa spectrum scales monotonically with this.
    fill_window_days: float = 365.25
    # Container detection (mirror LakeConfig — the Wave 66 cups we fill).
    depth_eps_m: float = 0.5
    min_lake_cells: int = 2
    top_lakes: int = 5
    default_sea_level_m: float = 0.0
    default_precip_mm: float = 800.0
    default_temp_c: float = 12.0
    # A terminal basin filled below this fraction of capacity is a *playa*.
    playa_fill_fraction: float = 0.5
    # At/above this fraction the basin is *full* (and spills if inflow exceeds).
    full_fill_fraction: float = 0.999
    # Below this standing volume (m³) a basin counts as *dry*.
    dry_volume_eps_m3: float = 1.0
    # Reported salinity-concentration proxy (capacity / water) is capped here.
    max_salinity_factor: float = 50.0
    # Runoff-balance knobs (SSOT with the discharge observer).
    discharge: DischargeConfig = field(default_factory=DischargeConfig)


@dataclass(frozen=True)
class FilledLake:
    """One emergent finite-volume lake: a Wave 66 container filled by inflow."""
    lake_id: int
    n_cells: int                 # container (max-extent) cells
    capacity_m3: float           # Priority-Flood container volume (Wave 66)
    inflow_m3: float             # routed runoff delivered over the window
    water_volume_m3: float       # min(inflow, capacity)
    fill_fraction: float         # water_volume / capacity, in [0, 1]
    overflow_m3: float           # max(inflow − capacity, 0) — spills downstream
    spills: bool
    sill_elev_m: float           # spill level = brim (container flat surface)
    bottom_elev_m: float
    water_level_m: float         # emergent finite-volume surface (≤ sill)
    water_area_km2: float        # wetted area at water_level (≤ container area)
    water_max_depth_m: float
    water_mean_depth_m: float
    container_area_km2: float
    is_terminal: bool            # endorheic (holds an interior D8 sink)
    state: str                   # full | lake | playa | dry | throughflow
    salinity_factor: float       # capacity / water for terminal basins
    centroid_yx: Tuple[int, int]
    deepest_yx: Tuple[int, int]


@dataclass(frozen=True)
class FSMSnapshot:
    """Global + top-K finite-volume lake snapshot at a given sim tick."""
    tick: int
    cell_km: float
    window_days: float
    land_cells: int
    n_basins: int
    n_full: int
    n_partial: int
    n_playa: int
    n_dry: int
    n_throughflow: int
    n_spilling: int
    total_capacity_m3: float
    total_inflow_m3: float
    total_water_m3: float
    total_overflow_m3: float
    overall_fill_fraction: float
    total_water_area_km2: float
    max_salinity_factor: float
    lakes_top: Tuple[FilledLake, ...]
    signature: str


@dataclass
class FSMHistory:
    snapshots: List[FSMSnapshot] = field(default_factory=list)


@dataclass
class FSMState:
    config: FSMConfig
    history: FSMHistory = field(default_factory=FSMHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# Pure core — hypsometric finite-volume fill of one container
# ---------------------------------------------------------------------------

def _fill_level(elev_sorted: np.ndarray, cell_area_m2: float,
                target_vol: float, sill: float) -> float:
    """Flat water level that holds ``target_vol`` over a sorted cell set.

    ``elev_sorted`` are one container's cell elevations, ascending, all ≤
    ``sill``. Returns ``h`` with ``Σ max(h − e_i, 0)·A == target_vol`` (clamped
    to ``sill`` — a fuller basin cannot rise past its brim). O(n), exact on the
    piecewise-linear volume(level) curve, deterministic.
    """
    n = int(elev_sorted.size)
    if n == 0:
        return float(sill)
    if target_vol <= 0.0:
        return float(elev_sorted[0])
    ps = 0.0  # prefix sum of the k lowest cells
    for k in range(1, n + 1):
        ps += float(elev_sorted[k - 1])
        seg_hi = float(elev_sorted[k]) if k < n else float(sill)
        # Volume when the level reaches seg_hi with exactly k cells submerged.
        vol_hi = (k * seg_hi - ps) * cell_area_m2
        if vol_hi >= target_vol:
            h = (target_vol / cell_area_m2 + ps) / k
            return float(min(h, sill))
    return float(sill)


def fill_depressions(elev: np.ndarray,
                     discharge: Optional[np.ndarray],
                     flow_dir: Optional[np.ndarray],
                     *,
                     cell_km: float,
                     sea_level_m: float = 0.0,
                     window_s: float,
                     config: Optional[FSMConfig] = None,
                     ) -> Tuple[np.ndarray, np.ndarray, np.ndarray,
                                List[FilledLake]]:
    """Finite-volume fill of every Priority-Flood container.

    Returns ``(filled, depth, water_depth, lakes)`` where ``filled`` / ``depth``
    are the Wave 66 Priority-Flood surface / capacity depth, ``water_depth`` is
    the *emergent standing-water* depth (≤ ``depth`` everywhere), and ``lakes``
    the per-basin :class:`FilledLake` records. Pure / deterministic; no sim, no
    mutation of the inputs.
    """
    cfg = config if config is not None else FSMConfig()
    elev = np.asarray(elev, dtype=np.float64)
    if elev.ndim != 2:
        raise ValueError("elev must be a 2-D array")

    filled = priority_flood_fill(elev, sea_level_m=sea_level_m)
    depth = np.maximum(filled - elev, 0.0)
    land = elev > np.float64(sea_level_m)
    container_mask = (depth > np.float64(cfg.depth_eps_m)) & land
    labels, n = _label_components(container_mask)

    cell_area_m2 = (float(cell_km) * 1000.0) ** 2
    cell_area_km2 = float(cell_km) * float(cell_km)

    if discharge is None:
        Q = np.zeros_like(elev)
    else:
        Q = np.asarray(discharge, dtype=np.float64)
        if Q.shape != elev.shape:
            Q = np.zeros_like(elev)

    fd = None
    if flow_dir is not None:
        fd = np.asarray(flow_dir, dtype=np.uint8)
        if fd.shape != elev.shape:
            fd = None

    water_depth = np.zeros_like(elev)
    lakes: List[FilledLake] = []

    for lid in range(1, n + 1):
        comp = labels == lid
        n_cells = int(comp.sum())
        if n_cells < cfg.min_lake_cells:
            continue

        e = elev[comp]
        sill = float(filled[comp].max())          # flat brim (== surface)
        bottom = float(e.min())
        capacity = float(depth[comp].sum()) * cell_area_m2

        # --- inflow: terminal basins sum their interior-sink discharge, --------
        #     throughflow basins take the peak discharge crossing them.
        if fd is not None and bool(np.any(fd[comp] == _D8_SINK)):
            terminal = True
            inflow_rate = float(Q[comp][fd[comp] == _D8_SINK].sum())
        else:
            terminal = False
            inflow_rate = float(Q[comp].max()) if Q.size else 0.0
        inflow_vol = inflow_rate * float(window_s)
        water_vol = min(inflow_vol, capacity)
        overflow = max(inflow_vol - capacity, 0.0)

        # --- hypsometric fill --------------------------------------------------
        level = _fill_level(np.sort(e), cell_area_m2, water_vol, sill)
        wd = np.maximum(level - e, 0.0)
        wet = wd > 1e-9
        water_area = float(int(wet.sum())) * cell_area_km2
        w_max = float(wd.max()) if wd.size else 0.0
        w_mean = float(wd[wet].mean()) if bool(wet.any()) else 0.0
        water_depth[comp] = wd

        fill_frac = float(water_vol / capacity) if capacity > 0.0 else 0.0
        if terminal and water_vol > cfg.dry_volume_eps_m3:
            salinity = float(min(capacity / water_vol, cfg.max_salinity_factor))
        else:
            salinity = 1.0

        if water_vol <= cfg.dry_volume_eps_m3:
            state = "dry"
        elif not terminal:
            state = "throughflow"
        elif fill_frac >= cfg.full_fill_fraction:
            state = "full"
        elif fill_frac < cfg.playa_fill_fraction:
            state = "playa"
        else:
            state = "lake"

        ys, xs = np.nonzero(comp)
        cyx = (int(round(float(ys.mean()))), int(round(float(xs.mean()))))
        comp_depth = np.where(comp, depth, -1.0)
        flat = int(comp_depth.argmax())
        dy, dx = divmod(flat, elev.shape[1])

        lakes.append(FilledLake(
            lake_id=lid,
            n_cells=n_cells,
            capacity_m3=capacity,
            inflow_m3=float(inflow_vol),
            water_volume_m3=float(water_vol),
            fill_fraction=float(min(fill_frac, 1.0)),
            overflow_m3=float(overflow),
            spills=bool(overflow > cfg.dry_volume_eps_m3),
            sill_elev_m=sill,
            bottom_elev_m=bottom,
            water_level_m=float(level),
            water_area_km2=water_area,
            water_max_depth_m=w_max,
            water_mean_depth_m=w_mean,
            container_area_km2=float(n_cells) * cell_area_km2,
            is_terminal=terminal,
            state=state,
            salinity_factor=salinity,
            centroid_yx=cyx,
            deepest_yx=(int(dy), int(dx)),
        ))

    return filled, depth, water_depth, lakes


# ---------------------------------------------------------------------------
# World resolution (read-only) — mirrors lake_hydrology / discharge_observer
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


def _field(world, name: str, fallback: float, shape) -> np.ndarray:
    """Read a macro field, falling back to a constant of the right shape."""
    arr = getattr(world, name, None)
    if arr is None:
        return np.full(shape, float(fallback), dtype=np.float64)
    a = np.asarray(arr, dtype=np.float64)
    if a.shape != tuple(shape):
        return np.full(shape, float(fallback), dtype=np.float64)
    return a


# ---------------------------------------------------------------------------
# Snapshot / signature
# ---------------------------------------------------------------------------

def _snapshot_signature(snap_seed: Tuple[Any, ...]) -> str:
    """sha256 of a canonical, language-neutral tuple representation."""
    return hashlib.sha256(repr(snap_seed).encode("utf-8")).hexdigest()


def fsm_from_world(world, config: Optional[FSMConfig] = None,
                   tick: int = 0,
                   window_s: Optional[float] = None) -> FSMSnapshot:
    """Pure read-only finite-volume lake snapshot from a :class:`GenesisWorld`.

    Builds the routed discharge from the world's live climate (the discharge
    observer SSOT: ``runoff = max(P − ET, 0)`` routed down the static D8 graph)
    and pours it into the Priority-Flood containers over ``window_s`` seconds
    (defaults to ``config.fill_window_days``).
    """
    cfg = config if config is not None else FSMConfig()
    elev = np.asarray(world.elevation_m, dtype=np.float64)
    R = int(elev.shape[0])
    sea = float(getattr(getattr(world, "params", None), "sea_level_m",
                        cfg.default_sea_level_m))
    map_km = float(getattr(getattr(world, "params", None), "map_size_km",
                           float(R)))
    cell_km = map_km / float(R) if R else 1.0
    flow_dir = np.asarray(world.flow_dir, dtype=np.uint8)

    precip = _field(world, "precip_mm", cfg.default_precip_mm, elev.shape)
    temp = _field(world, "temp_c", cfg.default_temp_c, elev.shape)
    runoff = runoff_field_m3s(precip, temp, cell_km, cfg.discharge)
    discharge = route_runoff(flow_dir, runoff)

    if window_s is None:
        window_s = float(cfg.fill_window_days) * 24.0 * 3600.0

    filled, depth, water_depth, lakes = fill_depressions(
        elev, discharge, flow_dir, cell_km=cell_km, sea_level_m=sea,
        window_s=window_s, config=cfg)

    land_cells = int((elev > sea).sum())
    total_cap = float(sum(lk.capacity_m3 for lk in lakes))
    total_inflow = float(sum(lk.inflow_m3 for lk in lakes))
    total_water = float(sum(lk.water_volume_m3 for lk in lakes))
    total_overflow = float(sum(lk.overflow_m3 for lk in lakes))
    total_water_area = float(sum(lk.water_area_km2 for lk in lakes))
    overall_frac = (total_water / total_cap) if total_cap > 0.0 else 0.0
    max_sal = float(max((lk.salinity_factor for lk in lakes), default=1.0))

    n_full = sum(1 for lk in lakes if lk.state == "full")
    n_partial = sum(1 for lk in lakes if lk.state == "lake")
    n_playa = sum(1 for lk in lakes if lk.state == "playa")
    n_dry = sum(1 for lk in lakes if lk.state == "dry")
    n_through = sum(1 for lk in lakes if lk.state == "throughflow")
    n_spilling = sum(1 for lk in lakes if lk.spills)

    ranked = sorted(lakes, key=lambda lk: (-lk.water_volume_m3, lk.lake_id))
    top = tuple(ranked[:cfg.top_lakes])

    canonical = tuple(
        (lk.lake_id, lk.n_cells, round(lk.capacity_m3, 2),
         round(lk.water_volume_m3, 2), round(lk.fill_fraction, 6),
         round(lk.overflow_m3, 2), round(lk.water_level_m, 3),
         round(lk.water_area_km2, 4), round(lk.water_max_depth_m, 3),
         lk.is_terminal, lk.state, round(lk.salinity_factor, 4),
         lk.centroid_yx, lk.deepest_yx)
        for lk in sorted(lakes, key=lambda lk: lk.lake_id)
    )
    sig = _snapshot_signature((
        int(tick), round(cell_km, 6), round(float(cfg.fill_window_days), 4),
        land_cells, len(lakes), n_full, n_partial, n_playa, n_dry, n_through,
        n_spilling, round(total_cap, 2), round(total_inflow, 2),
        round(total_water, 2), round(total_overflow, 2), round(overall_frac, 6),
        round(total_water_area, 4), round(max_sal, 4), canonical,
    ))

    return FSMSnapshot(
        tick=int(tick),
        cell_km=cell_km,
        window_days=float(cfg.fill_window_days),
        land_cells=land_cells,
        n_basins=len(lakes),
        n_full=int(n_full),
        n_partial=int(n_partial),
        n_playa=int(n_playa),
        n_dry=int(n_dry),
        n_throughflow=int(n_through),
        n_spilling=int(n_spilling),
        total_capacity_m3=total_cap,
        total_inflow_m3=total_inflow,
        total_water_m3=total_water,
        total_overflow_m3=total_overflow,
        overall_fill_fraction=float(overall_frac),
        total_water_area_km2=total_water_area,
        max_salinity_factor=max_sal,
        lakes_top=top,
        signature=sig,
    )


def observe_fsm(sim, config: Optional[FSMConfig] = None
                ) -> Optional[FSMSnapshot]:
    """Pure read-only FSM snapshot for ``sim``. ``None`` if no world wired."""
    cfg = config if config is not None else FSMConfig()
    world = _resolve_world(sim)
    if world is None:
        return None
    try:
        tick = int(sim.tick)
    except Exception:
        tick = 0
    return fsm_from_world(world, cfg, tick=tick)


# ---------------------------------------------------------------------------
# Install / uninstall (mirrors wave 66 / 53 / 62 / 63)
# ---------------------------------------------------------------------------

def install_fsm_observer(sim, config: Optional[FSMConfig] = None) -> FSMState:
    """Idempotent installer. Wraps ``sim.step`` once to capture a snapshot every
    ``cfg.snapshot_every`` ticks."""
    cfg = config if config is not None else FSMConfig()
    existing: Optional[FSMState] = getattr(sim, "_fsm_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = FSMState(config=cfg)
    sim._fsm_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_fsm(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._fsm_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._fsm_wrapped = True
    return state


def uninstall_fsm_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_fsm_state", None)
    if state is None:
        return False
    original = getattr(sim, "_fsm_original_step", None)
    if original is not None:
        sim.step = original
        del sim._fsm_original_step
    sim._fsm_wrapped = False
    del sim._fsm_state
    return True


def fsm_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards (does not mutate sim)."""
    state: Optional[FSMState] = getattr(sim, "_fsm_state", None)
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
        "n_basins": (last.n_basins if last is not None else None),
        "n_full": (last.n_full if last is not None else None),
        "n_playa": (last.n_playa if last is not None else None),
        "n_spilling": (last.n_spilling if last is not None else None),
        "total_water_m3": (last.total_water_m3 if last is not None else None),
        "overall_fill_fraction": (last.overall_fill_fraction
                                  if last is not None else None),
        "max_salinity_factor": (last.max_salinity_factor
                                if last is not None else None),
    }


__all__ = [
    "FSMConfig",
    "FilledLake",
    "FSMSnapshot",
    "FSMHistory",
    "FSMState",
    "fill_depressions",
    "fsm_from_world",
    "observe_fsm",
    "install_fsm_observer",
    "uninstall_fsm_observer",
    "fsm_summary",
]
