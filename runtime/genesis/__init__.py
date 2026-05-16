"""DEPRECATED — see ../engine/ for the real runtime.

This directory was an exploratory parallel implementation built before the
real `engine/` package was discovered. It is preserved only because the host
filesystem does not currently allow file deletion. Use `engine.sim.Simulation`.
"""
raise ImportError(
    "genesis.* is deprecated — import from engine instead. "
    "See ../README.md for the supported entry points."
)
