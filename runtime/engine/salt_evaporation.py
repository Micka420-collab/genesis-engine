"""Genesis Engine — Substrate capability : sel d'évaporation solaire (Cap. C15).

**Le 8ᵉ opérateur ORTHOGONAL — SÉCHER AU SOLEIL (solar evaporation).** Réponse
directe à la reco ``R-J9-1`` de l'audit J+9
(``native/world-engine/AUDIT-DELTA-2026-06-19.md``) : « choisir le 8ᵉ opérateur
**avant** de revenir au feu ». C14 (``cryoclasty``) avait rompu la chaîne de 7
capacités *fire-based* en ajoutant le verbe **ramasser** ; pour ne pas retomber
dans le treadmill du foyer, cette capacité ajoute un verbe primitif **non
thermique** de plus : **laisser l'eau s'évaporer au soleil**. Le soleil fait le
travail — aucun feu, aucune percussion, aucune fonte.

C'est la 4ᵉ branche de la liste explicite des candidats orthogonaux de
``R-J9-1`` (eau bouillante / fermentation / **séchage solaire** / levier), et
la plus fondamentale de l'âge de pierre : le **sel solaire** (marais salants,
sabkhas, salars). Le sel conserve la viande et le poisson — il **structure le
commerce** néolithique (« or blanc ») bien avant le métal.

**Règle invariante du projet** (cf. ``water_potability`` (C3), ``cryoclasty``
(C14)) : rien n'est scripté. Un agent ne *sait* pas qu'une lagune salée laissée
au soleil donnera du sel — il **VOIT** une croûte blanche d'efflorescence sur
un bas-fond aride, puis décide lui-même d'aller la **récolter**. La découverte
est émergente ; ce module ne fait qu'exposer un **signal physique véridique**.

Pourquoi ce module — et ce qu'il consomme
-----------------------------------------
C3 (``water_potability``) a livré la perception de la **salinité** : le goût
salé qui dit « ne bois pas ». Mais cette même salinité est une **ressource**
quand le climat l'évapore. Ce module **consomme C3** (la salinité véridique du
plan d'eau) et la **croise avec le climat aride** (le déficit d'évaporation
issu des champs macro ``temp_c`` / ``precip_mm``) pour exposer le **potentiel
de sel solaire** d'un lieu. C'est l'**inversion exacte de C3** : là où C3 dit
« trop salée pour boire », C15 dit « assez salée pour récolter » — le **même
seuil** ``POTABLE_MAX_PPT`` sépare les deux lectures.

Ce n'est PAS un ``*_observer.py`` qui *mesure* le tick — c'est un **signal de
monde interrogeable** que les agents *consomment pour agir*. Coût tick **nul** :
les indices sont calculés paresseusement par chunk et mémorisés. Il échappe au
moratoire observateurs (``CONTRIBUTING.md`` §"Moratoire observateurs").

L'orthogonalité (pourquoi C15 ≠ C7..C13)
----------------------------------------
* **C7..C13** = *allumer / chauffer / fondre* : toute la chaleur vient du
  **foyer** (combustion). Sept capacités empilées sur le même verbe (verrou D9).
* **C15** = *sécher* : la chaleur vient du **soleil**, gratuitement, sans
  combustible. La transformation (saumure → sel) est **passive et solaire**.

Le 8ᵉ verbe primitif réellement nouveau : sentir / voir / tâter / casser (C2) /
boire (C3) / allumer (C7) / ramasser (C14) / **sécher au soleil** (C15).

La physique de l'évaporation solaire (marais salant)
----------------------------------------------------
Le sel précipite quand **l'évaporation potentielle dépasse l'apport d'eau** :
une saumure peu profonde se concentre jusqu'à saturation de l'halite (NaCl),
puis croûte. Deux vérités indépendantes sont requises :

1. **Une eau réellement saline** — C3 ``salinity_ppt ≥ MIN_BRINE_PPT`` (mer,
   estuaire côtier, source de saumure halite). Sous ce seuil, l'eau est douce /
   potable : l'évaporer ne laisse rien (silence véridique).
2. **Un climat net-évaporatif** — le **seuil d'aridité de Köppen**
   (``20·T + 280``, cf. ``engine.koeppen_grid._p_thresh`` — la **SSOT** du
   critère « B aride » du moteur) : le climat est évaporatif quand
   ``precip_mm < p_thresh``. Le **déficit** ``net_evap_mm = p_thresh − precip``
   est la lame d'eau (mm/an) que le soleil peut évaporer au-delà de la pluie.

Le rendement physique en sel (kg/m²/an) :

    salt_yield = net_evap_mm × 1e-3 [m d'eau évaporée] × salinity_ppt [≈ kg/m³]

L'eau de mer (35 ppt) sous 1000 mm de déficit annuel → 35 kg/m²/an : l'ordre de
grandeur réel des salines solaires (~10–40 kg/m²/an). ``harvestable`` n'est vrai
qu'au-dessus de ``MIN_HARVEST_KG_M2``.

Le MENSONGE RENDU VISIBLE #6
----------------------------
(pendant de l'obsidienne C8, du kaolin C9, du cuivre C13, de l'arène C14.)
Une **lagune tout aussi salée** dans un climat **humide** (``precip ≥ p_thresh``)
→ ``net_evap = 0`` → **aucune croûte** : la pluie redilue plus vite que le soleil
n'évapore. La **même saumure** sous un climat **aride** → sel abondant. « Eau
salée » n'est PAS un signal fiable de sel : c'est le **bilan évaporatif** qui
décide. Le monde montre l'eau salée (vrai, via C3) ; ``harvestable`` /
``salt_yield_kg_m2`` disent la vérité sur ce qu'on en tirera.

Le monde ne ment jamais
-----------------------
Un indice de sel n'est émis QUE si une **eau saline réelle** est présente
(``salinity_ppt ≥ MIN_BRINE_PPT``, vérité C3 dérivée du biome OCEAN / de
l'halite peu profonde / de l'intrusion côtière). ``harvestable`` n'est vrai que
si **en plus** le climat est net-évaporatif. La réciproque est volontairement
*faible* (pas de croûte perçue ⇏ pas de sel ailleurs) : on ne donne pas la carte
des salines ; l'agent prospecte.

N'introduit AUCUN nouveau tell
------------------------------
COMPOSE C3 (``water_potability`` — salinité) × le critère d'aridité de
``koeppen_grid`` (climat). Pas de ``_PROFILE`` propre, pas d'entrée ``PY_TO_RUST``
(garde-fou **D8 — 9ᵉ fois par composition** ; voir
``test_geology_cross_language_contract.py`` et ``test_salt_evaporation.py``).
Hors glob ``*_outcrop.py`` : le fichier s'appelle ``salt_evaporation.py`` à
dessein.

Périmètre honnête (audit)
-------------------------
* ``harvest_salt_at`` est un **aperçu non mutant** (preview) : il ne consomme NI
  ``chunk.water`` NI la saumure (contrairement au ``smelt_at`` mutant de C13).
  D10 (frontière de mutation cross-langage) reste donc **gelé** — comme le
  recommande ``R-J9-2``.
* Le climat est dérivé des champs **macro** (seed) échantillonnés au point de
  l'agent, exactement comme C14 pour le champ de gel. Pas de solveur
  d'évaporation transitoire : c'est un **potentiel** climatique annuel, à
  l'altitude perception/stone-age.
* La **profondeur** réelle du plan d'eau n'est pas modélisée (C3 ne distingue
  pas mer ouverte profonde et bas-fond) : le rendement est un potentiel par m²
  de surface saline. Une mer enclavée aride (Mer Morte, Lac Assal) précipite
  réellement l'halite à ses marges — le modèle reste physiquement défendable.

Déterminisme
------------
Pur : fonction de la salinité C3 (issue du seed) + des champs macro climat
(``temp_c`` / ``precip_mm``, issus du seed). Aucun RNG nouveau. Bit-identique
entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — le sel solaire est une lecture
dérivée du substrat (salinité + climat), comme C1/C2/C3/C14.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape
(point → indice), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

from engine import koeppen_grid as kp
from engine import water_potability as wp
from engine.world import CHUNK_SIDE_M, world_to_chunk
from engine.world_genesis import sample_macro

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# Below this salinity (ppt) the water is fresh / potable: evaporating it leaves
# no meaningful salt. Bound to C3's potability ceiling so the two capabilities
# share ONE boundary — the elegant inversion: C3 "too salty to drink" above this
# is exactly C15 "salty enough to harvest". (POTABLE_MAX_PPT == 3.0 ppt.)
MIN_BRINE_PPT = wp.POTABLE_MAX_PPT

# Standard seawater salinity (reused from C3) — the normalisation reference.
SEAWATER_PPT = wp.SEAWATER_PPT

# Minimum annual solar-salt yield (kg/m²/yr) for a pan to be worth harvesting.
# Real solar salterns yield ~10–40 kg/m²/yr; 5 is a meaningful, modest floor.
MIN_HARVEST_KG_M2 = 5.0

# At/above this yield the pan is a copious salar (a striking white expanse).
ABUNDANT_KG_M2 = 20.0

# Aridity-surplus zone bounds (fraction of the Köppen dryness deficit). Mirrors
# the UNEP aridity tiers in spirit (hyper-arid / arid / semi-arid / humid).
HYPERARID_SURPLUS = 0.66
ARID_SURPLUS = 0.33


class SaltPanClass(IntEnum):
    """What the agent perceives at a saline water body under the sky."""
    SALINE_LAGOON = 0   # salty water, NO crust (humid climate — the lie #6)
    SALT_FLAT = 1       # a thin salt rime forms (semi-arid)
    SALT_PAN = 2        # a clear harvestable salt pan (arid)
    SALAR = 3           # a copious blinding-white salt expanse (hyper-arid)


# Perceived surface colour / luster (RGB). A barren saline lagoon reads as dull
# brackish water (aligned with C3); a true pan reads as white efflorescence
# (aligned with C1's salt crust rgb (235,235,240) and C3's BRINE rgb).
_CLASS_RGB: Dict[SaltPanClass, Tuple[int, int, int]] = {
    SaltPanClass.SALINE_LAGOON: (120, 145, 150),   # salty water, no crust
    SaltPanClass.SALT_FLAT:     (200, 205, 205),    # patchy rime
    SaltPanClass.SALT_PAN:      (235, 236, 240),    # clear white crust
    SaltPanClass.SALAR:         (246, 247, 250),    # blinding salt expanse
}

_CLASS_LABEL: Dict[SaltPanClass, str] = {
    SaltPanClass.SALINE_LAGOON: "lagune salée sans croûte (le climat la dilue)",
    SaltPanClass.SALT_FLAT:     "bas-fond salé (mince efflorescence)",
    SaltPanClass.SALT_PAN:      "marais salant (croûte de sel récoltable)",
    SaltPanClass.SALAR:         "salar (étendue de sel blanc éblouissante)",
}


@dataclass(frozen=True)
class SaltPanCue:
    """A truthful solar salt-pan cue at one chunk.

    ``pan_class``/``label``/``rgb`` = what an agent *perceives* (a white crust,
    or just salty water). ``salinity_ppt``/``salt_yield_kg_m2``/``harvestable``
    = the ground truth it must agree with. It is NOT handed to the agent as
    "this is salt" — the agent learns the brine+sun→salt correlation by drying
    and tasting (emergence). It composes C3 (``source``/``salinity_ppt``).
    """
    coord: Tuple[int, int, int]
    source: str                 # C3 origin: "sea" | "coastal" | "brine_spring"
    salinity_ppt: float         # C3 ground-truth salinity of the water body
    temp_c: float               # local mean annual temperature (°C)
    precip_mm: float            # local mean annual precipitation (mm)
    p_thresh_mm: float          # Köppen dryness threshold (≈ potential evap)
    net_evap_mm: float          # annual evaporative deficit (mm) = max(0, p_th−P)
    aridity_surplus: float      # net_evap / p_thresh in [0, 1]
    salt_yield_kg_m2: float     # solar-salt yield (kg/m²/yr) — the ground truth
    harvestable: bool           # salt_yield ≥ MIN_HARVEST_KG_M2
    pan_class: SaltPanClass
    label: str
    rgb: Tuple[int, int, int]
    zone: str                   # "hyperarid" | "arid" | "semiarid" | "humid"
    abundant: bool              # copious salar (yield ≥ ABUNDANT_KG_M2)
    water_litres: float         # surface water available at the chunk (C3)
    biome: int
    confidence: float           # perceptual confidence in [0, 1]


# ---------------------------------------------------------------------------
# Climate aridity — single source of truth = the Köppen dryness threshold.
# ---------------------------------------------------------------------------

def _aridity(temp_c: float, precip_mm: float) -> Tuple[float, float, float]:
    """Return ``(p_thresh_mm, net_evap_mm, aridity_surplus)``.

    ``p_thresh`` is the Köppen dryness threshold (``20·T + 280`` for T≥0), reused
    **verbatim** from :func:`engine.koeppen_grid._p_thresh` so this capability
    and the engine's biome classifier never disagree on what "arid" means.
    A net-evaporative climate has ``precip < p_thresh`` → ``net_evap > 0``. For
    very cold cells (``p_thresh ≤ 0``) the surplus is 0: cold deserts do not
    solar-evaporate — that domain belongs to frost (C14), not the sun.
    """
    p_thresh = float(kp._p_thresh(float(temp_c)))
    if p_thresh <= 0.0:
        return p_thresh, 0.0, 0.0
    net_evap = max(0.0, p_thresh - float(precip_mm))
    surplus = min(1.0, net_evap / p_thresh)
    return p_thresh, net_evap, surplus


def _aridity_zone(surplus: float) -> str:
    if surplus <= 0.0:
        return "humid"
    if surplus >= HYPERARID_SURPLUS:
        return "hyperarid"
    if surplus >= ARID_SURPLUS:
        return "arid"
    return "semiarid"


def _classify_pan(harvestable: bool, salt_yield: float, surplus: float
                  ) -> SaltPanClass:
    """The perceived pan class. No crust unless the climate actually crusts it."""
    if not harvestable:
        return SaltPanClass.SALINE_LAGOON          # the lie #6 (salty, no salt)
    if salt_yield >= ABUNDANT_KG_M2 and surplus >= HYPERARID_SURPLUS:
        return SaltPanClass.SALAR
    if surplus >= ARID_SURPLUS:
        return SaltPanClass.SALT_PAN
    return SaltPanClass.SALT_FLAT


# ---------------------------------------------------------------------------
# Core derivation — pure, testable with synthetic salinity + climate inputs.
# ---------------------------------------------------------------------------

def _saltpan_from_inputs(coord, salinity_ppt: float, source: str,
                         water_litres: float, temp_c: float, precip_mm: float,
                         biome: int) -> Optional[SaltPanCue]:
    """Pure derivation of the salt-pan cue from explicit salinity + climate.

    Returns ``None`` (truthful silence) when the water is fresh/potable
    (``salinity_ppt < MIN_BRINE_PPT``) — nothing to crystallise. Otherwise a cue
    is always emitted (the agent perceives salty water); ``harvestable`` then
    tells the truth about whether the climate actually precipitates salt.
    """
    if salinity_ppt < MIN_BRINE_PPT:
        return None  # fresh / potable water → no brine to evaporate (truthful)
    p_thresh, net_evap, surplus = _aridity(temp_c, precip_mm)
    # kg/m²/yr ≈ (m of water evaporated) × (kg salt per m³ ≈ ppt).
    salt_yield = net_evap * 1e-3 * float(salinity_ppt)
    harvestable = salt_yield >= MIN_HARVEST_KG_M2
    abundant = salt_yield >= ABUNDANT_KG_M2
    zone = _aridity_zone(surplus)
    pan_class = _classify_pan(harvestable, salt_yield, surplus)
    sal_norm = min(1.0, float(salinity_ppt) / SEAWATER_PPT)
    # Confidence rises with how saline the water is and how strongly the climate
    # evaporates: a blinding salar reads loud, a faint humid brackish marsh faint.
    confidence = float(min(1.0, sal_norm * (0.4 + 0.6 * surplus)))
    return SaltPanCue(
        coord=tuple(int(c) for c in coord),
        source=str(source), salinity_ppt=float(round(salinity_ppt, 4)),
        temp_c=float(round(temp_c, 4)), precip_mm=float(round(precip_mm, 4)),
        p_thresh_mm=float(round(p_thresh, 4)),
        net_evap_mm=float(round(net_evap, 4)),
        aridity_surplus=float(round(surplus, 6)),
        salt_yield_kg_m2=float(round(salt_yield, 6)),
        harvestable=bool(harvestable), pan_class=pan_class,
        label=_CLASS_LABEL[pan_class], rgb=_CLASS_RGB[pan_class], zone=zone,
        abundant=bool(abundant), water_litres=float(water_litres),
        biome=int(biome), confidence=confidence)


# ---------------------------------------------------------------------------
# Macro-climate access (read the seed climate field at a point) — mirrors C14.
# ---------------------------------------------------------------------------

def _resolve_anchor(sim) -> Tuple[Optional[object], Optional[Tuple[float, float]]]:
    """Locate the GenesisWorld + its sim→macro origin (km), to sample the macro
    climate at the agent's location. Mirrors :func:`engine.cryoclasty._resolve_anchor`."""
    boot = getattr(sim, "_genesis_bootstrap_state", None)
    if boot is not None:
        anchor = getattr(boot, "anchor", None)
        if anchor is not None and getattr(anchor, "world", None) is not None:
            return anchor.world, tuple(anchor.sim_origin_macro_km)
    streamer = getattr(sim, "streamer", None)
    if streamer is not None:
        anchor = getattr(streamer, "genesis", None)
        if anchor is not None and getattr(anchor, "world", None) is not None:
            return anchor.world, tuple(anchor.sim_origin_macro_km)
    return None, None


def _climate_at(world, origin: Tuple[float, float],
                coord: Tuple[int, int, int]) -> Tuple[float, float]:
    """(temp_c, precip_mm) of the macro climate at the chunk centre."""
    cx, cy, _cz = coord
    x_km = (cx + 0.5) * CHUNK_SIDE_M * 0.001 + float(origin[0])
    y_km = (cy + 0.5) * CHUNK_SIDE_M * 0.001 + float(origin[1])
    m = sample_macro(world, x_km, y_km)
    return float(m["temp_c"]), float(m["precip_mm"])


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_salt_evaporation(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim``.

    Adds **zero** per-tick cost: cues are derived on query and memoised.
    Returns the cache dict (``sim._saltpan_cue_cache``)."""
    wp.install_water_potability(sim)  # ensure C3 salinity perception exists
    cache = getattr(sim, "_saltpan_cue_cache", None)
    if cache is None:
        cache = {}
        sim._saltpan_cue_cache = cache
    return cache


def saltpan_cue_for_chunk(sim, coord: Tuple[int, int, int]
                          ) -> Optional[SaltPanCue]:
    """Truthful solar salt-pan cue at ``coord`` (or None). Memoised.

    Invariant: a returned cue means C3 says the water here is genuinely saline
    (``salinity_ppt ≥ MIN_BRINE_PPT``). ``harvestable`` is True only when the
    macro climate is net-evaporative enough to crust the brine into salt."""
    coord = tuple(int(c) for c in coord)
    cache = install_salt_evaporation(sim)
    if coord in cache:
        return cache[coord]
    water = wp.water_cue_for_chunk(sim, coord)
    world, origin = _resolve_anchor(sim)
    if water is None or world is None or origin is None:
        cache[coord] = None
        return None
    if water.salinity_ppt < MIN_BRINE_PPT:
        cache[coord] = None      # fresh / potable water → no brine (truthful)
        return None
    temp_c, precip_mm = _climate_at(world, origin, coord)
    cue = _saltpan_from_inputs(coord, water.salinity_ppt, water.source,
                               water.water_litres, temp_c, precip_mm,
                               water.biome)
    cache[coord] = cue
    return cue


def prospect_saltpan(sim, world_x: float, world_y: float) -> Optional[SaltPanCue]:
    """What an agent at world ``(x, y)`` perceives of the solar salt potential
    here: the crust's look + truthful yield, or None if no saline water."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return saltpan_cue_for_chunk(sim, coord)


def harvest_salt_at(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of what harvesting solar salt at ``(x, y)``
    yields — the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no water consumed, no brine depleted, unlike C13
    ``smelt_at``): it is the truth oracle of the SOLAR-DRY verb, not the action.
    ``harvestable`` is True only when the brine actually crusts into salt — a
    saline lagoon in a humid climate returns ``harvestable=False`` (the lie #6)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = saltpan_cue_for_chunk(sim, coord)
    if cue is None:
        return {"material": None, "salt_yield_kg_m2": 0.0, "harvestable": False,
                "salinity_ppt": 0.0, "aridity_surplus": 0.0, "source": None,
                "zone": None, "abundant": False}
    return {"material": "halite", "salt_yield_kg_m2": cue.salt_yield_kg_m2,
            "harvestable": cue.harvestable, "salinity_ppt": cue.salinity_ppt,
            "aridity_surplus": cue.aridity_surplus, "source": cue.source,
            "zone": cue.zone, "abundant": cue.abundant,
            "pan_class": cue.pan_class.name}


def discover_saltpans_by_sight(sim, rows: List[int],
                               perception_radius_m: float = 128.0
                               ) -> Dict[int, List[SaltPanCue]]:
    """For each agent ``row``, the salt-pan cues perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static brine + climate into a **perceivable, actionable** signal —
    the agent then *chooses* where to dry salt. Deterministic order (chunk
    distance then coord)."""
    out: Dict[int, List[SaltPanCue]] = {}
    if not rows:
        return out
    install_salt_evaporation(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], SaltPanCue]] = []
        for dy in range(-span, span + 1):
            for dx in range(-span, span + 1):
                coord = (ccx + dx, ccy + dy, ccz)
                if sim.streamer.cache.get(coord) is None:
                    continue
                cx_center = (coord[0] + 0.5) * CHUNK_SIDE_M
                cy_center = (coord[1] + 0.5) * CHUNK_SIDE_M
                d2 = (cx_center - ax) ** 2 + (cy_center - ay) ** 2
                if d2 > r2:
                    continue
                cue = saltpan_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_saltpan_near(sim, row: int, perception_radius_m: float = 192.0
                      ) -> Optional[SaltPanCue]:
    """The single best **harvestable** salt pan an agent at ``row`` can perceive
    — the actionable pick when seeking salt to preserve food.

    Skips barren saline lagoons (``harvestable == False``): an agent at a humid
    salty lagoon must keep walking to find an arid pan, exactly as in reality.
    Returns None if every perceivable saline body is barren (or none in sight)."""
    cues = discover_saltpans_by_sight(sim, [int(row)], perception_radius_m
                                      ).get(int(row), [])
    workable = [c for c in cues if c.harvestable]
    if not workable:
        return None
    # distance-sorted already; pick the richest pan, ties keep nearest order.
    return max(workable, key=lambda c: c.salt_yield_kg_m2)


def salt_evaporation_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_salt_evaporation(sim)
    by_zone: Dict[str, int] = {}
    by_class: Dict[str, int] = {}
    n_chunks = 0
    n_saline = 0
    n_harvestable = 0
    best_yield = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = saltpan_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_saline += 1
        if cue.harvestable:
            n_harvestable += 1
        by_zone[cue.zone] = by_zone.get(cue.zone, 0) + 1
        by_class[cue.pan_class.name] = by_class.get(cue.pan_class.name, 0) + 1
        best_yield = max(best_yield, cue.salt_yield_kg_m2)
    return {
        "n_chunks": n_chunks,
        "n_chunks_with_brine": n_saline,
        "n_harvestable": n_harvestable,
        "brine_rate": round(n_saline / n_chunks, 4) if n_chunks else 0.0,
        "harvestable_rate": round(n_harvestable / n_saline, 4) if n_saline else 0.0,
        "best_salt_yield_kg_m2": round(best_yield, 4),
        "by_zone": dict(sorted(by_zone.items())),
        "by_class": dict(sorted(by_class.items())),
    }


__all__ = [
    "SaltPanCue", "SaltPanClass",
    "install_salt_evaporation", "saltpan_cue_for_chunk",
    "prospect_saltpan", "harvest_salt_at", "discover_saltpans_by_sight",
    "best_saltpan_near", "salt_evaporation_summary",
    "MIN_BRINE_PPT", "SEAWATER_PPT", "MIN_HARVEST_KG_M2", "ABUNDANT_KG_M2",
    "HYPERARID_SURPLUS", "ARID_SURPLUS",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
