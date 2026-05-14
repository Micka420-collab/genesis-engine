"""High-level Genesis World builder.

Single entry point for creating a full Genesis Engine world: Earth-anchored
or procedural, with all 5cd subsystems and L2 sim_lift wired in. Replaces
the boilerplate that previously lived in every ``p*_leman*.py`` script.

Usage::

    from engine.world_builder import WorldBuilder

    world = (WorldBuilder("lausanne")
             .anchor(lat=46.510, lon=6.633)
             .size_km(2.0)
             .founders(20)
             .cultures(2)
             .max_agents(1000)
             .with_l1_earth(True)        # Copernicus DEM + ESA WorldCover
             .with_l2_lift(True)         # vegetation + erosion + slope
             .build())

    # World is a Simulation with everything wired. Use it like one:
    for _ in range(2000):
        world.step()

    # Or get a live dashboard:
    world.start_dashboard(port=8765)

Determinism is preserved end-to-end through ``engine.core.prf_rng`` — same
config in, same world out (modulo network reachability of Earth data).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from engine.sim import Simulation, SimConfig
from engine.sim_5cd_integration import install
from engine.earth_loader import EarthLoader
from engine.earth_streamer import attach_earth_loader, attach_land_filter
from engine.sim_lift import install_lift, lift_state
from engine.realism import install_realism, realism_state


@dataclass
class _BuilderState:
    name: str = "world"
    lat: Optional[float] = None
    lon: Optional[float] = None
    size_km: float = 2.0
    n_founders: int = 20
    n_cultures: int = 2
    max_agents: int = 1000
    spawn_radius_m: float = 200.0
    drive_accel: float = 1500.0
    seed: int = 0xFADE_C0FFEE_5A & 0xFFFFFFFF_FFFFFFFF
    enable_l1: bool = True
    enable_l2: bool = True
    enable_5cd: bool = True
    enable_realism: bool = False
    realism_cfg: dict = field(default_factory=dict)
    cache_dir: Optional[str] = None
    extra_install: List[callable] = field(default_factory=list)


class WorldBuilder:
    """Fluent builder for a full Genesis Engine world.

    Methods return ``self`` so calls chain. Call :meth:`build` to instantiate.
    """

    def __init__(self, name: str = "world") -> None:
        self._s = _BuilderState(name=name)

    # ---- geography ---------------------------------------------------------

    def anchor(self, lat: float, lon: float) -> "WorldBuilder":
        """Set the geographic origin (decimal degrees). When set, L1 fetches
        real Copernicus DEM + ESA WorldCover tiles for the bounding box."""
        self._s.lat = float(lat)
        self._s.lon = float(lon)
        return self

    def size_km(self, km: float) -> "WorldBuilder":
        """Square-side half-extent in km."""
        self._s.size_km = float(km)
        return self

    def cache_dir(self, path: str) -> "WorldBuilder":
        """Directory for Earth-data and chunk cache. Default:
        ``<project>/cache/earth_<name>``."""
        self._s.cache_dir = os.path.abspath(path)
        return self

    # ---- demographics ------------------------------------------------------

    def founders(self, n: int) -> "WorldBuilder":
        self._s.n_founders = int(n)
        return self

    def cultures(self, n: int) -> "WorldBuilder":
        self._s.n_cultures = int(n)
        return self

    def max_agents(self, n: int) -> "WorldBuilder":
        self._s.max_agents = int(n)
        return self

    def spawn_radius_m(self, m: float) -> "WorldBuilder":
        self._s.spawn_radius_m = float(m)
        return self

    def drive_accel(self, x: float) -> "WorldBuilder":
        self._s.drive_accel = float(x)
        return self

    def seed(self, s: int) -> "WorldBuilder":
        self._s.seed = int(s) & 0xFFFFFFFF_FFFFFFFF
        return self

    # ---- layers ------------------------------------------------------------

    def with_l1_earth(self, enabled: bool = True) -> "WorldBuilder":
        self._s.enable_l1 = bool(enabled)
        return self

    def with_l2_lift(self, enabled: bool = True) -> "WorldBuilder":
        self._s.enable_l2 = bool(enabled)
        return self

    def with_5cd(self, enabled: bool = True) -> "WorldBuilder":
        """Phase 5c+5d sub-systems (construction, atmosphere, invention,
        tech, chronic fatigue, speech, foraging, value override). On by
        default — disabling produces a vanilla Phase-4 sim."""
        self._s.enable_5cd = bool(enabled)
        return self

    def with_realism(self, *,
                     hydrology: bool = True,
                     wildlife: Optional[dict] = None,
                     trails: bool = True,
                     seasons: Optional[dict] = None,
                     disease: bool = True,
                     river_threshold: float = 8.0) -> "WorldBuilder":
        """Enable the Reality Engine on top of L1+L2 (hydrology, wildlife,
        trails, seasons, disease). Defaults to a balanced configuration
        suited for temperate-zone simulations."""
        self._s.enable_realism = True
        if wildlife is None:
            wildlife = {"deer": 60, "fish": 200, "wolf": 4}
        if seasons is None:
            seasons = {"year": 2026, "day_of_year": 120}
        self._s.realism_cfg = {
            "hydrology": hydrology,
            "wildlife": wildlife,
            "trails": trails,
            "seasons": seasons,
            "disease": disease,
            "river_threshold": river_threshold,
        }
        return self

    def extra_install(self, fn) -> "WorldBuilder":
        """Register a custom install hook ``fn(sim)`` to run after the
        standard ones. Useful for third-party extensions / experiments."""
        self._s.extra_install.append(fn)
        return self

    # ---- build -------------------------------------------------------------

    def build(self) -> "World":
        """Materialise the world. Returns a :class:`World` wrapping the sim."""
        s = self._s
        # Cache directory
        if s.cache_dir is None:
            here = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(here, "..", ".."))
            s.cache_dir = os.path.join(project_root, "cache", f"earth_{s.name}")
        os.makedirs(s.cache_dir, exist_ok=True)

        cfg = SimConfig(
            name=s.name,
            seed=s.seed,
            founders=s.n_founders,
            max_agents=s.max_agents,
            bounds_km=(s.size_km, s.size_km),
            spawn_radius_m=s.spawn_radius_m,
            cultures=s.n_cultures,
            drive_accel=s.drive_accel,
        )
        sim = Simulation(cfg)
        # L1: try Earth-anchored if lat/lon given.
        loader = None
        if s.enable_l1 and s.lat is not None and s.lon is not None:
            loader = EarthLoader(origin_lat=s.lat, origin_lon=s.lon,
                                 bounds_km=s.size_km, cache_dir=s.cache_dir)
            sim.earth_loader = loader
            attach_earth_loader(sim.streamer, loader,
                                strict=False, log_first_hit=False)
            attach_land_filter(sim)
        # 5cd subsystems
        if s.enable_5cd:
            install(sim)
        # L2 vegetation + erosion + slope
        if s.enable_l2:
            install_lift(sim)
        # Reality Engine — hydrology, wildlife, trails, seasons, disease
        if s.enable_realism:
            install_realism(sim, **s.realism_cfg)
        # Extras
        for fn in s.extra_install:
            try:
                fn(sim)
            except Exception:
                pass

        return World(name=s.name, sim=sim, loader=loader, builder_state=s)


@dataclass
class World:
    """Wrapper bundling a simulation, optional Earth loader, and helpers."""
    name: str
    sim: Simulation
    loader: Optional[EarthLoader]
    builder_state: _BuilderState

    # ---- delegated sim API -------------------------------------------------

    def step(self):
        return self.sim.step()

    def run(self, ticks: int) -> "World":
        for _ in range(int(ticks)):
            self.sim.step()
        return self

    @property
    def tick(self) -> int:
        return int(self.sim.tick)

    @property
    def n_alive(self) -> int:
        n = self.sim.agents.n_active
        if n == 0:
            return 0
        return int(self.sim.agents.alive[:n].sum())

    @property
    def n_spawned(self) -> int:
        return int(self.sim.agents.n_active)

    # ---- diagnostics -------------------------------------------------------

    def summary(self) -> dict:
        """Compact, JSON-serialisable snapshot for logging / dashboards."""
        s = self.builder_state
        sim = self.sim
        out = {
            "name": s.name,
            "anchor": ({"lat": s.lat, "lon": s.lon}
                       if s.lat is not None else None),
            "size_km": s.size_km,
            "tick": int(sim.tick),
            "n_alive": self.n_alive,
            "n_spawned": self.n_spawned,
            "config": {
                "founders": s.n_founders, "max_agents": s.max_agents,
                "cultures": s.n_cultures, "drive_accel": s.drive_accel,
                "seed": s.seed,
            },
        }
        if s.enable_l1 and hasattr(sim.streamer, "_earth_hits"):
            out["l1"] = {
                "hits": int(sim.streamer._earth_hits),
                "misses": int(sim.streamer._earth_misses),
            }
        if s.enable_l2:
            out["l2"] = lift_state(sim)
        if s.enable_realism:
            out["realism"] = realism_state(sim)
        if hasattr(sim, "atmosphere"):
            out["atmosphere"] = {
                "co2_ppm": round(float(sim.atmosphere.co2_ppm), 3),
                "temp_anomaly_k": round(float(sim.atmosphere.temp_anomaly_k), 4),
            }
        if hasattr(sim, "construction_registry"):
            out["construction"] = {
                "active_projects": len(sim.construction_registry.projects),
                "completed_structures": len(sim.construction_registry.structures),
            }
        if hasattr(sim, "invention_registry"):
            out["invention"] = {
                "artifacts": len(sim.invention_registry.artifacts),
                "names": [a.name for a in
                          list(sim.invention_registry.artifacts.values())[:10]],
            }
        return out

    # ---- time-warp ---------------------------------------------------------

    def set_time_warp(self, mode: str) -> dict:
        """Set the simulation time-warp mode.

        Modes: ``"realtime"``, ``"x10"``, ``"x100"``, ``"x1000"``,
        ``"milestone"``. Idempotent — installs the controller on first call.
        Returns the new status dict from :class:`engine.timewarp.TimeWarp`.
        """
        from engine.timewarp import install_timewarp
        tw = install_timewarp(self.sim)
        return tw.set_mode(mode)

    # ---- live dashboard ----------------------------------------------------

    def start_dashboard(self, host: str = "127.0.0.1", port: int = 8765):
        """Launch the HTTP god-view server on ``host:port``. Returns
        ``(srv, god, log)`` from :func:`engine.dashboard.start_god_server`."""
        from engine.dashboard import SimController, start_god_server
        ctl = SimController()
        return start_god_server(self.sim, ctl, host=host, port=port)


__all__ = ["WorldBuilder", "World"]
