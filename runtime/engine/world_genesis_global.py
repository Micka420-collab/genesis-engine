"""Genesis Engine — Wave 22 global world genesis.

Avant Wave 22, chaque ``WorldBuilder`` qui voulait un macro continent
appelait :func:`engine.world_genesis.generate_world` indépendamment de ses
voisins. Si on instanciait 4 régions (par exemple Amazon, Sahara,
Lausanne, Reykjavik), on obtenait quatre :class:`GenesisWorld` séparés,
chacun avec ses propres plaques tectoniques, ses propres fleuves et son
propre climat. Conséquence directe :

  - Aucune plaque ne traverse une frontière régionale.
  - Aucun bassin versant n'est partagé.
  - Le climat est *par îlot* (chaque continent croit qu'il est au
    centre du monde).

Wave 22 corrige cela en livrant **une seule** ``GenesisWorld``
continentale partagée entre N régions, chacune ancrée à une portion via
:class:`engine.world_genesis.GenesisAnchor`. Les fleuves, les plaques et
les biomes deviennent cohérents *inter-régions*.

API publique
------------

::

    config = GlobalGenesisConfig(seed=0xCAFE, map_size_km=8000.0,
                                  resolution=128, n_plates=16,
                                  cache_path="cache/global_world.npz")
    state = build_or_load_global_world(config)

    register_region(state, "amazon",   sim_origin_macro_km=(2000.0, 3000.0))
    register_region(state, "sahara",   sim_origin_macro_km=(5000.0, 2500.0))
    register_region(state, "lausanne", sim_origin_macro_km=(4500.0, 1500.0))

    # Plus tard, quand on instancie chaque sim :
    anchor_amz = attach_region_to_sim(state, sim_amazon, "amazon")
    anchor_sah = attach_region_to_sim(state, sim_sahara, "sahara")
    # `id(state.world) == id(anchor_amz.world) == id(anchor_sah.world)` : tous
    # voient la MÊME GenesisWorld.

    # Diagnostic :
    rivers = find_inter_region_rivers(state)
    summary = global_state_summary(state)

Pureté
------

Aucune RNG en dehors de :func:`engine.world_genesis.generate_world` qui
elle-même route tout via :func:`engine.core.prf_rng`. Deux appels de
``build_or_load_global_world(config)`` avec la même config produisent un
:class:`GenesisWorld` bit-identique (vérifié par
``world_signature`` dans le smoke). Le cache npz utilise
:func:`engine.world_genesis.save_world` /
:func:`engine.world_genesis.load_world` qui ont déjà un round-trip
testé en Wave 16 step 9.

Persistence
-----------

Si ``config.cache_path`` est fourni et que le fichier existe :
``load_world`` est invoqué. Sinon ``generate_world`` est lancé puis
``save_world`` écrit le résultat. Comportement idempotent : un deuxième
appel sur le même chemin charge depuis le disque sans regénérer.

Limitations
-----------

  - Les régions peuvent se chevaucher : aucune vérification d'unicité
    n'est faite. Le smoke step 3 valide qu'on raise sur out-of-bounds,
    pas sur overlap (utile pour des bandes côtières contiguës).
  - :func:`find_inter_region_rivers` est diagnostique : la migration
    inter-région le long des bassins versants n'est PAS branchée
    automatiquement sur :class:`engine.global_world.MigrationCoordinator`.
    À faire dans une future Wave.
  - Aucun streaming inter-sim : un agent ne *traverse* pas physiquement
    une frontière de région ; il faut un :func:`request_migration`
    (Wave 15) explicite. Wave 22 garantit *seulement* que les terrains
    de part et d'autre de la frontière sont cohérents.

Taxonomy tags (ADR 0005)
------------------------

:data:`PIPELINE_LAYER` = ``"Genesis-L0 World Seed"``.
:data:`WORLD_MODEL_CAPABILITY` = ``"paper-L1 Predictor"``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.world_genesis import (
    GenesisAnchor, GenesisParams, GenesisWorld,
    generate_world, load_world, make_anchor,
    save_world, world_signature,
)


PIPELINE_LAYER = "Genesis-L0 World Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Configuration & dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GlobalGenesisConfig:
    """Configuration pour un monde planétaire partagé entre N régions.

    Attributes
    ----------
    seed
        Graine déterministe transmise à :class:`GenesisParams`.
    map_size_km
        Côté carré du monde global, en kilomètres. Par défaut 8000 km
        (~la taille d'un continent réaliste, plus grand que les 4000 km
        de :class:`GenesisParams`).
    resolution
        Nombre de cellules par côté. 128 par défaut (~62 km/cell pour
        8000 km).
    n_plates
        Nombre de plaques tectoniques sur le monde. 16 par défaut (vs
        12 pour un monde régional).
    cache_path
        Si fourni, le monde est chargé depuis ce fichier npz s'il
        existe, sinon généré puis écrit. Aucun side-effect filesystem
        si ``None``.
    """

    seed: int = 0xCAFE
    map_size_km: float = 8000.0
    resolution: int = 128
    n_plates: int = 16
    cache_path: Optional[str] = None

    def to_genesis_params(self) -> GenesisParams:
        """Transcrit la config globale en :class:`GenesisParams` régulier."""
        return GenesisParams(
            seed=int(self.seed) & 0xFFFFFFFFFFFFFFFF,
            map_size_km=float(self.map_size_km),
            resolution=int(self.resolution),
            n_plates=int(self.n_plates),
        )


@dataclass
class RegionAnchor:
    """Une région nommée pointant vers une zone du monde global.

    Attributes
    ----------
    name
        Identifiant unique de la région dans le state.
    sim_origin_macro_km
        Coordonnée macro (en km) à laquelle la coord sim (0, 0) est
        ancrée. C'est le *centre* de la portion du monde que la région
        explore.
    size_km
        Demi-extension carrée de la sim locale en km. La région
        couvre donc ``[origin - size_km, origin + size_km]`` sur les
        deux axes macro.
    blend
        Mélange macro/micro pour le :class:`GenesisAnchor` qu'on
        produira. Voir :class:`engine.world_genesis.GenesisAnchor`.
    """

    name: str
    sim_origin_macro_km: Tuple[float, float]
    size_km: float = 4.0
    blend: float = 1.0


@dataclass
class GlobalGenesisState:
    """Container du monde planétaire partagé + régions et sims attachés."""

    config: GlobalGenesisConfig
    world: GenesisWorld
    regions: Dict[str, RegionAnchor] = field(default_factory=dict)
    # Mapping sim_name -> Simulation. On ne tient pas weakref car les
    # waves précédentes garantissent un lifecycle long.
    registered_sims: Dict[str, object] = field(default_factory=dict)
    # Mapping sim_name -> region_name (pour retrouver l'anchor d'un sim).
    sim_to_region: Dict[str, str] = field(default_factory=dict)
    # Mapping sim_name -> GenesisAnchor produit pour ce sim.
    sim_anchors: Dict[str, GenesisAnchor] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Build / load
# ---------------------------------------------------------------------------

def build_or_load_global_world(
    config: GlobalGenesisConfig,
) -> GlobalGenesisState:
    """Génère ou charge depuis ``config.cache_path`` un monde global.

    Comportement :

      - Si ``cache_path`` est ``None`` : génère systématiquement via
        :func:`engine.world_genesis.generate_world`.
      - Si ``cache_path`` est fourni mais n'existe pas : génère, puis
        écrit via :func:`engine.world_genesis.save_world`. Idempotent
        sur les invocations suivantes.
      - Si ``cache_path`` existe : charge directement via
        :func:`engine.world_genesis.load_world` sans regénérer.

    Détermisme : même ``config`` => même ``world_signature``.

    Returns
    -------
    GlobalGenesisState
        State prêt à recevoir des régions via :func:`register_region`.
    """
    if config.cache_path is not None and os.path.isfile(config.cache_path):
        world = load_world(config.cache_path)
    else:
        params = config.to_genesis_params()
        world = generate_world(params)
        if config.cache_path is not None:
            # On crée le dossier parent si nécessaire (cache/ par ex.).
            parent = os.path.dirname(config.cache_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            save_world(world, config.cache_path)

    return GlobalGenesisState(config=config, world=world)


# ---------------------------------------------------------------------------
# Region registration
# ---------------------------------------------------------------------------

def register_region(state: GlobalGenesisState,
                    name: str,
                    sim_origin_macro_km: Tuple[float, float],
                    size_km: float = 4.0,
                    blend: float = 1.0) -> RegionAnchor:
    """Enregistre une région dans le state.

    Vérifie que la région reste à l'intérieur du monde global :
    ``[0, map_size_km]`` sur les deux axes, en tenant compte de
    ``size_km`` comme demi-extension. Raise :class:`ValueError` sinon.

    Si une région du même nom existe déjà, elle est **remplacée**
    (idempotence sur (name, sim_origin_macro_km)).

    Parameters
    ----------
    state
        Le state retourné par :func:`build_or_load_global_world`.
    name
        Identifiant unique de la région.
    sim_origin_macro_km
        Coordonnée macro (km) de l'origine de la sim locale.
    size_km
        Demi-extension carrée locale.
    blend
        Mélange macro/micro pour le :class:`GenesisAnchor`.

    Returns
    -------
    RegionAnchor
        L'objet d'enregistrement persisté dans ``state.regions``.
    """
    map_size = state.config.map_size_km
    ox, oy = float(sim_origin_macro_km[0]), float(sim_origin_macro_km[1])
    half = float(size_km)

    # Validation bounds : la zone (origin ± size_km) doit rester dans
    # [0, map_size_km]. On laisse une tolérance 1e-6 pour éviter des
    # rejets dus aux arrondis float.
    eps = 1e-6
    if ox - half < -eps or ox + half > map_size + eps:
        raise ValueError(
            f"region '{name}' x out of bounds: origin={ox} size={half} "
            f"-> [{ox - half}, {ox + half}] not in [0, {map_size}]")
    if oy - half < -eps or oy + half > map_size + eps:
        raise ValueError(
            f"region '{name}' y out of bounds: origin={oy} size={half} "
            f"-> [{oy - half}, {oy + half}] not in [0, {map_size}]")

    region = RegionAnchor(name=name,
                           sim_origin_macro_km=(ox, oy),
                           size_km=half,
                           blend=float(blend))
    state.regions[name] = region
    return region


# ---------------------------------------------------------------------------
# Sim attachment
# ---------------------------------------------------------------------------

def attach_region_to_sim(state: GlobalGenesisState,
                         sim,
                         region_name: str) -> GenesisAnchor:
    """Attache une région enregistrée à une simulation.

    Construit un :class:`GenesisAnchor` pointant vers le world global
    avec l'origine macro de la région, puis le branche sur
    ``sim.streamer`` via ``set_genesis`` + ``clear_cache`` pour
    invalider tout chunk pré-calculé.

    Le state mémorise le mapping sim_name <-> region_name. Si le sim
    n'a pas d'attribut ``cfg.name``, son nom est généré à la volée
    (``sim_N``).

    Raises
    ------
    KeyError
        Si la région demandée n'a pas été enregistrée.

    Returns
    -------
    GenesisAnchor
        L'anchor produit. Pointe vers ``state.world`` (id partagé entre
        toutes les régions).
    """
    if region_name not in state.regions:
        raise KeyError(
            f"region '{region_name}' not registered "
            f"(known: {list(state.regions.keys())})")
    region = state.regions[region_name]
    anchor = make_anchor(state.world,
                         sim_origin_macro_km=region.sim_origin_macro_km,
                         blend=region.blend)
    # Nom du sim : tente cfg.name, sinon fabrique-en un.
    sim_name = ""
    try:
        sim_name = str(getattr(sim.cfg, "name", "") or "")
    except Exception:
        sim_name = ""
    if not sim_name:
        sim_name = f"sim_{len(state.registered_sims)}"

    # Brancher sur le streamer (cf. Wave 16b).
    streamer = getattr(sim, "streamer", None)
    if streamer is not None:
        if hasattr(streamer, "set_genesis"):
            streamer.set_genesis(anchor)
        if hasattr(streamer, "clear_cache"):
            streamer.clear_cache()

    state.registered_sims[sim_name] = sim
    state.sim_to_region[sim_name] = region_name
    state.sim_anchors[sim_name] = anchor
    return anchor


# ---------------------------------------------------------------------------
# Inter-region rivers
# ---------------------------------------------------------------------------

def _region_macro_cell_bounds(state: GlobalGenesisState,
                              region: RegionAnchor
                              ) -> Tuple[int, int, int, int]:
    """Calcule les indices [ix0, iy0, ix1, iy1] de la grille macro
    couverts par une région (inclusifs côté min, exclusifs côté max).
    """
    p = state.world.params
    cell_km = p.map_size_km / p.resolution
    ox, oy = region.sim_origin_macro_km
    half = region.size_km
    ix0 = int(np.clip(np.floor((ox - half) / cell_km), 0, p.resolution - 1))
    iy0 = int(np.clip(np.floor((oy - half) / cell_km), 0, p.resolution - 1))
    ix1 = int(np.clip(np.ceil((ox + half) / cell_km), 1, p.resolution))
    iy1 = int(np.clip(np.ceil((oy + half) / cell_km), 1, p.resolution))
    return ix0, iy0, ix1, iy1


def _macro_cell_to_region(state: GlobalGenesisState,
                          ix: int, iy: int) -> Optional[str]:
    """Renvoie le nom de la première région dont la grille macro couvre
    la cellule (ix, iy), ou None si aucune.
    """
    for name, region in state.regions.items():
        rx0, ry0, rx1, ry1 = _region_macro_cell_bounds(state, region)
        if rx0 <= ix < rx1 and ry0 <= iy < ry1:
            return name
    return None


# D8 displacements (alignés sur engine.world_genesis._D8_DX/_D8_DY).
_D8_DX = np.array([1, 1, 0, -1, -1, -1, 0, 1], dtype=np.int8)
_D8_DY = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=np.int8)


def find_inter_region_rivers(state: GlobalGenesisState,
                             flow_acc_threshold: float = 30.0
                             ) -> List[Dict[str, object]]:
    """Détecte les rivières (cellules macro avec ``flow_acc >= threshold``)
    qui traversent une frontière inter-région.

    Algorithme :

      Pour chaque région enregistrée, on échantillonne sa grille
      macro. Pour chaque cellule de la région qui est un fleuve, on
      regarde où elle s'écoule (via ``flow_dir`` D8). Si la cellule
      réceptrice tombe dans une autre région enregistrée, on
      enregistre le passage.

    Parameters
    ----------
    state
        Le state du monde global.
    flow_acc_threshold
        Seuil minimal de ``flow_acc`` pour qu'une cellule soit
        considérée comme rivière. Défaut 30.0 (proche du
        ``river_threshold_cells`` du :class:`GenesisParams`).

    Returns
    -------
    List[Dict]
        Une liste (possiblement vide) de dicts avec :

          - ``from_region`` : nom de la région source
          - ``to_region`` : nom de la région destination
          - ``macro_x_km`` / ``macro_y_km`` : coordonnée macro (km) de
            la cellule source
          - ``flow_acc`` : drainage area de la cellule source
    """
    world = state.world
    p = world.params
    cell_km = p.map_size_km / p.resolution
    R = p.resolution
    flow_acc = world.flow_acc
    flow_dir = world.flow_dir

    crossings: List[Dict[str, object]] = []

    for src_name, region in state.regions.items():
        rx0, ry0, rx1, ry1 = _region_macro_cell_bounds(state, region)
        for iy in range(ry0, ry1):
            for ix in range(rx0, rx1):
                acc = float(flow_acc[iy, ix])
                if acc < flow_acc_threshold:
                    continue
                fd = int(flow_dir[iy, ix])
                if fd == 255:
                    continue
                # Cellule réceptrice via D8.
                nx = ix + int(_D8_DX[fd])
                ny = iy + int(_D8_DY[fd])
                if nx < 0 or nx >= R or ny < 0 or ny >= R:
                    continue
                # Eviter de marquer une cellule encore dans la même région.
                dst_name = _macro_cell_to_region(state, nx, ny)
                if dst_name is None or dst_name == src_name:
                    continue
                crossings.append({
                    "from_region": src_name,
                    "to_region": dst_name,
                    "macro_x_km": float((ix + 0.5) * cell_km),
                    "macro_y_km": float((iy + 0.5) * cell_km),
                    "flow_acc": acc,
                })
    return crossings


# ---------------------------------------------------------------------------
# Diagnostics / reporter
# ---------------------------------------------------------------------------

def global_state_summary(state: GlobalGenesisState) -> Dict[str, object]:
    """Reporter compact pour dashboards / smokes.

    Returns
    -------
    Dict
        Champ ``world_signature`` (SHA-256), nombre de régions et de
        sims attachés, liste des régions avec leurs métadonnées,
        diagnostics du :class:`GenesisWorld` sous-jacent.
    """
    sig = world_signature(state.world)
    regions_info = []
    for name, region in state.regions.items():
        regions_info.append({
            "name": name,
            "sim_origin_macro_km": region.sim_origin_macro_km,
            "size_km": region.size_km,
            "blend": region.blend,
        })
    return {
        "world_signature": sig,
        "world_signature_short": sig[:16],
        "map_size_km": state.config.map_size_km,
        "resolution": state.config.resolution,
        "n_plates": state.config.n_plates,
        "seed": int(state.config.seed),
        "n_regions": len(state.regions),
        "n_sims_registered": len(state.registered_sims),
        "regions": regions_info,
        "sims_to_regions": dict(state.sim_to_region),
        "world_diagnostics": dict(state.world.diagnostics),
        "cache_path": state.config.cache_path,
    }


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "GlobalGenesisConfig",
    "GlobalGenesisState",
    "RegionAnchor",
    "attach_region_to_sim",
    "build_or_load_global_world",
    "find_inter_region_rivers",
    "global_state_summary",
    "register_region",
]
