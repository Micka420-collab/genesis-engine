"""Python mirror of ``genesis_core::MultiRateCoupler`` for the runtime sim.

Dispatches weather / ecology / tectonics sub-steps when their domain clocks
cross LCM boundaries. Agent cognition stays on the base ``Simulation.step``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Dict, List, Optional, Tuple

from engine.core import TICK_DT_S

PIPELINE_LAYER = "Genesis-L0 Core"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


class TickDomain(IntEnum):
    Agent = 0
    Weather = 1
    Ecology = 2
    Tectonics = 3

    @classmethod
    def default_dt_sim_seconds(cls, domain: "TickDomain") -> int:
        return {
            TickDomain.Agent: 1,
            TickDomain.Weather: 300,
            TickDomain.Ecology: 86_400,
            TickDomain.Tectonics: 31_557_600_000,
        }[domain]

    @classmethod
    def all_domains(cls) -> Tuple["TickDomain", ...]:
        return (TickDomain.Agent, TickDomain.Weather,
                TickDomain.Ecology, TickDomain.Tectonics)


@dataclass
class DomainConfig:
    domain: TickDomain
    dt_sim_seconds: int

    @classmethod
    def with_defaults(cls, domain: TickDomain) -> "DomainConfig":
        return cls(domain=domain,
                   dt_sim_seconds=TickDomain.default_dt_sim_seconds(domain))


@dataclass
class CouplerStep:
    master_tick: int = 0
    fired: List[TickDomain] = field(default_factory=list)


@dataclass
class _DomainState:
    domain: TickDomain
    dt: int
    domain_tick: int = 0
    remainder_s: int = 0


class MultiRateCoupler:
    """Tracks per-domain clocks; ``advance`` returns domains to run."""

    def __init__(self, master_dt: int,
                 configs: Optional[List[DomainConfig]] = None):
        self.master_tick = 0
        self.master_dt = max(1, int(master_dt))
        if configs is None:
            configs = [DomainConfig.with_defaults(d) for d in TickDomain.all_domains()]
        self._domains: List[_DomainState] = [
            _DomainState(domain=c.domain,
                         dt=max(1, int(c.dt_sim_seconds)))
            for c in configs
        ]

    @classmethod
    def new_default(cls, master_dt: Optional[int] = None) -> "MultiRateCoupler":
        dt = master_dt if master_dt is not None else int(TICK_DT_S)
        return cls(dt)

    def domain_tick(self, domain: TickDomain) -> int:
        for st in self._domains:
            if st.domain == domain:
                return st.domain_tick
        return 0

    def advance(self) -> CouplerStep:
        self.master_tick += 1
        fired: List[TickDomain] = []
        for st in self._domains:
            st.remainder_s += self.master_dt
            while st.remainder_s >= st.dt:
                st.remainder_s -= st.dt
                st.domain_tick += 1
                fired.append(st.domain)
        return CouplerStep(master_tick=self.master_tick, fired=fired)


def _tick_weather_domain(sim) -> None:
    """Mesoscale weather nudge on streamed chunks (deterministic)."""
    from engine.world import weather_at
    accel = float(getattr(sim.cfg, "drive_accel", 1500.0))
    st = getattr(sim, "_coupler_weather", None)
    if st is None:
        st = {"n_updates": 0, "last_mean_temp": 15.0}
        sim._coupler_weather = st
    for chunk in sim.streamer.cache.values():
        base_t = float(chunk.height.mean() * -0.0065 + 15.0)
        avg_p = float(chunk.food_capacity.mean() * 3.0)
        w = weather_at(sim.tick * int(accel), base_t, avg_p)
        st["last_mean_temp"] = float(w.temp_c)
        st["n_updates"] = int(st.get("n_updates", 0)) + 1
    st["domain_tick"] = sim._coupler.domain_tick(TickDomain.Weather)


def _tick_ecology_domain(sim) -> None:
    """Daily ecology: light food-pressure scaling from weather mean."""
    st = getattr(sim, "_coupler_ecology", None)
    if st is None:
        st = {"pressure_scale": 1.0}
        sim._coupler_ecology = st
    wst = getattr(sim, "_coupler_weather", {})
    t = float(wst.get("last_mean_temp", 15.0))
    # Cold → slightly higher effective hunger pressure (stored for observers).
    st["pressure_scale"] = float(1.0 + max(0.0, (10.0 - t) * 0.02))
    st["domain_tick"] = sim._coupler.domain_tick(TickDomain.Ecology)


def _tick_tectonics_domain(sim) -> None:
    st = getattr(sim, "_coupler_tectonics", None)
    if st is None:
        st = {"epochs": 0}
        sim._coupler_tectonics = st
    st["epochs"] = int(st.get("epochs", 0)) + 1
    st["domain_tick"] = sim._coupler.domain_tick(TickDomain.Tectonics)


_DOMAIN_HANDLERS: Dict[TickDomain, Callable] = {
    TickDomain.Weather: _tick_weather_domain,
    TickDomain.Ecology: _tick_ecology_domain,
    TickDomain.Tectonics: _tick_tectonics_domain,
}


def install_multi_rate_coupler(sim, *,
                                master_dt: Optional[int] = None,
                                configs: Optional[List[DomainConfig]] = None
                                ) -> MultiRateCoupler:
    """Wrap ``sim.step`` with coupled domain dispatch (idempotent)."""
    if getattr(sim, "_coupler_wrapped", False):
        coupler = sim._coupler
        if master_dt is not None:
            coupler.master_dt = max(1, int(master_dt))
        return coupler

    dt = master_dt if master_dt is not None else int(sim.cfg.drive_accel)
    coupler = MultiRateCoupler(dt, configs)
    sim._coupler = coupler
    sim._coupler_wrapped = True
    sim._last_coupler_step: Optional[CouplerStep] = None
    original = sim.step

    def coupled_step():
        stats = original()
        step = coupler.advance()
        sim._last_coupler_step = step
        for domain in step.fired:
            if domain == TickDomain.Agent:
                continue
            handler = _DOMAIN_HANDLERS.get(domain)
            if handler is not None:
                handler(sim)
        return stats

    sim.step = coupled_step
    return coupler


def coupler_summary(sim) -> Dict[str, object]:
    """Diagnostics for smokes / manifest."""
    c: Optional[MultiRateCoupler] = getattr(sim, "_coupler", None)
    if c is None:
        return {"installed": False}
    last = getattr(sim, "_last_coupler_step", None)
    return {
        "installed": True,
        "master_tick": c.master_tick,
        "master_dt": c.master_dt,
        "domain_ticks": {d.name: c.domain_tick(d) for d in TickDomain.all_domains()},
        "last_fired": [d.name for d in (last.fired if last else [])],
        "weather": getattr(sim, "_coupler_weather", {}),
        "ecology": getattr(sim, "_coupler_ecology", {}),
    }


__all__ = [
    "TickDomain", "DomainConfig", "CouplerStep", "MultiRateCoupler",
    "install_multi_rate_coupler", "coupler_summary",
]
