"""Genesis Engine — operational multi-agent simulation runtime."""
__version__ = "0.1.0"

# FUTURE-VISION Wave 1 (Pillar 1 — Knowledge base ingestion) modules.
# Listed here for discoverability via `dir(engine)` / static tooling.
# These modules are pure-data / pure-function (no I/O, no RNG) and may be
# imported lazily; the names below are only the public Wave 1 surface.
__all__ = [
    "physics",            # B1 — constants, mechanics, thermodynamics
    "chemistry",          # B2 — periodic table, bond energies, alloy helpers
    "material_synthesis", # B3 — combine(composition, conditions) -> material
    "statics",            # B4 — structural stability (Structure, blocks)
]
