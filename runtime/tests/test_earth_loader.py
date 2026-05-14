"""Smoke test for engine.earth_loader.

Designed to pass in offline / no-internet environments: when rasterio or the
remote AWS Open Data buckets are unreachable, ``chunk_data`` returns ``None``
and we simply assert that behaviour. When data IS reachable, we assert the
shape and dtype contract.
"""
from __future__ import annotations

import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from engine.earth_loader import EarthLoader, EarthLoaderConfig, _stable_seed
from engine.world import CHUNK_SIZE


EXPECTED_KEYS = {"height", "biome", "water", "food_capacity", "stone", "wood", "metal"}


class EarthLoaderSmokeTests(unittest.TestCase):
    """Lake Geneva smoke test: lat=46.40, lon=6.45, bounds_km=2.0."""

    def setUp(self) -> None:
        self.loader = EarthLoader(
            origin_lat=46.40,
            origin_lon=6.45,
            bounds_km=2.0,
        )

    def test_loader_constructs(self) -> None:
        self.assertEqual(self.loader.origin_lat, 46.40)
        self.assertEqual(self.loader.origin_lon, 6.45)
        self.assertEqual(self.loader.bounds_km, 2.0)
        # Cache dir should be a real path string (creation may have failed silently)
        self.assertIsInstance(self.loader.cache_dir, str)

    def test_seed_is_deterministic(self) -> None:
        s1 = _stable_seed("earth", 46.40, 6.45)
        s2 = _stable_seed("earth", 46.40, 6.45)
        self.assertEqual(s1, s2)
        s3 = _stable_seed("earth", 46.40, 6.46)
        self.assertNotEqual(s1, s3)

    def test_chunk_lonlat_bounds_near_origin(self) -> None:
        """Chunk (0,0,0) should sit very near the origin lat/lon."""
        lon_min, lat_min, lon_max, lat_max = self.loader._chunk_lonlat_bounds((0, 0, 0))
        # Chunk is 32m wide, so bounds in degrees should be tiny.
        self.assertLess(abs(lat_min - self.loader.origin_lat), 0.01)
        self.assertLess(abs(lat_max - self.loader.origin_lat), 0.01)
        self.assertLess(abs(lon_min - self.loader.origin_lon), 0.01)
        self.assertLess(abs(lon_max - self.loader.origin_lon), 0.01)
        self.assertGreater(lat_max, lat_min)
        self.assertGreater(lon_max, lon_min)

    def test_chunk_data_graceful_offline(self) -> None:
        """Either we got valid arrays (online) or we got None (offline). Both OK."""
        result = self.loader.chunk_data((0, 0, 0))
        if result is None:
            # Offline / data unavailable: this is the documented fallback.
            return
        # Online path: full contract check
        self.assertIsInstance(result, dict)
        self.assertEqual(set(result.keys()), EXPECTED_KEYS)
        for key in EXPECTED_KEYS:
            arr = result[key]
            self.assertIsInstance(arr, np.ndarray, f"{key} must be ndarray")
            self.assertEqual(arr.shape, (CHUNK_SIZE, CHUNK_SIZE),
                             f"{key} shape mismatch")
        self.assertEqual(result["height"].dtype, np.float32)
        self.assertEqual(result["biome"].dtype, np.uint8)
        self.assertEqual(result["water"].dtype, np.float32)
        self.assertEqual(result["food_capacity"].dtype, np.float32)
        self.assertEqual(result["stone"].dtype, np.float32)
        self.assertEqual(result["wood"].dtype, np.float32)
        self.assertEqual(result["metal"].dtype, np.float32)
        # Sanity bounds
        self.assertTrue(np.all(result["biome"] < 12))
        self.assertTrue(np.all(result["stone"] >= 0))
        self.assertTrue(np.all(result["wood"] >= 0))
        self.assertTrue(np.all(result["metal"] >= 0))
        self.assertTrue(np.all(result["water"] >= 0))
        self.assertTrue(np.all(result["food_capacity"] >= 0))

    def test_chunk_data_unreachable_paths_returns_none(self) -> None:
        """Forcing bogus data sources must yield None, never crash."""
        cfg = EarthLoaderConfig(
            dem_template="/vsis3/__nonexistent_bucket__/{ns}{lat:02d}{ew}{lon:03d}.tif",
            worldcover_template="/vsis3/__nonexistent_bucket__/{tile}.tif",
        )
        loader = EarthLoader(46.40, 6.45, bounds_km=2.0, config=cfg)
        result = loader.chunk_data((0, 0, 0))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
