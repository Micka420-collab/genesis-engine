"""Génération déterministe d'un chunk — l'unité de travail du réseau.

Un chunk est une **fonction pure** de ``(world_seed, cx, cy, ticks)``. Deux
machines quelconques produisent le même ``digest`` → le coordinateur vérifie un
échantillon par recalcul (anti-triche), et « le monde ne ment jamais » s'étend
au réseau.

Déterminisme : on réutilise *à l'identique* la primitive PRF canonique du
moteur (``engine.core.prf_bytes``, BLAKE2b-keyed). Si le moteur n'est pas
importable (volontaire externe sans le dépôt complet), une réimplémentation
byte-identique prend le relais — le test ``test_prf_matches_engine`` garantit
qu'elles ne divergent jamais.
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys
from dataclasses import asdict, dataclass
from typing import Iterable, List

# --------------------------------------------------------------------------- #
# PRF — réimplémentation byte-identique de engine.core.prf_bytes (BLAKE2b)     #
# --------------------------------------------------------------------------- #


def _seed_key(world_seed: int) -> bytes:
    ws = world_seed & ((1 << 128) - 1)
    lo = ws & ((1 << 64) - 1)
    hi = ws >> 64
    return struct.pack("<QQ", lo, hi) + struct.pack(">QQ", hi, lo)


def prf_bytes(world_seed: int, ctx: Iterable[str], indices: Iterable[int],
              n_bytes: int = 32) -> bytes:
    """BLAKE2b-keyed PRF → ``n_bytes`` octets déterministes."""
    key = _seed_key(world_seed)
    h = hashlib.blake2b(key=key[:64], digest_size=min(64, max(1, n_bytes)))
    for c in ctx:
        h.update(b"|")
        h.update(c.encode("utf-8"))
    for i in indices:
        h.update(b"|")
        h.update(struct.pack("<Q", int(i) & 0xFFFFFFFFFFFFFFFF))
    out = h.digest()
    while len(out) < n_bytes:
        out += hashlib.blake2b(out, key=key[:64], digest_size=64).digest()
    return out[:n_bytes]


def _prf_float(world_seed: int, ctx: List[str], indices: List[int]) -> float:
    """Float déterministe dans [0, 1)."""
    b = prf_bytes(world_seed, ctx, indices, 8)
    return (struct.unpack("<Q", b)[0] >> 11) / float(1 << 53)


# --------------------------------------------------------------------------- #
# Biomes — table alignée sur engine (terrain.BiomeKind)                        #
# --------------------------------------------------------------------------- #

# (nom, couleur hex pour la carte web, (food, wood, stone, water))
BIOMES = {
    "OCEAN":     ("#1c3d5a", (0, 0, 0, 6)),
    "BEACH":     ("#d8c89a", (1, 0, 1, 1)),
    "GRASSLAND": ("#6f9c4a", (6, 2, 1, 1)),
    "FOREST":    ("#2f6b35", (10, 12, 1, 2)),
    "DESERT":    ("#cBA868", (1, 0, 3, 0)),
    "TUNDRA":    ("#9fb3b8", (2, 1, 2, 1)),
    "MOUNTAIN":  ("#7d7d85", (1, 1, 8, 1)),
}
BIOME_NAMES = list(BIOMES.keys())


def _classify(elevation: float, moisture: float, temperature: float) -> str:
    """Classe un biome depuis 3 champs PRF — émergent, jamais scripté par case."""
    if elevation < 0.32:
        return "OCEAN"
    if elevation < 0.36:
        return "BEACH"
    if elevation > 0.82:
        return "MOUNTAIN"
    if temperature < 0.25:
        return "TUNDRA"
    if moisture < 0.28:
        return "DESERT"
    if moisture > 0.62:
        return "FOREST"
    return "GRASSLAND"


@dataclass(frozen=True)
class ChunkData:
    """Résultat calculé d'une unité de travail."""

    cx: int
    cy: int
    ticks: int
    biome: str
    color: str
    height_m: float
    food: float
    wood: float
    stone: float
    water: float
    population: int
    digest: str

    def summary(self) -> dict:
        d = asdict(self)
        d["height_m"] = round(self.height_m, 2)
        for k in ("food", "wood", "stone", "water"):
            d[k] = round(getattr(self, k), 3)
        return d


def generate_chunk(world_seed: int, cx: int, cy: int, ticks: int = 64) -> ChunkData:
    """Génère + fait évoluer un chunk sur ``ticks`` pas — déterministe.

    Le coût CPU croît avec ``ticks`` : c'est ce qui rend « plus de puissance =
    plus de résolution » concret (le coordinateur augmente ``ticks`` quand le
    réseau grandit).
    """
    elev = _prf_float(world_seed, ["elevation"], [cx, cy])
    moist = _prf_float(world_seed, ["moisture"], [cx, cy])
    temp = _prf_float(world_seed, ["temperature"], [cx, cy])
    biome = _classify(elev, moist, temp)
    color, (fc, wc, sc, watc) = BIOMES[biome]
    height = round((elev - 0.32) * 4000.0, 3)

    # État initial des ressources (capacités par biome).
    food = float(fc) * 8.0
    wood = float(wc) * 15.0
    stone = float(sc) * 50.0
    water = float(watc) * 1e3
    food_cap, wood_cap = float(fc) * 10.0, float(wc) * 20.0

    # Population émergente : pression de portage ~ ressources disponibles.
    carry = _prf_float(world_seed, ["carry"], [cx, cy])
    pop_seed = int((food + wood) * carry)

    # Évolution déterministe sur `ticks` (regrowth + consommation) — coût réel.
    pop = pop_seed
    for t in range(max(1, ticks)):
        # Regrowth borné par capacité.
        if food < food_cap:
            food = min(food_cap, food + food_cap / 7200.0)
        if wood < wood_cap:
            wood = min(wood_cap, wood + wood_cap / 86400.0)
        # Consommation par la population (déterministe, pas de RNG dans la boucle).
        demand = pop * 0.01
        food = max(0.0, food - demand)
        # Démographie : croît si nourri, décroît sinon (pas tous les ticks).
        if t % 16 == 0:
            if food > demand * 4:
                pop += 1 + (pop // 50)
            elif food < demand:
                pop = max(0, pop - 1)

    # On arrondit AVANT le digest : le résumé transmis (mêmes valeurs arrondies)
    # détermine alors exactement le hash → le serveur peut lier résumé↔hash sans
    # tout recalculer (anti-empoisonnement, cf. coordinator.submit).
    food = round(food, 3)
    wood = round(wood, 3)
    stone = round(stone, 3)
    water = round(water, 3)
    digest = chunk_digest(world_seed, cx, cy, ticks, biome, food, wood, stone,
                          water, pop)
    return ChunkData(cx=cx, cy=cy, ticks=ticks, biome=biome, color=color,
                     height_m=height, food=food, wood=wood, stone=stone,
                     water=water, population=pop, digest=digest)


def chunk_digest(world_seed: int, cx: int, cy: int, ticks: int, biome: str,
                 food: float, wood: float, stone: float, water: float,
                 population: int) -> str:
    """Empreinte canonique content-addressed d'un chunk calculé."""
    canon = "|".join([
        "ge-chunk/1", str(world_seed), str(cx), str(cy), str(ticks), biome,
        f"{food:.6f}", f"{wood:.6f}", f"{stone:.6f}", f"{water:.6f}",
        str(population),
    ])
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Seam d'adaptateur : brancher le vrai moteur plus tard sans changer le contrat#
# --------------------------------------------------------------------------- #


def engine_prf_available() -> bool:
    """True si engine.core (le moteur réel) est importable dans cet env."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime = os.path.join(here, "runtime")
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    try:
        import engine.core  # noqa: F401
        return True
    except Exception:
        return False
