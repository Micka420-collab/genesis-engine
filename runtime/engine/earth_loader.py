"""Real-Earth geospatial loader for Genesis Engine.

Streams DEM (Copernicus DEM GLO-30 on AWS Open Data), land cover (ESA
WorldCover 10m), and optional climate (CHELSA) / hydrography (HydroSHEDS)
into the existing ``engine.world.Chunk`` raster grid.

Design goals:
  * Never download a whole tile -- always stream via ``rasterio.windows``.
  * Local azimuthal-equidistant projection centred on the simulation origin
    so a metric chunk grid translates cleanly to lat/lon.
  * Graceful offline fallback: any missing dependency or unreachable data
    source causes ``chunk_data`` to return ``None``, so the caller can fall
    back to the procedural ``generate_chunk`` path.
  * Determinism: any noise we inject uses a stable BLAKE2b-derived seed,
    matching the convention in ``engine.world._stable_layer_salt``.

The module is intentionally tolerant: optional imports (rasterio, pyproj,
fiona, boto3) are guarded so the engine still imports cleanly on minimal
installations.
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np

# --- Chunk geometry must match engine.world ----------------------------------
try:
    from engine.world import CHUNK_SIZE, VOXEL_SIZE_M, CHUNK_SIDE_M, Biome
except Exception:  # pragma: no cover - defensive fallback for standalone use
    CHUNK_SIZE = 64
    VOXEL_SIZE_M = 0.5
    CHUNK_SIDE_M = CHUNK_SIZE * VOXEL_SIZE_M

    class Biome:  # type: ignore[no-redef]
        OCEAN = 0
        ICE = 1
        TUNDRA = 2
        BOREAL_FOREST = 3
        TEMPERATE_FOREST = 4
        TEMPERATE_RAINFOREST = 5
        GRASSLAND = 6
        HOT_DESERT = 7
        COLD_DESERT = 8
        SAVANNA = 9
        TROPICAL_DRY_FOREST = 10
        TROPICAL_RAINFOREST = 11


log = logging.getLogger(__name__)

# --- Optional heavy dependencies (all guarded) -------------------------------
try:
    import rasterio
    from rasterio.windows import from_bounds as _rio_from_bounds
    from rasterio.warp import transform_bounds as _rio_transform_bounds
    _HAS_RASTERIO = True
except Exception:  # pragma: no cover
    rasterio = None  # type: ignore[assignment]
    _HAS_RASTERIO = False

# Allow unsigned access to AWS Open Data buckets (Copernicus DEM, ESA
# WorldCover) — both are public and require no credentials. Setting this at
# module import time means callers don't need to remember the env var.
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
# Optional: speed up COG streaming by enabling GDAL's HTTP cache.
os.environ.setdefault("CPL_VSIL_CURL_USE_HEAD", "NO")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

try:
    from pyproj import CRS, Transformer
    _HAS_PYPROJ = True
except Exception:  # pragma: no cover
    _HAS_PYPROJ = False

try:
    import fiona  # noqa: F401  (only used if HydroSHEDS shapefile is present)
    _HAS_FIONA = True
except Exception:  # pragma: no cover
    _HAS_FIONA = False


# ---------------------------------------------------------------------------
# Determinism helpers
# ---------------------------------------------------------------------------

def _stable_seed(*parts: Any) -> int:
    """BLAKE2b-based 64-bit seed derived from arbitrary parts.

    Matches the style of ``engine.world._stable_layer_salt`` so seeds are
    process-stable and platform-independent.
    """
    h = hashlib.blake2b(digest_size=8)
    for p in parts:
        h.update(repr(p).encode("utf-8"))
        h.update(b"|")
    return int.from_bytes(h.digest(), "little", signed=False)


# ---------------------------------------------------------------------------
# ESA WorldCover -> Genesis Biome mapping
# ---------------------------------------------------------------------------
#   10 tree cover, 20 shrubland, 30 grassland, 40 cropland,
#   50 built-up, 60 bare/sparse vegetation, 70 snow & ice,
#   80 permanent water, 90 herbaceous wetland, 95 mangroves,
#   100 moss & lichen.
#
# We map to the closest existing Biome enum, leaning on temperature later
# (from CHELSA or latitude fallback) to disambiguate tropical vs. temperate.
_ESA_TO_BIOME_BASE: Dict[int, int] = {
    10: int(Biome.TEMPERATE_FOREST),     # refined by temp/precip
    20: int(Biome.SAVANNA),              # shrubland; refined by temp
    30: int(Biome.GRASSLAND),
    40: int(Biome.GRASSLAND),            # cropland -> grassland-like NPP
    50: int(Biome.GRASSLAND),            # built-up: treat as cleared land
    60: int(Biome.HOT_DESERT),           # bare; refined by temp
    70: int(Biome.ICE),
    80: int(Biome.OCEAN),
    90: int(Biome.TEMPERATE_RAINFOREST), # wetland -> high water/NPP
    95: int(Biome.TROPICAL_RAINFOREST),  # mangrove -> tropical wet
    100: int(Biome.TUNDRA),              # moss & lichen
}


def _refine_biome(esa_class: int, temp_c: float, precip_mm: float) -> int:
    """Pick a Biome enum value using ESA class + climate."""
    if esa_class == 80:
        return int(Biome.OCEAN)
    if esa_class == 70:
        return int(Biome.ICE)
    if esa_class == 95:
        return int(Biome.TROPICAL_RAINFOREST)
    if esa_class == 100:
        return int(Biome.TUNDRA)

    if esa_class == 10:  # trees
        if temp_c < 0.0:
            return int(Biome.BOREAL_FOREST)
        if temp_c < 5.0:
            return int(Biome.BOREAL_FOREST)
        if temp_c < 20.0:
            return int(Biome.TEMPERATE_RAINFOREST) if precip_mm > 1500.0 \
                else int(Biome.TEMPERATE_FOREST)
        return int(Biome.TROPICAL_RAINFOREST) if precip_mm > 1500.0 \
            else int(Biome.TROPICAL_DRY_FOREST)

    if esa_class == 20:  # shrubland
        if temp_c < 0.0:
            return int(Biome.TUNDRA)
        return int(Biome.SAVANNA) if temp_c >= 20.0 else int(Biome.GRASSLAND)

    if esa_class in (30, 40, 50):
        if temp_c < 0.0:
            return int(Biome.TUNDRA)
        if temp_c >= 20.0 and precip_mm < 750.0:
            return int(Biome.SAVANNA)
        return int(Biome.GRASSLAND)

    if esa_class == 60:  # bare
        if temp_c < 0.0:
            return int(Biome.COLD_DESERT)
        return int(Biome.HOT_DESERT)

    if esa_class == 90:  # wetland
        if temp_c < 0.0:
            return int(Biome.TUNDRA)
        if temp_c >= 20.0:
            return int(Biome.TROPICAL_RAINFOREST)
        return int(Biome.TEMPERATE_RAINFOREST)

    return _ESA_TO_BIOME_BASE.get(esa_class, int(Biome.GRASSLAND))


# Per-biome resource priors (kg/m^2 stone+wood+metal, L/cell water, kcal/cell)
_BIOME_RESOURCE = {
    Biome.OCEAN: dict(stone=0.0, wood=0.0, metal=0.0, water=1000.0, food=150.0),
    Biome.ICE: dict(stone=20.0, wood=0.0, metal=0.0, water=0.0, food=25.0),
    Biome.TUNDRA: dict(stone=20.0, wood=2.0, metal=0.0, water=10.0, food=75.0),
    Biome.BOREAL_FOREST: dict(stone=10.0, wood=30.0, metal=0.0, water=20.0, food=275.0),
    Biome.TEMPERATE_FOREST: dict(stone=10.0, wood=50.0, metal=0.0, water=20.0, food=400.0),
    Biome.TEMPERATE_RAINFOREST: dict(stone=10.0, wood=50.0, metal=0.0, water=30.0, food=400.0),
    Biome.GRASSLAND: dict(stone=10.0, wood=2.0, metal=0.0, water=15.0, food=225.0),
    Biome.HOT_DESERT: dict(stone=30.0, wood=0.0, metal=0.0, water=0.0, food=25.0),
    Biome.COLD_DESERT: dict(stone=30.0, wood=0.0, metal=0.0, water=0.0, food=25.0),
    Biome.SAVANNA: dict(stone=10.0, wood=5.0, metal=0.0, water=15.0, food=225.0),
    Biome.TROPICAL_DRY_FOREST: dict(stone=10.0, wood=30.0, metal=0.0, water=20.0, food=275.0),
    Biome.TROPICAL_RAINFOREST: dict(stone=10.0, wood=80.0, metal=0.0, water=30.0, food=500.0),
}


# ---------------------------------------------------------------------------
# Earth loader
# ---------------------------------------------------------------------------

@dataclass
class EarthLoaderConfig:
    dem_template: str = "/vsis3/copernicus-dem-30m/Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif"
    worldcover_template: str = "/vsis3/esa-worldcover/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
    chelsa_bio1_path: Optional[str] = None   # local mean annual temperature (deg C * 10)
    chelsa_bio12_path: Optional[str] = None  # local mean annual precipitation (mm)
    hydrosheds_rivers_path: Optional[str] = None
    hydrosheds_lakes_path: Optional[str] = None


class EarthLoader:
    """Stream real Earth data into Chunk-shaped numpy arrays.

    Parameters
    ----------
    origin_lat, origin_lon : float
        Geographic centre of the simulation (degrees).
    bounds_km : float
        Approximate half-extent (km) the loader is allowed to serve. Chunks
        whose centre falls outside this radius will still load, but the
        bound informs sanity checks and caching.
    cache_dir : str
        Directory for cached COG sidecars / vector reads. Created if missing.
    config : EarthLoaderConfig, optional
        Override default data-source URIs (useful for tests).
    """

    def __init__(
        self,
        origin_lat: float,
        origin_lon: float,
        bounds_km: float = 50.0,
        cache_dir: Optional[str] = None,
        config: Optional[EarthLoaderConfig] = None,
    ) -> None:
        self.origin_lat = float(origin_lat)
        self.origin_lon = float(origin_lon)
        self.bounds_km = float(bounds_km)
        self.cache_dir = cache_dir or os.path.join(
            os.path.expanduser("~"), ".cache", "genesis-engine", "earth"
        )
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except OSError:  # pragma: no cover - read-only fs
            log.warning("EarthLoader: cache_dir %s not writable", self.cache_dir)
        self.cfg = config or EarthLoaderConfig()
        self.seed = _stable_seed("earth", self.origin_lat, self.origin_lon)

        # Build a local azimuthal-equidistant projection so chunk-metres map
        # cleanly to lat/lon around the origin. Fall back to a flat-earth
        # approximation if pyproj is missing.
        self._transformer_xy_to_ll = None
        self._transformer_ll_to_xy = None
        if _HAS_PYPROJ:
            try:
                proj4 = (
                    f"+proj=aeqd +lat_0={self.origin_lat} +lon_0={self.origin_lon} "
                    f"+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
                )
                self._crs_local = CRS.from_proj4(proj4)
                self._crs_wgs84 = CRS.from_epsg(4326)
                self._transformer_xy_to_ll = Transformer.from_crs(
                    self._crs_local, self._crs_wgs84, always_xy=True
                )
                self._transformer_ll_to_xy = Transformer.from_crs(
                    self._crs_wgs84, self._crs_local, always_xy=True
                )
            except Exception as exc:  # pragma: no cover
                log.warning("EarthLoader: pyproj unavailable (%s); using flat-earth", exc)

        # Probe optional CHELSA rasters once
        self._has_chelsa = bool(
            self.cfg.chelsa_bio1_path and os.path.exists(self.cfg.chelsa_bio1_path)
            and self.cfg.chelsa_bio12_path and os.path.exists(self.cfg.chelsa_bio12_path)
        )
        # Probe optional HydroSHEDS layers
        self._has_hydrosheds = _HAS_FIONA and bool(
            (self.cfg.hydrosheds_rivers_path and os.path.exists(self.cfg.hydrosheds_rivers_path))
            or (self.cfg.hydrosheds_lakes_path and os.path.exists(self.cfg.hydrosheds_lakes_path))
        )

    # -- projection helpers --------------------------------------------------

    def _xy_to_lonlat(self, x_m: np.ndarray, y_m: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Convert local metric coords (around origin) -> (lon, lat) degrees."""
        if self._transformer_xy_to_ll is not None:
            lon, lat = self._transformer_xy_to_ll.transform(x_m, y_m)
            return np.asarray(lon, dtype=np.float64), np.asarray(lat, dtype=np.float64)
        # Flat-earth fallback (good enough for ~50km extents)
        lat = self.origin_lat + (y_m / 111_320.0)
        lon = self.origin_lon + (x_m / (111_320.0 * max(math.cos(math.radians(self.origin_lat)), 1e-6)))
        return np.asarray(lon, dtype=np.float64), np.asarray(lat, dtype=np.float64)

    def _chunk_lonlat_bounds(self, coord: Tuple[int, int, int]) -> Tuple[float, float, float, float]:
        """(min_lon, min_lat, max_lon, max_lat) for one chunk."""
        cx, cy, _cz = coord
        x0 = cx * CHUNK_SIDE_M
        y0 = cy * CHUNK_SIDE_M
        x1 = x0 + CHUNK_SIDE_M
        y1 = y0 + CHUNK_SIDE_M
        # Sample corners + midpoints to be robust to the projection's distortion
        xs = np.array([x0, x1, x0, x1, (x0 + x1) * 0.5], dtype=np.float64)
        ys = np.array([y0, y0, y1, y1, (y0 + y1) * 0.5], dtype=np.float64)
        lon, lat = self._xy_to_lonlat(xs, ys)
        return float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max())

    def _chunk_xy_grid(self, coord: Tuple[int, int, int]) -> Tuple[np.ndarray, np.ndarray]:
        """Per-cell centre (x_m, y_m) arrays for one chunk, shape (CHUNK_SIZE, CHUNK_SIZE)."""
        cx, cy, _cz = coord
        ox = cx * CHUNK_SIDE_M
        oy = cy * CHUNK_SIDE_M
        xs = ox + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M
        ys = oy + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M
        XX, YY = np.meshgrid(xs, ys, indexing="xy")
        return XX.astype(np.float64), YY.astype(np.float64)

    # -- raster sampling -----------------------------------------------------

    def _sample_raster(
        self,
        path: str,
        lon_min: float,
        lat_min: float,
        lon_max: float,
        lat_max: float,
        out_shape: Tuple[int, int],
        resampling: Any = None,
    ) -> Optional[np.ndarray]:
        """Read a windowed sample of a raster reprojected to (lon, lat) bbox.

        Returns the array on success, ``None`` on any error so the caller can
        fall back to synthetic data.
        """
        if not _HAS_RASTERIO:
            return None
        try:
            from rasterio.enums import Resampling
            from rasterio.vrt import WarpedVRT
        except Exception:
            return None
        try:
            with rasterio.open(path) as src:
                # Transform our lon/lat bbox into the source CRS
                src_bounds = _rio_transform_bounds(
                    "EPSG:4326", src.crs, lon_min, lat_min, lon_max, lat_max, densify_pts=21
                )
                window = _rio_from_bounds(*src_bounds, transform=src.transform)
                window = window.round_offsets().round_lengths()
                if window.width <= 0 or window.height <= 0:
                    return None
                data = src.read(
                    1,
                    window=window,
                    out_shape=out_shape,
                    resampling=resampling or Resampling.nearest,
                    boundless=True,
                    fill_value=src.nodata if src.nodata is not None else 0,
                )
                return np.asarray(data)
        except Exception as exc:
            log.debug("EarthLoader: raster read failed for %s: %s", path, exc)
            return None

    # -- DEM (Copernicus GLO-30) --------------------------------------------

    def _dem_tile_uri(self, lat: float, lon: float) -> str:
        ns = "N" if lat >= 0 else "S"
        ew = "E" if lon >= 0 else "W"
        lat_i = int(math.floor(abs(lat)))
        lon_i = int(math.floor(abs(lon)))
        return self.cfg.dem_template.format(ns=ns, lat=lat_i, ew=ew, lon=lon_i)

    def _sample_dem(self, bounds: Tuple[float, float, float, float]) -> Optional[np.ndarray]:
        lon_min, lat_min, lon_max, lat_max = bounds
        centre_lat = 0.5 * (lat_min + lat_max)
        centre_lon = 0.5 * (lon_min + lon_max)
        uri = self._dem_tile_uri(centre_lat, centre_lon)
        return self._sample_raster(
            uri, lon_min, lat_min, lon_max, lat_max,
            out_shape=(CHUNK_SIZE, CHUNK_SIZE),
        )

    # -- ESA WorldCover ------------------------------------------------------

    def _worldcover_tile_id(self, lat: float, lon: float) -> str:
        # WorldCover tiles span 3 degrees on each side, named by SW corner.
        tile_lat = int(math.floor(lat / 3.0) * 3)
        tile_lon = int(math.floor(lon / 3.0) * 3)
        ns = "N" if tile_lat >= 0 else "S"
        ew = "E" if tile_lon >= 0 else "W"
        return f"{ns}{abs(tile_lat):02d}{ew}{abs(tile_lon):03d}"

    def _sample_worldcover(
        self, bounds: Tuple[float, float, float, float]
    ) -> Optional[np.ndarray]:
        lon_min, lat_min, lon_max, lat_max = bounds
        centre_lat = 0.5 * (lat_min + lat_max)
        centre_lon = 0.5 * (lon_min + lon_max)
        tile = self._worldcover_tile_id(centre_lat, centre_lon)
        uri = self.cfg.worldcover_template.format(tile=tile)
        return self._sample_raster(
            uri, lon_min, lat_min, lon_max, lat_max,
            out_shape=(CHUNK_SIZE, CHUNK_SIZE),
        )

    # -- Climate -------------------------------------------------------------

    def _sample_climate(
        self, bounds: Tuple[float, float, float, float], centre_lat: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return (mean_annual_temp_c, mean_annual_precip_mm), shape (CHUNK_SIZE, CHUNK_SIZE)."""
        if self._has_chelsa:
            t = self._sample_raster(
                self.cfg.chelsa_bio1_path or "", *bounds,
                out_shape=(CHUNK_SIZE, CHUNK_SIZE),
            )
            p = self._sample_raster(
                self.cfg.chelsa_bio12_path or "", *bounds,
                out_shape=(CHUNK_SIZE, CHUNK_SIZE),
            )
            if t is not None and p is not None:
                # CHELSA bio1 is in degC * 10; bio12 is mm/yr
                return (t.astype(np.float32) / 10.0,
                        p.astype(np.float32))
        # Latitude-only synthetic fallback
        base_temp = 30.0 * (1.0 - abs(centre_lat) / 90.0) - 5.0
        base_precip = max(0.0, 1500.0 * math.cos(math.radians(centre_lat)) ** 2)
        temp = np.full((CHUNK_SIZE, CHUNK_SIZE), base_temp, dtype=np.float32)
        precip = np.full((CHUNK_SIZE, CHUNK_SIZE), base_precip, dtype=np.float32)
        return temp, precip

    # -- Public API ----------------------------------------------------------

    def chunk_data(self, chunk_coord: Tuple[int, int, int]) -> Optional[Dict[str, np.ndarray]]:
        """Return a dict of Chunk-shaped numpy arrays, or ``None`` on failure.

        Keys: height, biome, water, food_capacity, stone, wood, metal.
        On any data-source failure we return ``None`` so the caller can fall
        back to the procedural generator in ``engine.world.generate_chunk``.
        """
        try:
            bounds = self._chunk_lonlat_bounds(chunk_coord)
        except Exception as exc:
            log.warning("EarthLoader: failed to compute bounds: %s", exc)
            return None

        # 1. DEM
        dem = self._sample_dem(bounds)
        if dem is None:
            return None
        height = np.asarray(dem, dtype=np.float32)
        # Replace fill / nodata sentinels (Copernicus uses -32767 / 0 over sea)
        height = np.where(np.isfinite(height), height, 0.0).astype(np.float32)
        height = np.where(height < -1000.0, 0.0, height)

        # 2. WorldCover
        cover = self._sample_worldcover(bounds)
        if cover is None:
            # We can still synthesize biome from elevation + climate, but the
            # spec says return None for graceful fallback when data missing.
            return None
        cover = np.asarray(cover, dtype=np.uint8)

        # 3. Climate
        centre_lat = 0.5 * (bounds[1] + bounds[3])
        temp_c, precip_mm = self._sample_climate(bounds, centre_lat)

        # 4. Biome refinement
        biome = np.empty_like(cover, dtype=np.uint8)
        unique_classes = np.unique(cover)
        for cls in unique_classes:
            mask = cover == cls
            if not mask.any():
                continue
            # Use mean climate inside this class for the refinement decision.
            t_mean = float(temp_c[mask].mean()) if temp_c.size else 15.0
            p_mean = float(precip_mm[mask].mean()) if precip_mm.size else 800.0
            biome[mask] = _refine_biome(int(cls), t_mean, p_mean)

        # Force oceans on water-class or where DEM <= 0 over ESA water
        water_class = (cover == 80)
        biome[water_class] = int(Biome.OCEAN)

        # 5. Resources (deterministic noise keyed by seed + chunk coord)
        rng = np.random.default_rng(_stable_seed(self.seed, "resources", *chunk_coord))
        noise = rng.random((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)

        stone = np.zeros_like(height, dtype=np.float32)
        wood = np.zeros_like(height, dtype=np.float32)
        metal = np.zeros_like(height, dtype=np.float32)
        water = np.zeros_like(height, dtype=np.float32)
        food_capacity = np.zeros_like(height, dtype=np.float32)

        for b_id, props in _BIOME_RESOURCE.items():
            mask = biome == int(b_id)
            if not mask.any():
                continue
            stone[mask] = props["stone"] + noise[mask] * 5.0
            wood[mask] = props["wood"] * (0.5 + noise[mask])
            water[mask] = props["water"]
            food_capacity[mask] = props["food"] * (0.75 + 0.5 * noise[mask])

        # Boost stone with elevation (mountains expose rock)
        stone += np.maximum(height, 0.0) * 0.02

        # Metal deposits: sparse, biased to higher elevation, deterministic
        metal_prob = 0.01 + np.clip(np.maximum(height, 0.0), 0.0, 3000.0) / 60_000.0
        metal_mask = noise < metal_prob
        metal_vals = rng.random((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32) * 50.0
        metal[metal_mask] = metal_vals[metal_mask]

        # 6. Hydrography: ESA water class is the baseline; optional rivers/lakes
        water[biome == int(Biome.OCEAN)] = 1000.0
        # Stamp lakes / rivers if HydroSHEDS is locally cached
        if self._has_hydrosheds:
            try:
                hydro_mask = self._rasterize_hydrosheds(bounds, chunk_coord)
                if hydro_mask is not None:
                    water = np.maximum(water, hydro_mask.astype(np.float32) * 800.0)
                    biome[hydro_mask & (biome != int(Biome.OCEAN))] = int(Biome.OCEAN)
            except Exception as exc:  # pragma: no cover - shapefile rare path
                log.debug("EarthLoader: hydrosheds rasterize failed: %s", exc)

        # Wood is zero in water/ice/desert -- already handled by biome priors.
        # Final dtype guarantees.
        return {
            "height": height.astype(np.float32),
            "biome": biome.astype(np.uint8),
            "water": water.astype(np.float32),
            "food_capacity": food_capacity.astype(np.float32),
            "stone": stone.astype(np.float32),
            "wood": wood.astype(np.float32),
            "metal": metal.astype(np.float32),
        }

    # -- HydroSHEDS (optional) ----------------------------------------------

    def _rasterize_hydrosheds(
        self, bounds: Tuple[float, float, float, float], coord: Tuple[int, int, int]
    ) -> Optional[np.ndarray]:
        """Rasterise HydroLAKES / HydroRIVERS shapefiles to a chunk-sized mask.

        Returns a boolean array or None if anything is missing.
        """
        if not (_HAS_FIONA and _HAS_RASTERIO):
            return None
        try:
            from rasterio import features
            from rasterio.transform import from_bounds as _tx_from_bounds
            import fiona as _fiona
        except Exception:
            return None
        lon_min, lat_min, lon_max, lat_max = bounds
        transform = _tx_from_bounds(lon_min, lat_min, lon_max, lat_max,
                                    CHUNK_SIZE, CHUNK_SIZE)
        shapes = []
        for path in (self.cfg.hydrosheds_lakes_path, self.cfg.hydrosheds_rivers_path):
            if not path or not os.path.exists(path):
                continue
            try:
                with _fiona.open(path) as src:
                    for feat in src.filter(bbox=(lon_min, lat_min, lon_max, lat_max)):
                        shapes.append((feat["geometry"], 1))
            except Exception:
                continue
        if not shapes:
            return None
        mask = features.rasterize(
            shapes,
            out_shape=(CHUNK_SIZE, CHUNK_SIZE),
            transform=transform,
            fill=0,
            dtype="uint8",
        )
        return mask.astype(bool)


__all__ = ["EarthLoader", "EarthLoaderConfig"]
