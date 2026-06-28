"""Backend worldgen « vrai Genesis » — branche le moteur réel derrière le seam.

Au lieu du worldgen simplifié de ``worldgen.py``, ce backend produit la VRAIE
géographie Genesis : relief issu des plaques tectoniques + érosion, climat
(température/précipitation), biomes de Whittaker, et ressources réelles
(``engine.world._compute_resources_py``).

Contrat identique à ``worldgen.generate_chunk`` (même ``ChunkData``, même
fonction de hash) → le coordinateur, la vérification et le quorum fonctionnent
sans changement. SEULE différence : les valeurs sont celles du vrai moteur.

⚠️ Ce backend nécessite ``numpy`` + le paquet ``engine`` (le dépôt). Il n'est
donc PAS compatible avec le client autonome « zéro dépendance » (`/client`) :
les workers du backend ``engine`` doivent utiliser ``python -m network donate``
depuis le dépôt. Le macro mondial (global, déterministe) est calculé UNE fois
par seed puis mis en cache.
"""
from __future__ import annotations

import os
import sys
import threading
from typing import Dict, Optional

from .worldgen import ChunkData, chunk_digest

# Résolution du macro continental : petit = rapide, déterministe, suffisant pour
# une carte observable. (cell ≈ map_size_km / resolution.)
MACRO_RESOLUTION = 64

# Palette des 12 biomes du moteur (engine.world.Biome) pour la carte web.
_BIOME_COLORS = {
    "OCEAN": "#1c3d5a", "ICE": "#e8f0f5", "TUNDRA": "#9fb3b8",
    "BOREAL_FOREST": "#2e4d3a", "TEMPERATE_FOREST": "#3f7a43",
    "TEMPERATE_RAINFOREST": "#2f6b50", "GRASSLAND": "#7fa24a",
    "HOT_DESERT": "#d9b061", "COLD_DESERT": "#b9a98a", "SAVANNA": "#b7972f",
    "TROPICAL_DRY_FOREST": "#5c8a2f", "TROPICAL_RAINFOREST": "#1f5e2a",
}

_lock = threading.Lock()
_macro_cache: Dict[int, object] = {}
_engine: Optional[dict] = None


def _load_engine() -> Optional[dict]:
    """Importe paresseusement le moteur réel. None si indisponible."""
    global _engine
    if _engine is not None:
        return _engine or None
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = os.path.join(here, "runtime")
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    try:
        import numpy as np
        from engine.world_genesis import generate_world, GenesisParams, sample_macro
        from engine.world import classify_biome, _compute_resources_py
        _engine = {
            "np": np, "generate_world": generate_world,
            "GenesisParams": GenesisParams, "sample_macro": sample_macro,
            "classify_biome": classify_biome,
            "_compute_resources_py": _compute_resources_py,
        }
    except Exception:
        _engine = {}
    return _engine or None


def available() -> bool:
    """True si le backend moteur peut tourner dans cet environnement."""
    return _load_engine() is not None


def _macro(world_seed: int):
    """Génère (ou récupère du cache) le macro continental déterministe du seed."""
    eng = _load_engine()
    if eng is None:
        raise RuntimeError("backend engine indisponible (numpy/engine manquant)")
    with _lock:
        w = _macro_cache.get(world_seed)
        if w is None:
            params = eng["GenesisParams"](seed=int(world_seed),
                                          resolution=MACRO_RESOLUTION)
            w = eng["generate_world"](params)
            _macro_cache[world_seed] = w
        return w, eng


def _chunk_km(world, cx: int, cy: int) -> tuple:
    """Mappe un chunk réseau (cx,cy) vers une position km du macro (centré)."""
    size_km = float(getattr(world.params, "map_size_km", 4000.0))
    cell_km = size_km / MACRO_RESOLUTION
    return (size_km / 2.0 + cx * cell_km, size_km / 2.0 + cy * cell_km)


def generate_chunk(world_seed: int, cx: int, cy: int, ticks: int = 64) -> ChunkData:
    """Vrai chunk Genesis — même contrat que ``worldgen.generate_chunk``."""
    world, eng = _macro(world_seed)
    np = eng["np"]
    x_km, y_km = _chunk_km(world, cx, cy)
    sp = eng["sample_macro"](world, x_km, y_km)
    elev_m = float(sp["elevation_m"])
    temp_c = float(sp["temp_c"])
    precip = float(sp["precip_mm"])
    biome_enum = eng["classify_biome"](temp_c, precip, elev_m)
    biome = biome_enum.name
    color = _BIOME_COLORS.get(biome, "#777777")

    # Ressources réelles (moyennes sur le chunk 64×64).
    elev_arr = np.full((64, 64), elev_m, np.float32)
    biome_arr = np.full((64, 64), int(biome_enum), np.uint8)
    r = eng["_compute_resources_py"](int(world_seed), cx, cy, 0, elev_arr, biome_arr)
    stone = float(r[0].mean())
    wood = float(r[1].mean())
    water = float(r[3].mean())
    food = float(r[4].mean())

    # Population émergente : portance ∝ nourriture, évoluée sur `ticks`
    # (déterministe, sans RNG dans la boucle).
    food_cap = food
    pop = int(food * 0.02)
    f = food
    for t in range(max(1, ticks)):
        if f < food_cap:
            f = min(food_cap, f + food_cap / 7200.0)
        demand = pop * 0.01
        f = max(0.0, f - demand)
        if t % 16 == 0:
            if f > demand * 4:
                pop += 1 + (pop // 50)
            elif f < demand:
                pop = max(0, pop - 1)

    # Arrondi AVANT le digest (lien résumé↔hash, cf. worldgen).
    food = round(food, 3)
    wood = round(wood, 3)
    stone = round(stone, 3)
    water = round(water, 3)
    digest = chunk_digest(world_seed, cx, cy, ticks, biome, food, wood, stone,
                          water, pop)
    return ChunkData(cx=cx, cy=cy, ticks=ticks, biome=biome, color=color,
                     height_m=round(elev_m, 3), food=food, wood=wood,
                     stone=stone, water=water, population=pop, digest=digest)
