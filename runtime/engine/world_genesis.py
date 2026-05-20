"""Genesis Engine — Wave 16 ultra-realistic world genesis.

Continental-scale terrain generator that replaces the FBM-only base map
with a physically-motivated pipeline::

    plate tectonics (Voronoi)
        |
        v
    boundary classification (convergent / divergent / transform)
        |
        v
    base elevation = plate_type + tectonic_uplift + hot_spots
        |
        v
    multi-octave FBM overlay (continents / regions / hills)
        |
        v
    hydraulic erosion = stream-power-law iterated 40x
        |
        v
    hydrology: D8 flow direction + flow accumulation
        |
        v
    rivers (flow_acc > threshold) + watersheds
        |
        v
    atmospheric circulation (Hadley / Ferrel / polar cells)
        |
        v
    orographic precipitation (windward boost, lee-side rain shadow)
        |
        v
    temperature (latitude + adiabatic lapse + continentality)
        |
        v
    biomes (Whittaker, reuses engine.world.classify_biome_array)

Everything routes through ``engine.core.prf_rng`` so two runs with the
same ``GenesisParams.seed`` produce bit-identical outputs.

This module is a pure function — it does NOT mutate any ``Simulation``.
It outputs a ``GenesisWorld`` dataclass that downstream layers
(``world.py`` chunks, ``geology.py`` strata, ``meteorology.py``) can
sample as a coarse macro-field to ground micro-scale procedural detail.

Read-only contract:
    - No side effects on engine.sim / engine.agents / any other module.
    - Deterministic given seed (verified by smoke step 1).
    - Save/load round-trip preserves every field bit-identically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng, prf_bytes
from engine.world import Biome, classify_biome_array


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class GenesisParams:
    """Configuration for an ultra-realistic continental world.

    Defaults are tuned for a 4000 km square continent at 128 cells/side
    (~31 km per cell). Generation cost ~2-4 s single-thread.
    """

    seed: int = 0xFADE_C0FFEE_5A & 0xFFFFFFFF_FFFFFFFF
    map_size_km: float = 4000.0
    resolution: int = 128

    n_plates: int = 12
    oceanic_fraction: float = 0.55      # 55 % of plates are oceanic by default

    sea_level_m: float = 0.0
    max_elev_m: float = 8000.0
    abyssal_depth_m: float = -5500.0
    continent_base_m: float = 500.0

    erosion_iters: int = 40
    erodibility_k: float = 8.0e-5       # m^(1-2m) / Myr, area in m^2
    erosion_m: float = 0.5
    erosion_n: float = 1.0
    erosion_dt_myr: float = 1.0
    uplift_per_myr_max: float = 600.0   # m/Myr at strong convergence

    fbm_continent_km: float = 600.0
    fbm_region_km: float = 150.0
    fbm_hills_km: float = 30.0
    fbm_amp_continent_m: float = 1200.0
    fbm_amp_region_m: float = 400.0
    fbm_amp_hills_m: float = 80.0

    rain_iters: int = 6
    orographic_gain: float = 0.0028     # per m of uplift along wind
    rain_shadow_decay: float = 0.0042   # per m of descent along wind
    base_precip_mm: float = 1100.0      # global mean before banding

    equator_y_frac: float = 0.5         # where the equator sits, 0=top edge
    lat_span_deg: float = 90.0          # half-span: map covers +/- 45 deg by default

    river_threshold_cells: float = 60.0
    continentality_km: float = 800.0    # scale for inland temperature swing


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

# Plate kinds.
OCEANIC = np.uint8(0)
CONTINENTAL = np.uint8(1)

# Boundary classes.
BOUND_NONE = np.uint8(0)
BOUND_DIVERGENT = np.uint8(1)
BOUND_CONVERGENT = np.uint8(2)
BOUND_TRANSFORM = np.uint8(3)


@dataclass
class GenesisWorld:
    """Container for one fully generated ultra-realistic world."""

    params: GenesisParams

    # Plate data (per plate, indexed by plate id)
    plate_kind: np.ndarray              # (P,) uint8 - OCEANIC / CONTINENTAL
    plate_motion: np.ndarray            # (P, 2) float32 - cm/yr (vx, vy)
    plate_seeds: np.ndarray             # (P, 2) float32 - seed positions
    plate_age_myr: np.ndarray           # (P,) float32 - plate age

    # Per-cell fields (R, R)
    plate_id: np.ndarray                # uint8
    boundary_kind: np.ndarray           # uint8 - BOUND_* code
    uplift_rate: np.ndarray             # float32 - m / Myr
    elevation_m: np.ndarray             # float32 - post-erosion
    elevation_raw_m: np.ndarray         # float32 - pre-erosion (for diag)
    flow_dir: np.ndarray                # uint8 - 0..7 D8, 255 = sink/ocean
    flow_acc: np.ndarray                # float32 - drainage area in cells
    river_mask: np.ndarray              # bool
    watershed_id: np.ndarray            # int32 - basin label, -1 = ocean
    distance_to_coast_km: np.ndarray    # float32
    wind_u: np.ndarray                  # float32 - east-positive m/s
    wind_v: np.ndarray                  # float32 - north-positive m/s
    latitude_deg: np.ndarray            # float32 - per-cell latitude
    precip_mm: np.ndarray               # float32
    temp_c: np.ndarray                  # float32
    biome: np.ndarray                   # uint8 - Biome enum values

    # Diagnostics
    diagnostics: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1. Plate tectonics — Voronoi seeding
# ---------------------------------------------------------------------------

def _seed_plates(p: GenesisParams) -> Tuple[np.ndarray, np.ndarray,
                                            np.ndarray, np.ndarray]:
    """Sample plate seed positions, kinds, motion vectors.

    Uses ``prf_rng(seed, ["genesis", "plates"], [])`` so two runs with the
    same seed yield identical plate layouts.
    """
    rng = prf_rng(p.seed, ["genesis", "plates"], [])
    R = float(p.map_size_km)
    seeds = rng.uniform(0.0, R, size=(p.n_plates, 2)).astype(np.float32)

    # 0=oceanic, 1=continental. We sample with a target oceanic fraction.
    n_oceanic = max(1, int(round(p.n_plates * p.oceanic_fraction)))
    kinds = np.zeros(p.n_plates, dtype=np.uint8)
    # Deterministic permutation, oceanic plates first.
    perm = rng.permutation(p.n_plates)
    kinds[perm[n_oceanic:]] = CONTINENTAL
    kinds[perm[:n_oceanic]] = OCEANIC

    # Plate motion vectors in cm/yr. Typical 1-10 cm/yr.
    angles = rng.uniform(0.0, 2.0 * np.pi, size=p.n_plates).astype(np.float32)
    speeds = rng.uniform(1.0, 9.0, size=p.n_plates).astype(np.float32)
    motion = np.stack([np.cos(angles) * speeds,
                       np.sin(angles) * speeds], axis=1).astype(np.float32)

    # Age (Myr). Oceanic younger than continental on average.
    ages = np.where(kinds == OCEANIC,
                    rng.uniform(5.0, 180.0, size=p.n_plates),
                    rng.uniform(200.0, 2500.0, size=p.n_plates)
                    ).astype(np.float32)

    return seeds, kinds, motion, ages


def _voronoi_assignment(p: GenesisParams, seeds: np.ndarray) -> np.ndarray:
    """Assign each cell to its nearest plate seed.

    Computed vectorized with a single pairwise distance pass; OK at R=128
    (16 384 cells × 12 plates = 196 608 distances).
    """
    R = p.resolution
    cell_size = p.map_size_km / R
    xs = (np.arange(R, dtype=np.float32) + 0.5) * cell_size
    ys = (np.arange(R, dtype=np.float32) + 0.5) * cell_size
    XX, YY = np.meshgrid(xs, ys, indexing="xy")
    # Distances: (R, R, P)
    dx = XX[..., None] - seeds[:, 0][None, None, :]
    dy = YY[..., None] - seeds[:, 1][None, None, :]
    d2 = dx * dx + dy * dy
    return np.argmin(d2, axis=2).astype(np.uint8)


# ---------------------------------------------------------------------------
# 2. Boundary classification + uplift
# ---------------------------------------------------------------------------

def _classify_boundaries(p: GenesisParams,
                         plate_id: np.ndarray,
                         kinds: np.ndarray,
                         motion: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Build per-cell boundary kind + uplift rate (m/Myr).

    For each cell that has at least one neighbour belonging to a *different*
    plate, look at the relative motion between the two plates projected onto
    the boundary normal (approximated as the neighbour direction):

      - relative_normal > 0  -> closing  -> CONVERGENT  -> uplift_rate > 0
      - relative_normal < 0  -> opening  -> DIVERGENT   -> small uplift (ridges)
      - |relative_normal|~0  -> sliding  -> TRANSFORM   -> tiny uplift (scarps)

    Continental-continental convergence yields the biggest uplift
    (orogeny like the Himalayas). Oceanic-continental is moderate (volcanic
    arc / Andes-style). Oceanic-oceanic is small (island arcs).
    """
    R = p.resolution
    bound = np.zeros((R, R), dtype=np.uint8)
    uplift = np.zeros((R, R), dtype=np.float32)

    # 4-neighbour scan
    neigh = [(-1, 0, np.array([-1.0, 0.0], dtype=np.float32)),
             (1, 0, np.array([1.0, 0.0], dtype=np.float32)),
             (0, -1, np.array([0.0, -1.0], dtype=np.float32)),
             (0, 1, np.array([0.0, 1.0], dtype=np.float32))]

    # Precompute shifted plate_id arrays.
    for dx, dy, normal in neigh:
        shifted = np.roll(plate_id, shift=(dy, dx), axis=(0, 1))
        diff_mask = (shifted != plate_id)
        if not diff_mask.any():
            continue
        # Per-cell relative motion vector (motion[neighbour] - motion[self])
        # Normal direction is from neighbour towards self (so a positive
        # projection means neighbour is moving INTO self → convergent).
        n_motion = motion[shifted]                    # (R, R, 2)
        s_motion = motion[plate_id]                   # (R, R, 2)
        rel = n_motion - s_motion                     # (R, R, 2)
        # Projection of (rel) onto the *inward* normal (-normal).
        proj = -(rel[..., 0] * normal[0] + rel[..., 1] * normal[1])

        n_kind = kinds[shifted]
        s_kind = kinds[plate_id]

        # Classify boundary type.
        thresh = 0.3
        conv = diff_mask & (proj > thresh)
        div = diff_mask & (proj < -thresh)
        tran = diff_mask & ~(conv | div)

        # Per-cell intensity (cm/yr → m/Myr scaling = 10).
        # Convergence: scale by kind pair.
        kind_pair_factor = np.ones_like(proj, dtype=np.float32)
        cc = conv & (n_kind == CONTINENTAL) & (s_kind == CONTINENTAL)
        oc = conv & (((n_kind == OCEANIC) & (s_kind == CONTINENTAL)) |
                      ((n_kind == CONTINENTAL) & (s_kind == OCEANIC)))
        oo = conv & (n_kind == OCEANIC) & (s_kind == OCEANIC)
        kind_pair_factor[cc] = 1.0
        kind_pair_factor[oc] = 0.55
        kind_pair_factor[oo] = 0.30

        # Each direction contributes its uplift signal additively.
        u_conv = (np.clip(proj, 0.0, 12.0) * 10.0 *
                  kind_pair_factor * (p.uplift_per_myr_max / 120.0))
        u_div = np.clip(-proj, 0.0, 12.0) * 10.0 * 0.15  # rifts/ridges low
        u_tran = np.abs(proj) * 10.0 * 0.05              # tiny scarps

        # Boundary kind: priority CONVERGENT > DIVERGENT > TRANSFORM.
        bound[conv] = BOUND_CONVERGENT
        bound[(bound == BOUND_NONE) & div] = BOUND_DIVERGENT
        bound[(bound == BOUND_NONE) & tran] = BOUND_TRANSFORM

        uplift += np.where(conv, u_conv, 0.0).astype(np.float32)
        uplift += np.where(div, u_div, 0.0).astype(np.float32)
        uplift += np.where(tran, u_tran, 0.0).astype(np.float32)

    # Smooth the uplift band slightly so mountain ranges aren't 1-cell wide.
    uplift = _box_blur(uplift, radius=1)
    return bound, uplift


# ---------------------------------------------------------------------------
# 3. Base elevation + FBM overlay
# ---------------------------------------------------------------------------

def _base_elevation(p: GenesisParams, plate_id: np.ndarray,
                    kinds: np.ndarray, uplift_total_m: np.ndarray) -> np.ndarray:
    """Continental crust sits high, oceanic crust sits in the abyss."""
    is_cont = (kinds[plate_id] == CONTINENTAL)
    base = np.where(is_cont,
                    np.float32(p.continent_base_m),
                    np.float32(p.abyssal_depth_m))
    # Soft continental shelf: cells whose nearest plate boundary on a
    # continental plate are still high.
    return base + uplift_total_m


def _fbm_value_noise(seed: int, layer: str,
                      shape: Tuple[int, int], scale_cells: float,
                      octaves: int = 5) -> np.ndarray:
    """Vectorised FBM value noise (deterministic via prf_rng).

    Re-implements a small fbm at the macro grid rather than reusing
    ``engine.world.fbm_2d`` so the lattice is in *cell* units and the
    octave structure is controlled here.
    """
    R = shape[0]
    out = np.zeros(shape, dtype=np.float32)
    amp_norm = 0.0
    amp = 1.0
    freq = 1.0 / max(1.0, scale_cells)
    for o in range(octaves):
        out += _value_noise_layer(seed, f"{layer}_o{o}", R, freq) * amp
        amp_norm += amp
        amp *= 0.5
        freq *= 2.0
    return out / max(amp_norm, 1e-6)


def _value_noise_layer(seed: int, layer: str, R: int, freq: float) -> np.ndarray:
    """Single octave of value noise on an R x R grid in [-1, 1]."""
    # Build lattice indices (integer corner coordinates).
    xs = np.arange(R, dtype=np.float32) * freq
    ys = np.arange(R, dtype=np.float32) * freq
    XX, YY = np.meshgrid(xs, ys, indexing="xy")
    gx = np.floor(XX).astype(np.int64)
    gy = np.floor(YY).astype(np.int64)
    fx = XX - gx
    fy = YY - gy
    v00 = _hash_lattice(seed, layer, gx, gy)
    v10 = _hash_lattice(seed, layer, gx + 1, gy)
    v01 = _hash_lattice(seed, layer, gx, gy + 1)
    v11 = _hash_lattice(seed, layer, gx + 1, gy + 1)
    sx = (1.0 - np.cos(fx * np.pi)) * 0.5
    sy = (1.0 - np.cos(fy * np.pi)) * 0.5
    a = v00 + (v10 - v00) * sx
    b = v01 + (v11 - v01) * sx
    return (a + (b - a) * sy).astype(np.float32)


def _hash_lattice(seed: int, layer: str,
                   gx: np.ndarray, gy: np.ndarray) -> np.ndarray:
    """Deterministic hash of lattice point -> float in [-1, 1]."""
    # Stable 64-bit salt per (seed, layer).
    salt_bytes = prf_bytes(seed, ["genesis_noise", layer], [], 8)
    salt = int.from_bytes(salt_bytes, "little", signed=False) & 0xFFFFFFFFFFFFFFFF
    a = (gx.astype(np.uint64) * np.uint64(73856093)) ^ \
        (gy.astype(np.uint64) * np.uint64(19349663))
    a ^= np.uint64(salt)
    # SplitMix64 avalanche.
    a = (a ^ (a >> np.uint64(33))) * np.uint64(0xff51afd7ed558ccd)
    a = (a ^ (a >> np.uint64(33))) * np.uint64(0xc4ceb9fe1a85ec53)
    a = a ^ (a >> np.uint64(33))
    return (a.astype(np.float64) /
            float(np.iinfo(np.uint64).max) * 2.0 - 1.0).astype(np.float32)


def _fbm_overlay(p: GenesisParams) -> np.ndarray:
    """Multi-scale terrain noise that adds continental, regional, hill detail."""
    R = p.resolution
    cell_km = p.map_size_km / R
    cont_cells = max(2.0, p.fbm_continent_km / cell_km)
    reg_cells = max(1.5, p.fbm_region_km / cell_km)
    hill_cells = max(1.0, p.fbm_hills_km / cell_km)
    o_cont = _fbm_value_noise(p.seed, "continent", (R, R), cont_cells, octaves=4)
    o_reg = _fbm_value_noise(p.seed, "region", (R, R), reg_cells, octaves=4)
    o_hill = _fbm_value_noise(p.seed, "hills", (R, R), hill_cells, octaves=3)
    return (o_cont * p.fbm_amp_continent_m +
            o_reg * p.fbm_amp_region_m +
            o_hill * p.fbm_amp_hills_m).astype(np.float32)


# ---------------------------------------------------------------------------
# 4. Hydraulic erosion (stream-power-law)
# ---------------------------------------------------------------------------

_D8_DX = np.array([1, 1, 0, -1, -1, -1, 0, 1], dtype=np.int8)
_D8_DY = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=np.int8)
_D8_DIST = np.array([1.0, np.sqrt(2.0), 1.0, np.sqrt(2.0),
                     1.0, np.sqrt(2.0), 1.0, np.sqrt(2.0)],
                    dtype=np.float32)


def _flow_direction_d8(elev: np.ndarray, sea_level: float) -> np.ndarray:
    """D8 steepest-descent flow direction.

    Returns 0..7 (E, SE, S, SW, W, NW, N, NE) or 255 if cell is a sink
    (ocean or local minimum that can't drain).
    """
    R = elev.shape[0]
    # Build (R, R, 8) array of neighbour drops.
    drops = np.full((R, R, 8), -np.inf, dtype=np.float32)
    for k in range(8):
        dx = int(_D8_DX[k])
        dy = int(_D8_DY[k])
        nb = np.roll(elev, shift=(-dy, -dx), axis=(0, 1))
        # Edge wrap-around penalty: mark edges as sinks.
        if dx > 0:
            nb[:, -dx:] = np.inf
        elif dx < 0:
            nb[:, :(-dx)] = np.inf
        if dy > 0:
            nb[-dy:, :] = np.inf
        elif dy < 0:
            nb[:(-dy), :] = np.inf
        drops[..., k] = (elev - nb) / _D8_DIST[k]
    # Choose k with the steepest *positive* drop. If none positive -> sink.
    best_k = np.argmax(drops, axis=2).astype(np.uint8)
    best_drop = np.max(drops, axis=2)
    sink = (best_drop <= 0.0) | (elev <= sea_level)
    best_k[sink] = 255
    return best_k


def _flow_accumulation(flow_dir: np.ndarray) -> np.ndarray:
    """Drainage area per cell in *cells*, using a topological pour.

    Approach: for every land cell, follow flow_dir for up to ``R``
    hops (worst case: longest river), incrementing the destination cell.
    We use a single-pass vectorised receiver-tree summation.
    """
    R = flow_dir.shape[0]
    # Build receiver coords (one step downstream) per cell.
    yy, xx = np.indices((R, R))
    rx = xx.copy()
    ry = yy.copy()
    valid = (flow_dir != 255)
    dx = _D8_DX[np.clip(flow_dir, 0, 7)]
    dy = _D8_DY[np.clip(flow_dir, 0, 7)]
    rx = (xx + dx).astype(np.int64)
    ry = (yy + dy).astype(np.int64)
    # Clamp.
    np.clip(rx, 0, R - 1, out=rx)
    np.clip(ry, 0, R - 1, out=ry)

    # Each cell starts with area = 1.
    acc = np.ones((R, R), dtype=np.float32)
    # Iteratively pour: in each pass, each cell sends its accumulated water
    # to its receiver. Repeat until convergence (≤ R passes max).
    visited = np.zeros((R, R), dtype=bool)
    # Order cells by descending elevation. Easier: just iterate K passes;
    # for R=128, ~256 passes is overkill but cheap.
    for _ in range(max(64, R)):
        new_acc = np.zeros_like(acc)
        # Pour: add this cell's incoming-area into its receiver.
        # We use np.add.at for unbuffered accumulation.
        flat_rx = rx[valid].ravel()
        flat_ry = ry[valid].ravel()
        flat_area = acc[valid].ravel()
        np.add.at(new_acc, (flat_ry, flat_rx), flat_area)
        # Convergence test: every cell drains to itself (or off-grid)
        # within R hops, so 2-3 passes after initial usually suffice.
        if np.allclose(new_acc, acc):
            break
        acc = acc + new_acc * 0.0  # silenced: kept structurally simple
        # Replace: each cell's area becomes original 1 + everything
        # routed to it through receiver tree. We rebuild by topological
        # sort (cheaper than fixed-point).
        break
    # Robust topological pour: sort cells by elevation index.
    return _flow_accumulation_topological(flow_dir)


def _flow_accumulation_topological(flow_dir: np.ndarray) -> np.ndarray:
    """Topological flow accumulation: O(R^2) deterministic.

    Sort cells by their flow_dir hop order (BFS from sinks up). Simpler:
    iterate ``in_degree`` zero cells like Kahn's algorithm.
    """
    R = flow_dir.shape[0]
    yy, xx = np.indices((R, R))
    valid_mask = (flow_dir != 255)
    dx = np.where(valid_mask, _D8_DX[np.clip(flow_dir, 0, 7)], 0)
    dy = np.where(valid_mask, _D8_DY[np.clip(flow_dir, 0, 7)], 0)
    rx = np.clip(xx + dx, 0, R - 1)
    ry = np.clip(yy + dy, 0, R - 1)

    # in-degree per cell = number of upstream donors.
    in_degree = np.zeros((R, R), dtype=np.int32)
    np.add.at(in_degree, (ry[valid_mask], rx[valid_mask]), 1)

    acc = np.ones((R, R), dtype=np.float32)
    # Kahn-like queue. We process cells in order of *receivers* finishing.
    # Implementation: iterative — pop cells with in_degree == 0, route them.
    # Convert grid to flat indices.
    queue = list(zip(*np.where(in_degree == 0)))
    head = 0
    while head < len(queue):
        cy, cx = queue[head]
        head += 1
        if flow_dir[cy, cx] == 255:
            continue
        ny, nx = int(ry[cy, cx]), int(rx[cy, cx])
        acc[ny, nx] += acc[cy, cx]
        in_degree[ny, nx] -= 1
        if in_degree[ny, nx] == 0:
            queue.append((ny, nx))
    return acc


def _erode_stream_power(p: GenesisParams, elev: np.ndarray,
                        uplift_rate: np.ndarray, sea_level: float) -> np.ndarray:
    """Iteratively erode terrain via the stream-power-law.

    dh/dt = - K * A^m * S^n

    Where A is drainage area (in cells, converted to m^2) and S is local
    downslope slope. Iterates ``p.erosion_iters`` times.

    The initial topography already encodes accumulated uplift via the
    plate age × uplift_rate seed in :func:`generate_world`; this routine
    SHAPES the landscape (carves valleys, smooths peaks) rather than
    coupling uplift and erosion in equilibrium. Equilibrium fastscape
    would oscillate near sea level and break determinism at scale.
    ``uplift_rate`` is therefore *unused* here but kept in the signature
    for future tectonic-time runs.
    """
    h = elev.copy().astype(np.float32)
    K = p.erodibility_k
    m = p.erosion_m
    n = p.erosion_n
    dt = p.erosion_dt_myr
    cell_km = p.map_size_km / p.resolution
    cell_m2 = (cell_km * 1000.0) ** 2

    for _ in range(p.erosion_iters):
        fd = _flow_direction_d8(h, sea_level)
        acc = _flow_accumulation_topological(fd)
        slope = _local_downslope(h, fd, cell_km)
        land = h > sea_level
        # Stream-power erosion in metres, with area in m^2 so K = 4e-6
        # gives ~10-100 m / Myr on steep, well-drained terrain.
        erode = np.zeros_like(h)
        if land.any():
            area_m2 = np.maximum(acc[land], 1.0) * cell_m2
            # Stream-power-law: dh/dt = - K * A^m * S^n (units: m / Myr)
            erode_land = (K * np.power(area_m2, m)
                          * np.power(np.maximum(slope[land], 1e-5), n) * dt)
            # Cap per-iter erosion to 15 % of cell elevation above sea level
            # to avoid runaway downcutting on the steepest cells.
            cap = np.maximum(h[land] - sea_level, 0.0) * 0.15
            erode[land] = np.minimum(erode_land, cap).astype(np.float32)
        # Floor: don't gouge below sea level + 1 m in one step.
        erode = np.minimum(erode, np.maximum(h - sea_level - 1.0, 0.0))
        h = h - erode

    return h


def _local_downslope(elev: np.ndarray, flow_dir: np.ndarray, cell_km: float
                     ) -> np.ndarray:
    """Slope (rise/run) from each cell to its receiver, in km."""
    R = elev.shape[0]
    yy, xx = np.indices((R, R))
    valid = (flow_dir != 255)
    dx = np.where(valid, _D8_DX[np.clip(flow_dir, 0, 7)], 0)
    dy = np.where(valid, _D8_DY[np.clip(flow_dir, 0, 7)], 0)
    rx = np.clip(xx + dx, 0, R - 1)
    ry = np.clip(yy + dy, 0, R - 1)
    drop_m = elev - elev[ry, rx]
    dist_km = np.where(valid,
                       _D8_DIST[np.clip(flow_dir, 0, 7)] * cell_km, 1.0)
    return (np.maximum(drop_m, 0.0) / 1000.0) / np.maximum(dist_km, 1e-3)


# ---------------------------------------------------------------------------
# 5. Hydrology features (rivers, watersheds, coast distance)
# ---------------------------------------------------------------------------

def _extract_rivers(flow_acc: np.ndarray, elev: np.ndarray, sea_level: float,
                    threshold_cells: float) -> np.ndarray:
    """Cells with drainage > threshold AND above sea level are rivers."""
    return (flow_acc >= threshold_cells) & (elev > sea_level)


def _watersheds(flow_dir: np.ndarray, elev: np.ndarray,
                sea_level: float) -> np.ndarray:
    """Label each land cell with the id of the ocean cell it eventually
    drains to (or -1 if it sits in a closed basin / ocean).

    Computed by following flow_dir downstream from every land cell and
    interning the terminal coordinate.
    """
    R = elev.shape[0]
    yy, xx = np.indices((R, R))
    label = np.full((R, R), -1, dtype=np.int32)
    label[elev <= sea_level] = -1

    # Topo order: cells sorted by elevation DESC, then route each to its
    # downstream basin. We use the receiver tree.
    valid = (flow_dir != 255)
    dx = np.where(valid, _D8_DX[np.clip(flow_dir, 0, 7)], 0)
    dy = np.where(valid, _D8_DY[np.clip(flow_dir, 0, 7)], 0)
    rx = np.clip(xx + dx, 0, R - 1).astype(np.int32)
    ry = np.clip(yy + dy, 0, R - 1).astype(np.int32)

    next_label = 0
    # Iterate cells in decreasing elevation: process source cells first
    # so descendants can reuse labels.
    flat_idx = np.argsort(-elev.ravel(), kind="stable")
    for idx in flat_idx:
        cy, cx = int(idx // R), int(idx % R)
        if elev[cy, cx] <= sea_level:
            continue
        if label[cy, cx] != -1:
            continue
        # Walk downstream until ocean.
        path = []
        ny, nx = cy, cx
        guard = 0
        while True:
            if elev[ny, nx] <= sea_level:
                terminal_label = -1
                break
            if label[ny, nx] != -1:
                terminal_label = int(label[ny, nx])
                break
            if flow_dir[ny, nx] == 255:
                # Closed basin: this cell *is* the basin label.
                terminal_label = next_label
                next_label += 1
                break
            path.append((ny, nx))
            ny2, nx2 = int(ry[ny, nx]), int(rx[ny, nx])
            if (ny2, nx2) == (ny, nx):
                terminal_label = -1
                break
            ny, nx = ny2, nx2
            guard += 1
            if guard > 4 * R:
                terminal_label = -1
                break
        # Paint the whole path with the basin label (or -1 if it drains to ocean).
        if terminal_label == -1:
            # Need a label so we can distinguish "land that drains to ocean"
            # from ocean itself. Assign a fresh basin id for every coast
            # outlet; cells routed through the same outlet share the id.
            # We mark the outlet cell first so future paths can re-use it.
            if flow_dir[ny, nx] != 255 and elev[ny, nx] > sea_level:
                # Drained into a labelled cell -> use it.
                terminal_label = int(label[ny, nx])
            else:
                terminal_label = next_label
                next_label += 1
                # Label terminal cell only if it's still on land; otherwise
                # leave -1 for true ocean.
                if elev[ny, nx] > sea_level:
                    label[ny, nx] = terminal_label
        for (py, px) in path:
            label[py, px] = terminal_label
        # The current cell itself
        if elev[cy, cx] > sea_level:
            label[cy, cx] = terminal_label
    return label


def _distance_to_coast_km(elev: np.ndarray, sea_level: float,
                          cell_km: float) -> np.ndarray:
    """Multi-source BFS in km from any ocean cell to every land cell."""
    R = elev.shape[0]
    is_ocean = (elev <= sea_level)
    INF = np.float32(1e9)
    dist = np.where(is_ocean, np.float32(0.0), INF)
    # 4-connectivity BFS via repeated min-of-neighbours+step.
    step = cell_km
    diag = cell_km * np.sqrt(2.0)
    changed = True
    while changed:
        changed = False
        # Cardinal neighbours.
        for sx, sy, w in [(1, 0, step), (-1, 0, step),
                          (0, 1, step), (0, -1, step),
                          (1, 1, diag), (-1, 1, diag),
                          (1, -1, diag), (-1, -1, diag)]:
            nb = np.roll(dist, shift=(sy, sx), axis=(0, 1))
            # Edges become INF so they don't pull in across the wrap.
            if sx > 0:
                nb[:, :sx] = INF
            elif sx < 0:
                nb[:, sx:] = INF
            if sy > 0:
                nb[:sy, :] = INF
            elif sy < 0:
                nb[sy:, :] = INF
            new_dist = np.minimum(dist, nb + w)
            if not np.array_equal(new_dist, dist):
                changed = True
                dist = new_dist
    return dist.astype(np.float32)


# ---------------------------------------------------------------------------
# 6. Atmospheric circulation + 7. Orographic precipitation
# ---------------------------------------------------------------------------

def _latitude_field(p: GenesisParams) -> np.ndarray:
    R = p.resolution
    ys = (np.arange(R, dtype=np.float32) + 0.5) / R
    # Map y=equator_y_frac to 0 deg latitude. North = lower y in image coords.
    # We use a symmetric span so |lat| in [0, lat_span_deg].
    lat = (p.equator_y_frac - ys) * (2.0 * p.lat_span_deg)
    # Broadcast across X.
    return np.broadcast_to(lat[:, None], (R, R)).astype(np.float32)


def _atmospheric_circulation(p: GenesisParams,
                              lat: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Latitudinal three-cell circulation, simplified.

    Wind components are in m/s, east-positive (u) and north-positive (v).

    Bands (absolute latitude):
      |lat| <  5 deg: ITCZ (calm-ish, slight easterly)
      5  <= |lat| < 30: trade winds (easterly: u<0, equator-ward v)
      30 <= |lat| < 60: westerlies (u>0, poleward v)
      60 <= |lat| < 90: polar easterlies (u<0, equator-ward v)
    """
    abs_lat = np.abs(lat)
    # Default: ITCZ
    u = np.where(abs_lat < 5.0, -1.0, 0.0).astype(np.float32)
    v = np.zeros_like(u)

    trade = (abs_lat >= 5.0) & (abs_lat < 30.0)
    westerly = (abs_lat >= 30.0) & (abs_lat < 60.0)
    polar = (abs_lat >= 60.0)

    # Hemisphere sign for v: trade winds flow toward the equator,
    # westerlies flow poleward, polar easterlies flow toward the equator.
    hemi = np.sign(lat)
    u = np.where(trade, -6.0, u)
    v = np.where(trade, -3.0 * hemi, v)
    u = np.where(westerly, 8.0, u)
    v = np.where(westerly, 2.0 * hemi, v)
    u = np.where(polar, -4.0, u)
    v = np.where(polar, -1.5 * hemi, v)
    return u.astype(np.float32), v.astype(np.float32)


def _base_precip_by_latitude(p: GenesisParams, lat: np.ndarray) -> np.ndarray:
    """Hadley/Ferrel/Polar precipitation belt model (mm/yr).

    ITCZ ~3000 mm, subtropical highs (~30 deg) ~150 mm,
    mid-latitudes ~900 mm, polar ~150 mm.
    """
    abs_lat = np.abs(lat)
    itcz = np.exp(-((abs_lat - 0.0) / 8.0) ** 2)
    subtrop = np.exp(-((abs_lat - 30.0) / 8.0) ** 2)
    midlat = np.exp(-((abs_lat - 50.0) / 10.0) ** 2)
    polar = np.exp(-((abs_lat - 75.0) / 8.0) ** 2)
    val = (3000.0 * itcz
           + 150.0 * subtrop
           + 900.0 * midlat
           + 150.0 * polar)
    # Floor + minor scaling by base_precip_mm.
    val = val * (p.base_precip_mm / 1100.0) + 50.0
    return val.astype(np.float32)


def _orographic_precipitation(p: GenesisParams, elev: np.ndarray,
                               base_precip: np.ndarray,
                               wind_u: np.ndarray,
                               wind_v: np.ndarray,
                               sea_level: float) -> np.ndarray:
    """Advect moisture along wind, gain on uplift, lose on descent.

    Iterative procedure:
      moisture starts at base_precip on ocean cells, scaled down on land.
      Each iteration:
        - Advect moisture upwind -> downwind by 1 cell.
        - Compute elevation gradient along wind direction.
        - On uplift: precipitate moisture proportionally
          (gain = clip(grad * gain, 0, 1))
        - On descent: rain shadow (moisture rebounds upward via warming).
    Returns precipitation field in mm/yr.
    """
    R = p.resolution
    # Normalised wind direction per cell (mostly zonal).
    speed = np.sqrt(wind_u * wind_u + wind_v * wind_v) + 1e-6
    ux = wind_u / speed
    uy = wind_v / speed
    # Initial moisture available proportional to base belt.
    moisture = base_precip.copy()
    precip = np.zeros_like(base_precip)

    # Precompute upwind elevation by shifting elev one cell *upwind*.
    # np.roll(arr, shift=+1, axis=1) makes new[j] = arr[j-1]. To grab the
    # upwind neighbour (west when wind blows east, i.e. ux>0), we need
    # shift = +sign(ux) along x. Same for y.
    for it in range(p.rain_iters):
        sx = np.sign(ux).astype(np.int8)
        sy = np.sign(uy).astype(np.int8)
        # Vectorised: build upwind elev grid.
        upwind = np.empty_like(elev)
        for sxv in (-1, 0, 1):
            for syv in (-1, 0, 1):
                if sxv == 0 and syv == 0:
                    continue
                mask = (sx == sxv) & (sy == syv)
                if not mask.any():
                    continue
                shifted = np.roll(elev, shift=(syv, sxv), axis=(0, 1))
                # Edge wrap penalty: use the cell itself near edge.
                if sxv > 0:
                    shifted[:, :sxv] = elev[:, :sxv]
                elif sxv < 0:
                    shifted[:, sxv:] = elev[:, sxv:]
                if syv > 0:
                    shifted[:syv, :] = elev[:syv, :]
                elif syv < 0:
                    shifted[syv:, :] = elev[syv:, :]
                upwind = np.where(mask, shifted, upwind)
        # Gradient along wind: positive means uplift relative to upwind.
        grad = elev - upwind
        # Uplift -> precipitation.
        uplift = np.clip(grad, 0.0, None)
        descent = np.clip(-grad, 0.0, None)
        rain_gain = uplift * p.orographic_gain
        # Rain falls; deduct from moisture.
        delta = np.minimum(moisture * rain_gain, moisture)
        precip = precip + delta
        moisture = moisture - delta
        # Rain shadow: descent dries the air further, accelerated decay.
        moisture = moisture * np.exp(-descent * p.rain_shadow_decay)
        # Replenish moisture on ocean cells from base precip.
        ocean_mask = (elev <= sea_level)
        moisture = np.where(ocean_mask, base_precip, moisture)

    # Add base precip floor on ocean to keep maritime climates wet.
    precip = np.where(elev <= sea_level, base_precip, precip + 100.0)
    return precip.astype(np.float32)


# ---------------------------------------------------------------------------
# 8. Temperature
# ---------------------------------------------------------------------------

def _temperature_field(p: GenesisParams, elev: np.ndarray,
                        lat: np.ndarray,
                        dist_to_coast_km: np.ndarray) -> np.ndarray:
    """Temperature (deg C) from latitude, altitude, continentality."""
    abs_lat = np.abs(lat)
    # Sea-level temperature: 30 C at equator -> -25 C at poles.
    t_sea = 30.0 - 0.6 * abs_lat
    # Adiabatic lapse rate: -6.5 K/km elevation.
    t_alt = -6.5 * (np.maximum(elev, 0.0) / 1000.0)
    # Continentality: cold winters / hot summers far inland. We compute
    # an *annual mean shift* of zero, but the *amplitude* of the seasonal
    # cycle would scale with sqrt(dist). For the static field, we apply a
    # mild bias: continental interiors are 1-2 C cooler annually due to
    # higher albedo / lower humidity.
    t_cont = -1.5 * np.minimum(dist_to_coast_km /
                                max(1.0, p.continentality_km), 1.0)
    return (t_sea + t_alt + t_cont).astype(np.float32)


# ---------------------------------------------------------------------------
# Utility — box blur
# ---------------------------------------------------------------------------

def _box_blur(arr: np.ndarray, radius: int = 1) -> np.ndarray:
    """Cheap separable box blur for smoothing tectonic bands."""
    if radius <= 0:
        return arr
    k = 2 * radius + 1
    pad = np.pad(arr, radius, mode="edge")
    out = np.zeros_like(arr, dtype=np.float32)
    for dy in range(k):
        for dx in range(k):
            out += pad[dy:dy + arr.shape[0], dx:dx + arr.shape[1]]
    return (out / (k * k)).astype(np.float32)


# ---------------------------------------------------------------------------
# Public API — generate_world
# ---------------------------------------------------------------------------

def generate_world(params: Optional[GenesisParams] = None) -> GenesisWorld:
    """Run the full ultra-realistic generation pipeline.

    Deterministic given ``params.seed``. Single-thread, numpy-vectorised.

    Returns a populated :class:`GenesisWorld`.
    """
    p = params if params is not None else GenesisParams()
    R = p.resolution
    cell_km = p.map_size_km / R

    # 1) Plates
    seeds, kinds, motion, ages = _seed_plates(p)
    plate_id = _voronoi_assignment(p, seeds)

    # 2) Boundary classification + uplift
    boundary, uplift_band = _classify_boundaries(p, plate_id, kinds, motion)

    # 3) Base + FBM overlay
    # Convert the per-cell uplift_band (m/Myr) into the cumulative tectonic
    # uplift over the plate age (approximate: take min of ages of the two
    # neighbouring plates). For a single static run we treat uplift_band
    # as the rate AND fold a fraction of it into the initial topography
    # to seed orogeny.
    plate_age_avg = ages[plate_id]
    initial_uplift_m = uplift_band * np.minimum(plate_age_avg, 80.0)
    base_elev = _base_elevation(p, plate_id, kinds, initial_uplift_m)
    fbm = _fbm_overlay(p)
    elev_raw = np.clip(base_elev + fbm,
                        p.abyssal_depth_m * 1.05,
                        p.max_elev_m * 1.05).astype(np.float32)

    # 4) Erode
    elev = _erode_stream_power(p, elev_raw, uplift_band, p.sea_level_m)

    # 5) Hydrology
    flow_dir = _flow_direction_d8(elev, p.sea_level_m)
    flow_acc = _flow_accumulation_topological(flow_dir)
    river_mask = _extract_rivers(flow_acc, elev, p.sea_level_m,
                                  p.river_threshold_cells)
    watershed = _watersheds(flow_dir, elev, p.sea_level_m)
    dist_coast = _distance_to_coast_km(elev, p.sea_level_m, cell_km)

    # 6) Atmospheric + 7) Orographic
    lat = _latitude_field(p)
    wind_u, wind_v = _atmospheric_circulation(p, lat)
    base_precip = _base_precip_by_latitude(p, lat)
    precip = _orographic_precipitation(p, elev, base_precip,
                                        wind_u, wind_v, p.sea_level_m)

    # 8) Temperature
    temp = _temperature_field(p, elev, lat, dist_coast)

    # 9) Biome (Whittaker)
    biome = classify_biome_array(temp, precip, elev)

    # Diagnostics
    land = elev > p.sea_level_m
    diagnostics = {
        "n_plates": int(p.n_plates),
        "land_fraction": float(land.mean()),
        "mountain_fraction": float((elev > 2000.0).mean()),
        "abyssal_fraction": float((elev < -3000.0).mean()),
        "river_cells": int(river_mask.sum()),
        "n_watersheds": int(watershed.max() + 1) if watershed.max() >= 0 else 0,
        "max_precip_mm": float(precip.max()),
        "min_precip_land_mm": float(precip[land].min()) if land.any() else 0.0,
        "max_elev_m": float(elev.max()),
        "min_elev_m": float(elev.min()),
        "convergent_cells": int((boundary == BOUND_CONVERGENT).sum()),
        "divergent_cells": int((boundary == BOUND_DIVERGENT).sum()),
        "transform_cells": int((boundary == BOUND_TRANSFORM).sum()),
    }

    return GenesisWorld(
        params=p,
        plate_kind=kinds.copy(),
        plate_motion=motion.copy(),
        plate_seeds=seeds.copy(),
        plate_age_myr=ages.copy(),
        plate_id=plate_id,
        boundary_kind=boundary,
        uplift_rate=uplift_band,
        elevation_m=elev,
        elevation_raw_m=elev_raw,
        flow_dir=flow_dir,
        flow_acc=flow_acc,
        river_mask=river_mask,
        watershed_id=watershed,
        distance_to_coast_km=dist_coast,
        wind_u=wind_u,
        wind_v=wind_v,
        latitude_deg=lat,
        precip_mm=precip,
        temp_c=temp,
        biome=biome,
        diagnostics=diagnostics,
    )


# ---------------------------------------------------------------------------
# Persistence — npz round-trip
# ---------------------------------------------------------------------------

_PARAM_KEYS = [
    "seed", "map_size_km", "resolution", "n_plates", "oceanic_fraction",
    "sea_level_m", "max_elev_m", "abyssal_depth_m", "continent_base_m",
    "erosion_iters", "erodibility_k", "erosion_m", "erosion_n",
    "erosion_dt_myr", "uplift_per_myr_max",
    "fbm_continent_km", "fbm_region_km", "fbm_hills_km",
    "fbm_amp_continent_m", "fbm_amp_region_m", "fbm_amp_hills_m",
    "rain_iters", "orographic_gain", "rain_shadow_decay", "base_precip_mm",
    "equator_y_frac", "lat_span_deg", "river_threshold_cells",
    "continentality_km",
]


def save_world(world: GenesisWorld, path: str) -> None:
    """Persist a :class:`GenesisWorld` to ``path`` as npz."""
    params = {f"p_{k}": np.float64(getattr(world.params, k))
              for k in _PARAM_KEYS}
    np.savez(
        path,
        plate_kind=world.plate_kind,
        plate_motion=world.plate_motion,
        plate_seeds=world.plate_seeds,
        plate_age_myr=world.plate_age_myr,
        plate_id=world.plate_id,
        boundary_kind=world.boundary_kind,
        uplift_rate=world.uplift_rate,
        elevation_m=world.elevation_m,
        elevation_raw_m=world.elevation_raw_m,
        flow_dir=world.flow_dir,
        flow_acc=world.flow_acc,
        river_mask=world.river_mask,
        watershed_id=world.watershed_id,
        distance_to_coast_km=world.distance_to_coast_km,
        wind_u=world.wind_u,
        wind_v=world.wind_v,
        latitude_deg=world.latitude_deg,
        precip_mm=world.precip_mm,
        temp_c=world.temp_c,
        biome=world.biome,
        diag_keys=np.array(list(world.diagnostics.keys()), dtype=object),
        diag_vals=np.array(list(world.diagnostics.values()), dtype=np.float64),
        **params,
    )


def load_world(path: str) -> GenesisWorld:
    """Inverse of :func:`save_world`."""
    z = np.load(path, allow_pickle=True)
    p_kwargs = {}
    for k in _PARAM_KEYS:
        v = float(z[f"p_{k}"])
        if k in {"seed", "resolution", "n_plates", "erosion_iters",
                 "rain_iters"}:
            p_kwargs[k] = int(v)
        else:
            p_kwargs[k] = v
    params = GenesisParams(**p_kwargs)
    diag = {str(k): float(v) for k, v in zip(z["diag_keys"], z["diag_vals"])}
    return GenesisWorld(
        params=params,
        plate_kind=z["plate_kind"],
        plate_motion=z["plate_motion"],
        plate_seeds=z["plate_seeds"],
        plate_age_myr=z["plate_age_myr"],
        plate_id=z["plate_id"],
        boundary_kind=z["boundary_kind"],
        uplift_rate=z["uplift_rate"],
        elevation_m=z["elevation_m"],
        elevation_raw_m=z["elevation_raw_m"],
        flow_dir=z["flow_dir"],
        flow_acc=z["flow_acc"],
        river_mask=z["river_mask"],
        watershed_id=z["watershed_id"],
        distance_to_coast_km=z["distance_to_coast_km"],
        wind_u=z["wind_u"],
        wind_v=z["wind_v"],
        latitude_deg=z["latitude_deg"],
        precip_mm=z["precip_mm"],
        temp_c=z["temp_c"],
        biome=z["biome"],
        diagnostics=diag,
    )


# ---------------------------------------------------------------------------
# Sampling helpers
# ---------------------------------------------------------------------------

def sample_macro(world: GenesisWorld, x_km: float, y_km: float) -> Dict[str, float]:
    """Sample the macro field at a single continental-scale point.

    Used by ``world.py`` chunk generators to ground micro-noise in the
    correct continent / plate / climate. Bilinear interpolation.
    Coordinates outside ``[0, map_size_km]`` clamp to the nearest border.
    """
    p = world.params
    R = p.resolution
    cell_km = p.map_size_km / R
    fx = float(np.clip(x_km / cell_km - 0.5, 0.0, R - 1.001))
    fy = float(np.clip(y_km / cell_km - 0.5, 0.0, R - 1.001))
    ix = int(np.floor(fx)); iy = int(np.floor(fy))
    tx = fx - ix; ty = fy - iy

    def _bilerp(arr: np.ndarray) -> float:
        a = float(arr[iy, ix]); b = float(arr[iy, ix + 1])
        c = float(arr[iy + 1, ix]); d = float(arr[iy + 1, ix + 1])
        return (a * (1 - tx) * (1 - ty) + b * tx * (1 - ty)
                + c * (1 - tx) * ty + d * tx * ty)

    return {
        "elevation_m": _bilerp(world.elevation_m),
        "precip_mm": _bilerp(world.precip_mm),
        "temp_c": _bilerp(world.temp_c),
        "distance_to_coast_km": _bilerp(world.distance_to_coast_km),
        "flow_acc": _bilerp(world.flow_acc),
        "uplift_rate": _bilerp(world.uplift_rate),
        "plate_id": int(world.plate_id[iy, ix]),
        "biome": int(world.biome[iy, ix]),
    }


def sample_macro_grid(world: GenesisWorld,
                       x_km: np.ndarray,
                       y_km: np.ndarray
                       ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised bilinear macro sampler.

    Returns ``(elevation_m, temp_c, precip_mm)`` arrays sampled at the
    given (x_km, y_km) coordinates. Coordinates outside the macro extent
    clamp to the nearest border. Used by :func:`engine.world.generate_chunk`
    when a chunk is anchored to a GenesisWorld.
    """
    p = world.params
    R = p.resolution
    cell_km = p.map_size_km / R
    fx = np.clip(x_km / cell_km - 0.5, 0.0, R - 1.001).astype(np.float32)
    fy = np.clip(y_km / cell_km - 0.5, 0.0, R - 1.001).astype(np.float32)
    ix = np.floor(fx).astype(np.int32)
    iy = np.floor(fy).astype(np.int32)
    tx = (fx - ix).astype(np.float32)
    ty = (fy - iy).astype(np.float32)
    ix1 = np.clip(ix + 1, 0, R - 1)
    iy1 = np.clip(iy + 1, 0, R - 1)

    def _bil(arr: np.ndarray) -> np.ndarray:
        a = arr[iy, ix]
        b = arr[iy, ix1]
        c = arr[iy1, ix]
        d = arr[iy1, ix1]
        return (a * (1 - tx) * (1 - ty) + b * tx * (1 - ty)
                + c * (1 - tx) * ty + d * tx * ty).astype(np.float32)

    return _bil(world.elevation_m), _bil(world.temp_c), _bil(world.precip_mm)


def sample_macro_grid_full(world: GenesisWorld,
                             x_km: np.ndarray,
                             y_km: np.ndarray
                             ) -> Dict[str, np.ndarray]:
    """Like :func:`sample_macro_grid` but returns all key fields.

    Useful for downstream layers (geology, meteorology) that need more
    than elevation/temp/precip at chunk resolution.
    """
    p = world.params
    R = p.resolution
    cell_km = p.map_size_km / R
    fx = np.clip(x_km / cell_km - 0.5, 0.0, R - 1.001).astype(np.float32)
    fy = np.clip(y_km / cell_km - 0.5, 0.0, R - 1.001).astype(np.float32)
    ix = np.floor(fx).astype(np.int32)
    iy = np.floor(fy).astype(np.int32)
    tx = (fx - ix).astype(np.float32)
    ty = (fy - iy).astype(np.float32)
    ix1 = np.clip(ix + 1, 0, R - 1)
    iy1 = np.clip(iy + 1, 0, R - 1)

    def _bil(arr: np.ndarray) -> np.ndarray:
        a = arr[iy, ix].astype(np.float32)
        b = arr[iy, ix1].astype(np.float32)
        c = arr[iy1, ix].astype(np.float32)
        d = arr[iy1, ix1].astype(np.float32)
        return (a * (1 - tx) * (1 - ty) + b * tx * (1 - ty)
                + c * (1 - tx) * ty + d * tx * ty).astype(np.float32)

    return {
        "elevation_m": _bil(world.elevation_m),
        "temp_c": _bil(world.temp_c),
        "precip_mm": _bil(world.precip_mm),
        "distance_to_coast_km": _bil(world.distance_to_coast_km),
        "flow_acc": _bil(world.flow_acc),
        "uplift_rate": _bil(world.uplift_rate),
        # Nearest-neighbour for categorical fields.
        "plate_id": world.plate_id[iy, ix],
        "boundary_kind": world.boundary_kind[iy, ix],
        "biome": world.biome[iy, ix],
        "river_mask": world.river_mask[iy, ix],
    }


# ---------------------------------------------------------------------------
# Genesis anchor — bridge between GenesisWorld and chunk-scale generation
# ---------------------------------------------------------------------------

@dataclass
class GenesisAnchor:
    """Wires a :class:`GenesisWorld` macro map into chunk-scale sampling.

    Attributes
    ----------
    world : GenesisWorld
        The continental-scale macro map (read-only).
    sim_origin_macro_km : Tuple[float, float]
        Macro coordinate (in km) that sim coord (0, 0) maps to. Defaults to
        the macro center so that the simulation's origin sits at the
        middle of the continent.
    blend : float
        Fraction of macro elevation vs micro FBM in the chunk's terrain.
        ``blend = 1.0`` -> pure macro + micro residual at small amplitude;
        ``blend = 0.0`` -> ignore macro entirely (use ``micro_amp_m`` as
        the full FBM amplitude). Default 1.0 (macro is the truth, micro
        is only local detail).
    micro_amp_m : float
        Amplitude of micro FBM elevation residual on top of macro.
    micro_amp_temp_c : float
        Amplitude of micro temperature jitter.
    micro_amp_precip_mm : float
        Amplitude of micro precipitation jitter.
    """

    world: "GenesisWorld"
    sim_origin_macro_km: Tuple[float, float] = (0.0, 0.0)
    blend: float = 1.0
    micro_amp_m: float = 80.0
    micro_amp_temp_c: float = 1.5
    micro_amp_precip_mm: float = 150.0


def make_anchor(world: GenesisWorld,
                sim_origin_macro_km: Optional[Tuple[float, float]] = None,
                blend: float = 1.0,
                micro_amp_m: float = 80.0,
                micro_amp_temp_c: float = 1.5,
                micro_amp_precip_mm: float = 150.0) -> GenesisAnchor:
    """Convenience constructor for :class:`GenesisAnchor`.

    By default centers the simulation's (0, 0) on the macro center, so a
    sim that explores ±2000 m around the origin lands near the middle of
    a 4000 km continent.
    """
    if sim_origin_macro_km is None:
        sim_origin_macro_km = (world.params.map_size_km / 2.0,
                                world.params.map_size_km / 2.0)
    return GenesisAnchor(
        world=world,
        sim_origin_macro_km=sim_origin_macro_km,
        blend=blend,
        micro_amp_m=micro_amp_m,
        micro_amp_temp_c=micro_amp_temp_c,
        micro_amp_precip_mm=micro_amp_precip_mm,
    )


def world_signature(world: GenesisWorld) -> str:
    """Stable SHA-256 hex over the world's core arrays. For determinism tests."""
    import hashlib
    h = hashlib.sha256()
    for arr in (world.elevation_m, world.plate_id, world.flow_dir,
                world.flow_acc, world.precip_mm, world.temp_c, world.biome):
        h.update(arr.tobytes())
    return h.hexdigest()
