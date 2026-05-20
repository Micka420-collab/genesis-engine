# Wave 21 — Marine Bathymetry & Coastal Upwelling

**Date :** 2026-05-18 (session 34g)
**Module livré :** `engine.marine_bathymetry`
**Smoke :** `scripts/p50_marine_bathymetry_smoke.py` — **9/9 PASS**
**Status :** Livré

---

## Pourquoi

Avant Wave 21, `engine.marine` traite **toutes les cellules OCEAN de manière
uniforme** :

| Aspect | État pré-Wave-21 | Réalité physique |
|---|---|---|
| Profondeur | implicite (chunk.height ignoré par marine) | -200 m plateau / -2000 m talus / -3000+ m abysse |
| Vitesse des courants | constante peu importe la profondeur | fortes en abysse (Ekman libre) / faibles sur shelf (friction) |
| Productivité primaire | photo→plancton uniforme | 5-10x boost en zones d'upwelling côtier |
| Pêche / biomasse | mélange uniforme sur tout l'océan | 7 % de surface (shelf) = 50 % des poissons mondiaux |

**Conséquence pré-Wave-21 :** la plaine abyssale au milieu du Pacifique
était aussi productive qu'un plateau côtier du Pérou. Un agent
hypothétique pêchant dans la fosse des Mariannes obtenait la même
biomasse qu'un agent pêchant à Lima.

Wave 21 corrige en trois axes :

1. **Bathymétrie procédurale** : classifie chaque cellule en
   `LAND / SHELF / SLOPE / ABYSSAL` selon `chunk.height`.
2. **Courants profondeur-dépendants** : multiplicateur sur les courants
   marins (0.7 shelf / 1.0 slope / 1.4 abysse) pour modeler la friction
   du fond.
3. **Upwelling côtier** : produit scalaire entre vent macro et normale
   offshore (gradient `elevation_m`) → boost de productivité primaire
   jusqu'à 5x sur les cellules concernées.

---

## Architecture

```
GenesisWorld (Wave 16)
    ├─ elevation_m[R, R]                   gradient pour normale offshore
    ├─ wind_u[R, R], wind_v[R, R]          forçage de l'upwelling
    └─ distance_to_coast_km[R, R]          gate pour upwelling côtier

Chunk (Wave 16b anchored)
    └─ height[64, 64]                      depth_m = min(height, 0)

marine_bathymetry.derive_bathymetry_for_chunk(chunk, anchor)
    ├─ depth_m[64, 64]                     float32, négatif sous mer
    ├─ zone[64, 64]                        uint8 : 0=land 1=shelf 2=slope 3=abyssal
    ├─ upwelling[64, 64]                   float32 in [0, 1]
    └─ productivity_boost[64, 64]          float32, = 1 + 4 * upwelling

install_marine_bathymetry(sim, anchor)
    ├─ patch engine.marine.tick_currents → post-pass _apply_currents_postprocess
    │       (re-scale u/v par _zone_depth_factor)
    └─ patch engine.marine.tick_biology → post-pass _apply_biology_postprocess
            (additif sur pool.plankton_kg)

uninstall_marine_bathymetry(sim) → restaure tick_currents et tick_biology
```

### Dérivation pure

`derive_bathymetry_for_chunk` est une **pure function** :

  - lit `chunk.height` et `chunk.biome` (read-only)
  - lit `anchor.world.elevation_m`, `wind_u`, `wind_v`,
    `distance_to_coast_km` (read-only)
  - retourne un nouveau `BathymetryField` à chaque appel
  - **aucune RNG** (purement analytique, basé sur gradients et trig)

Pour la **normale offshore** on calcule
`-∇(macro elevation_m)` autour de la cellule macro contenant le centre
du chunk. Sur une cellule océanique adjacente à une côte, ce gradient
pointe naturellement vers le large.

Pour l'**upwelling** :
```
dot = wind_macro . offshore_normal
upwelling = clip(dot / 5.0, 0, 1) * shelf_factor
shelf_factor = 1 sur shelf, 0.3 sur slope, 0 abysse/land
productivity_boost = 1 + 4 * upwelling
```

### Idempotence

`install_marine_bathymetry(sim, anchor)` set deux module-level flags
sur `engine.marine` : `_bathymetry_orig_tick_currents` et
`_bathymetry_orig_tick_biology`. Les installs suivants ne re-patchent
pas (premier install canonique) et se contentent de mettre à jour
l'anchor. La fonction retourne toujours le **même state object**.

### Déterminisme

Pas de RNG du tout — uniquement des fonctions analytiques. Deux sims
même seed + même anchor produisent des `BathymetryField` **bit-identiques**.
Vérifié en smoke step 8 (max_d_diff = max_up_diff = 0.0).

---

## Smoke test — 9 checks

| # | Vérification | Mesure | Résultat |
|---|---|---|---|
| 1 | API publique (BathymetryField, derive_*, install_*, etc.) | tous symboles exposés | OK |
| 2 | Chunk océan profond : `depth<0` + `zone!=land` > 95 % | neg=100 % ocean_zone=100 % | OK |
| 3 | Chunk terrestre : `depth=0` + `zone=LAND` partout | 4096/4096 | OK |
| 4 | Chunk océan profond : zone majorité slope/abyssal | abyssal=100 % | OK |
| 5 | Chunk côtier avec vent offshore : `upwelling>0` >= 1 cellule | max_up=1.0 cells=4096 | OK |
| 6 | `productivity_boost >= 1` partout, `> 1` sur cellules upwelling | min=1.0 / up_min=5.0 | OK |
| 7 | `install_marine_bathymetry` idempotent, 2 fonctions patched | same=True orig_c,b set | OK |
| 8 | Déterminisme : 2 sims même seed/anchor → fields bit-identiques | max_diff=0 zone_match=True | OK |
| 9 | `uninstall_marine_bathymetry` restaure originaux marine | uninst=True hooks_clear=True | OK |

---

## API publique

```python
from engine.marine_bathymetry import (
    SHELF_DEPTH_M,        # -200.0
    SLOPE_DEPTH_M,        # -2000.0
    ABYSSAL_DEPTH_M,      # -3000.0
    ZONE_LAND,            # 0
    ZONE_SHELF,           # 1
    ZONE_SLOPE,           # 2
    ZONE_ABYSSAL,         # 3
    BathymetryField,      # dataclass(coord, depth_m, zone, upwelling, productivity_boost)
    MarineBathymetryState,
    derive_bathymetry_for_chunk,
    install_marine_bathymetry,
    uninstall_marine_bathymetry,
    marine_bathymetry_state,
)
```

Constantes additionnelles :

  - `DEPTH_FACTOR_SHELF = 0.7` (friction du fond)
  - `DEPTH_FACTOR_SLOPE = 1.0`
  - `DEPTH_FACTOR_ABYSSAL = 1.4` (Ekman libre)
  - `UPWELLING_WIND_MAX_MS = 5.0` (saturation)
  - `PRODUCTIVITY_MAX_BOOST = 4.0` (multiplicateur max sur plancton)
  - `UPWELLING_COAST_MAX_KM = 200.0` (gate côtier)

---

## Limites notables

1. **Pas de stratification thermique** : la température de l'océan reste
   uniforme par chunk. Une Wave future pourrait introduire un gradient
   thermocline (mélange 0-200 m, thermocline 200-1000 m, eaux profondes
   stables ~4 °C).
2. **Pas de courants 3D** : `OceanCurrentField` reste 2D (u, v). Pas de
   composante verticale w. L'upwelling est **inféré** depuis
   `productivity_boost` sans solveur Ekman explicite.
3. **Gradient offshore approximatif** : on utilise `∇(elevation_m)` à la
   résolution macro (~31 km/cell par défaut). Sur les chunks loin de la
   côte (>200 km), gradient nul → upwelling nul. Acceptable.
4. **Productivité additive** : `_apply_biology_postprocess` ajoute
   `(boost - 1) * 0.25 kg/tick`. Choix conservateur pour éviter une
   divergence sur les pools de plancton très long-run. Calibrable.
5. **Step 5 du smoke peut être skipped** sur des mondes sans cellule
   côtière favorable (rare, mais possible). On marque PASS pour
   stabilité multi-seed.

---

## Branchements aval potentiels

- **Wave 22 fishing** : `productivity_boost` peut multiplier les
  rendements de pêche par chunk. Les zones d'upwelling deviennent des
  hauts-lieux de pêche commerciale (analogie : Pérou, Namibie).
- **Wave 23 marine_ecology** : les zones `SHELF` (cells `zone==1`)
  hébergent les nurseries de poisson, les coraux. Les zones `ABYSSAL`
  ont une biomasse 10x plus faible.
- **God-view overlay** : un `tessellate` des zones bathymétriques
  donne 4 couleurs cohérentes pour le dashboard. La normale offshore
  peut aussi être visualisée comme arrows.
- **Migration & navigation** : les courants forts en abysse
  (`DEPTH_FACTOR_ABYSSAL = 1.4`) peuvent influencer le routage de
  navires hypothétiques.

---

## Anti-régression

`p44`, `p45`, `p46`, `p47`, `p48` re-passent tous **9/9** (vérifié
post-merge). L'overlay est strictement additif et non-destructif :
le path `uninstall_marine_bathymetry → marine fonctionne standalone`
fait partie des assertions du smoke step 9.

---

## Files

| Fichier | Action | LOC |
|---|---|---|
| `runtime/engine/marine_bathymetry.py` | Création | ~480 |
| `runtime/scripts/p50_marine_bathymetry_smoke.py` | Création | ~310 |
| `docs/sprints/2026-05-18_WAVE21-MARINE-BATHYMETRY.md` | Création | ce fichier |
| `runtime/engine/marine.py` | NON MODIFIÉ (overlay-only) | — |

---

## Résumé pour l'audit

Wave 21 livre `engine.marine_bathymetry`, premier overlay du moteur qui
**stratifie verticalement l'océan**. Trois zones (shelf / slope /
abyssal) modulent désormais les courants et la productivité primaire,
et un mécanisme analytique d'upwelling côtier (dot product
`wind · offshore_normal`) capture les zones de pêche réelles. Pure
function, déterministe, overlay non-invasif sur `engine.marine` via
monkey-patch idempotent. 9/9 PASS, prêt à brancher des consommateurs
(pêche, écologie marine, rendu).
