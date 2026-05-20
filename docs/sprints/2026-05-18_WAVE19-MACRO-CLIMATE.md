# Wave 19 — Macro Climate Propagation

**Date :** 2026-05-18 (session 34e)
**Module livré :** `engine.macro_climate`
**Smoke :** `scripts/p48_macro_climate_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Levier #2 de l'audit Wave 18 (5 candidates classées). Le problème
identifié : avant Wave 19, **trois sources de vent indépendantes**
co-existaient dans le moteur :

| Module | Modèle de vent | Source |
|---|---|---|
| `meteorology` | Gradient de pression synthétique + Coriolis | `_wind_for_chunk(lat, lon, hour, alt, tick, seed)` |
| `marine` | Synoptic-scale period (6 sim-days) + phase per-chunk | `_wind_for_chunk(sim, coord)` |
| `wildfire` | Tuple `wind=(vx, vy)` optionnel du caller | `tick_fire_spread(wind=...)` |

Conséquence: un cyclone meteo soufflait vers l'est pendant que le
courant marin en-dessous dérivait vers l'ouest et qu'un incendie sur la
même côte propageait dans le vent nul.

Pendant ce temps, `engine.world_genesis.GenesisWorld` calculait depuis
Wave 16 un **champ de vent continental cohérent** (cellules
Hadley / Ferrel / polaires) mais personne ne le lisait.

Wave 19 branche les trois sur cette source unique.

---

## Architecture

```
GenesisWorld (Wave 16)
    └─ wind_u[R, R], wind_v[R, R]   m/s east+north positive
                                     ITCZ + trade winds + westerlies + polar

ChunkAnchor (Wave 16b)
    └─ sim_origin_macro_km           sim mètres ↔ macro km

macro_climate.sample_macro_wind_at(anchor, x_m, y_m)
    └─ bilinear lookup -> (u_ms, v_ms)

install_macro_climate(sim, anchor, *, blend=1.0)
    ├─ patch engine.marine._wind_for_chunk(sim, coord)
    │       → chunk_wind_at(state.anchor, coord)
    │       (blend lerps with legacy if blend<1)
    ├─ patch engine.meteorology.tick_meteorology(sim, state)
    │       → après l'original, overwrite cell.wind_u/v/speed par macro
    └─ patch engine.wildfire.tick_wildfire(sim, *, wind=None)
            → si wind=None, injecte la moyenne macro across chunks
```

### Pureté

`sample_macro_wind_at` est une pure-function : aucune RNG, aucune
mutation. Deux appels avec mêmes args -> bit-identique. Pas de cache
nécessaire (le coût est O(1) par appel).

### Idempotence

`install_macro_climate(sim, anchor)` set un module-level flag
`_macro_orig_<fn>` sur chaque module patché. Si déjà présent, n'écrase
pas (premier install est canonique). Les installs suivants juste
update l'anchor active. Compteur `modules_patched` ≤ 3 toujours.

### Blend

`blend = 1.0` (défaut) = pur macro. `blend = 0.0` = legacy synthétique.
Intermédiaire = lerp linéaire :

```
wind_returned = wind_macro * blend + wind_legacy * (1 - blend)
```

Utile pour A/B testing, ou pour transition douce quand l'anchor change
mid-sim.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique (`sample_*`, `install_*`, etc.) | OK |
| 2 | `sample_macro_wind_at` match macro at cell center (err=0.000) | OK |
| 3 | `marine._wind_for_chunk` legacy(+3.05,+0.06) → macro(-1.0,0.0) | OK |
| 4 | `meteorology.tick_meteorology` 91 cells, max_err=0.0000 | OK |
| 5 | `wildfire.tick_wildfire` reçoit `wind=(-1.0, 0.0)` injecté | OK |
| 6 | `blend=0.5` lerps : 0.5×(-1) + 0.5×3.05 = 1.025 (mesuré 1.03) | OK |
| 7 | Install idempotent, `modules_patched=3` | OK |
| 8 | Déterminisme bit-identique inter-sims | OK |
| 9 | Uninstall restaure les 3 originals | OK |

Particularité step 3 : on observe le passage **immédiat** du wind
legacy synthétique (+3.05, +0.06) m/s — bruit synoptique non aligné —
au macro ITCZ (-1.0, 0.0) m/s — alizé d'est cohérent. Voir
`engine.world_genesis._atmospheric_circulation` pour la table de
référence des bandes latitudinales.

---

## API publique

```python
from engine.macro_climate import (
    # Pure function lookups
    sample_macro_wind_at,    # anchor, x_m, y_m -> (u, v)
    chunk_wind_at,           # anchor, coord    -> (u, v)

    # Sim integration
    install_macro_climate,   # sim, anchor, *, blend=1.0 -> state
    uninstall_macro_climate, # sim -> bool
    macro_climate_state,     # sim -> diagnostics dict
    MacroClimateState,
)
```

### Usage type minimal

```python
from engine.world_genesis import generate_world, make_anchor, GenesisParams
from engine.macro_climate import install_macro_climate

world = generate_world(GenesisParams(seed=0xCAFE))
sim.streamer.set_genesis(make_anchor(world))
install_meteorology(sim)
install_marine(sim)
install_wildfire(sim)
install_macro_climate(sim, anchor)   # une ligne, 3 modules unifiés
```

### Usage type pipeline complet (Waves 16 + 16b + 17 + 18 + 19)

```python
world = generate_world(GenesisParams(seed=0xCAFE, resolution=128))
anchor = make_anchor(world)
sim.streamer.set_genesis(anchor)
sim.streamer.clear_cache()

install_geology(sim)
install_tectonic_overlay(sim, anchor)   # Wave 17 — provinces minéralisées
install_chunk_hydrology(sim, anchor)    # Wave 18 — rivières macro

install_meteorology(sim)
install_marine(sim)
install_wildfire(sim)
install_macro_climate(sim, anchor)      # Wave 19 — vent unifié
```

---

## Limitations connues

- **Pas de variabilité temporelle** : le macro wind est statique (snapshot
  à `t=0`). Pas de jets diurnes, pas de mousson saisonnière. Pour ça il
  faudrait recoupler avec une dérivée temporelle ou un overlay seasonal.
- **Pas de cyclones macro** : la macro `wind_u/v` est un champ régional
  moyen. Les cyclones tropicaux restent générés par
  `_maybe_form_storm` de meteorology et advected par le wind cell-level
  (qui est maintenant macro). Les trajectoires sont donc cohérentes avec
  l'atmosphère globale, ce qui est déjà un gros progrès.
- **Pas de pression macro** : seul le vent est partagé. La pression
  hPa de meteorology reste calculée depuis l'altitude. Pour le moment
  pas de feedback bidirectionnel pression macro ↔ vent macro.
- **Wildfire reçoit la MOYENNE** des vents sur les chunks cachés. Pour
  les feux de grande envergure, on perd l'information locale. À raffiner
  en passant un wind per-chunk si jamais wildfire en a besoin.

---

## Branchements futurs (audit Wave 18 restant)

| Levier | Module | Bénéfice |
|---|---|---|
| #3 | `ecology.py` | biome_shift_factor dynamique selon T anomaly |
| #4 | `marine.py` | bathymétrie + plateau continental + upwelling |
| #5 | `global_world.py` | une seule GenesisWorld partagée par toutes régions |
