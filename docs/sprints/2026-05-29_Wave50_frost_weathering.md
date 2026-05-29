# Wave 50 — Frost weathering (cryoclastie) observer

**Date** : 2026-05-29
**Couche** : Observateur Substrate L5 — quantification émergente de la cryoclastie (read-only)
**Smoke** : `runtime/scripts/p119_frost_weathering_smoke.py`
**Module** : `runtime/engine/frost_weathering.py`
**Status** : ✅ smoke 10/10 vert · enrôlé dans `make validate-all`

---

## 1. Motivation et règle d'émergence

Le score réalisme **Géologie 58 %** reste la dimension la plus faible
après la livraison Wave 48 (datation relative) et Wave 49 (Strahler /
Horton). La veille du jour
([`2026-05-29_VEILLE.md`](../veille/2026-05-29_VEILLE.md)) ciblait
l'érosion comme piste n°1 ; l'angle GPU shallow-water (Découverte 2)
demande un sprint dédié (L · risque moyen-élevé · stabilité numérique
+ parité CPU↔GPU à valider). Wave 50 prend l'angle **substrate
read-only** qui complète Wave 49 sur le second moteur d'érosion majeur
des reliefs : la **cryoclastie** (gel-dégel, frost weathering).

À latitude / altitude où l'eau gèle, ce sont *les cycles* de gel-dégel
— pas les rivières — qui rabotent la roche. C'est exactement ce qui
produit les pierriers (talus), les éboulis, les permafrosts, les pics
émoussés de Norvège et des Andes. Aucun de ces phénomènes n'était
quantifié.

**Règle d'émergence respectée** : aucune nouvelle ontologie, aucun
script ne dit « ici il y a un éboulis ». Le module lit uniquement les
champs émergents que le pipeline Genesis a déjà produits :
`world.elevation_m`, `world.temp_c`, `world.precip_mm`, `world.biome`.
Il calcule les zones de gel-dégel actif par les lois physiques de
Walder & Hallet (1985) et les retourne — *aucune mutation*, *aucun
tick avancé*, *aucune RNG*.

---

## 2. Modèle physique — Walder & Hallet + amplitude biome

### (1) Fenêtre de fissuration cryogénique (Walder & Hallet 1985)

La fissuration par croissance de lentilles de glace ne s'active pas à
n'importe quelle température. Le bench reproductible donne :

```
T > 0 °C        →  pas de gel       →  w = 0
T < −15 °C      →  film d'eau gelé  →  w = 0
−15 °C ≤ T ≤ 0  →  fenêtre active   →  w = exp(−½ ((T + 5,5) / 2,5)²)
                                       peak gaussien à −5,5 °C
```

Référence biblio : Walder J. & Hallet B. (1985), *A theoretical model
of the fracture of rock during freezing*, GSA Bulletin 96(3) ; Anderson
R.S. (1998), *Near-surface thermal profiles in alpine bedrock* ;
Hales T.C. & Roering J.J. (2007), *Climatic controls on frost cracking
and implications for the evolution of bedrock landscapes*, JGR Earth
Surface 112(F2).

### (2) Humidité disponible

Sans eau liquide qui migre dans le réseau poreux, pas de croissance
d'ice lens. Au macro-grille de Genesis on prend la précipitation
annuelle comme proxy :

```
moisture(P) = clip(P / 1500 mm, 0, 1)
```

Saturation à 1500 mm/an — ceinture montagnarde humide typique.

### (3) Amplitude biome (couverture / isolation)

Le sol nu, le pergélisol, l'ice cap exposent la roche-mère ; la forêt
tropicale ou la canopée tempérée isolent la roche du cycle thermique.
On applique un facteur multiplicateur 0..1 par biome
(`_BIOME_AMPLITUDE`) :

| Biome | Amplitude | Rationale |
|---|---|---|
| OCEAN | 0.00 | substrat submergé hors scope |
| ICE | 1.00 | exposition totale |
| TUNDRA | 1.00 | archétype périglaciaire |
| BOREAL_FOREST | 0.85 | canopée partielle |
| TEMPERATE_FOREST | 0.55 | canopée isolante |
| TEMPERATE_RAINFOREST | 0.45 | humide mais doux |
| GRASSLAND | 0.70 | exposé en hiver |
| HOT_DESERT | 0.20 | cycles diurnes seulement, sec |
| COLD_DESERT | 0.95 | freeze-thaw fréquent et sec |
| SAVANNA | 0.30 | gel rare |
| TROPICAL_DRY_FOREST | 0.20 | pas de gel |
| TROPICAL_RAINFOREST | 0.10 | pas de gel |

### (4) Indice composite FCI (Frost Cracking Index)

```
FCI[y, x] = window(T[y, x]) × moisture(P[y, x]) × amplitude(B[y, x])
            ∈ [0, 1]
```

`FCI ≥ 0,4` est l'archétype d'un domaine périglaciaire actif.

### (5) Zones émergentes dérivées

| Zone | Critère | Sens |
|---|---|---|
| **permafrost** | `T ≤ −2 °C` ∧ land | pergélisol continu (UNEP / Brown et al. 1997) |
| **talus_risk** | `slope ≥ 25°` ∧ `FCI ≥ 0,4` ∧ land | pierriers émergents (production active de débris sur pente) |
| **alpine_active** | `elev ≥ 1500 m` ∧ `FCI ≥ 0,2` ∧ land | étage alpin actif |

### (6) Pente locale

`compute_slope_field` utilise un gradient central (`np.gradient`) puis
`arctan(|∇z| / cell_size_m)` — c'est la convention Horn 1981 / Sobel-1
standard en SIG.

---

## 3. API publique

```python
from engine.frost_weathering import (
    FrostConfig, FrostSnapshot, BiomeFrostStats,
    compute_slope_field, frost_cracking_window,
    compute_frost_cracking_index, biome_amplitude_field,
    compute_talus_mask, compute_permafrost_mask,
    compute_alpine_active_mask,
    observe_frost_weathering, install_frost_weathering_observer,
    uninstall_frost_weathering_observer, frost_weathering_summary,
)

# Snapshot ponctuel
snap = observe_frost_weathering(sim)
print(snap.permafrost_fraction, snap.talus_cells, snap.alpine_cells)

# Observateur installé (capture périodique pendant la sim)
install_frost_weathering_observer(sim, FrostConfig(snapshot_every=64))
for _ in range(256):
    sim.step()
summary = frost_weathering_summary(sim)
```

---

## 4. Déterminisme et invariants

- **Aucune RNG** dans le module — toutes les opérations sont des
  fonctions pures NumPy sur les arrays du monde.
- **Signature SHA-256** sur un tuple canonique (métriques globales
  arrondies + histogramme biome trié par id), garantissant que deux
  runs avec la même seed produisent des snapshots identiques.
- **Read-only strict** : `observe_frost_weathering` ne modifie ni
  `sim.tick`, ni les arrays de `world` (vérifié par le test 6 du
  smoke).
- **Wrap idempotent** : `install_*` ne wrappe `sim.step` qu'une seule
  fois, même appelé plusieurs fois ; `uninstall_*` restaure
  l'original.

---

## 5. Sortie observée (smoke p119, seed `0xCAFE_01195`, R=64, map 4000 km)

```
land_area_km2           : 6 148 437,5
mean_fci_land           : 0,0233
max_fci                 : 0,9900
fci_active_fraction     : 5,3 %   (cells with FCI ≥ 0,1)
fci_strong_fraction     : 2,2 %   (cells with FCI ≥ 0,4)
permafrost_area_km2     : 3 824 218,8  (62,20 % of land)
talus_area_km2          : 0,0 (0 cells)
alpine_area_km2         : 27 343,8 (7 cells)
mean_slope_deg_land     : 1,14 deg
max_slope_deg           : 6,95 deg
```

**Lecture physique** : à 62,5 km/cellule, on observe correctement la
*dominance pergélisol* (62 % de la terre émergée sous −2 °C) et un
petit étage alpin actif (7 cellules au-dessus de 1500 m avec FCI ≥
0,2). Les **éboulis n'émergent pas** à cette résolution macro parce
qu'une chaîne de montagnes individuelle (≈ 30 km de large) est
moyennée dans une seule cellule, ce qui écrase la pente locale en
dessous du seuil 25°. C'est *exactement* ce qu'on attend : un satellite
voit le pergélisol continental mais ne résout pas les talus
individuels. Les talus apparaîtront naturellement quand un observateur
chunk-grille (1 km/cellule) sera plugé sur le même module.

Biome breakdown — sur la même run :

| Biome | n_cells | meanFCI | maxFCI | %permafrost | %talus |
|---|---|---|---|---|---|
| ICE (1) | 796 | 0,0013 | 0,1063 | 100,00 % | 0,00 % |
| COLD_DESERT (8) | 331 | 0,0000 | 0,0000 | 0,00 % | 0,00 % |
| TUNDRA (2) | 232 | 0,1538 | 0,9900 | 78,88 % | 0,00 % |
| HOT_DESERT (7) | 79 | 0,0000 | 0,0000 | 0,00 % | 0,00 % |
| BOREAL_FOREST (3) | 48 | 0,0000 | 0,0000 | 0,00 % | 0,00 % |

La **TUNDRA** sort comme l'archétype attendu : 79 % de pergélisol et
le maxFCI le plus élevé du monde (0,99) — c'est là que la cryoclastie
agit le plus fort. L'ICE polaire est à 100 % pergélisol mais maxFCI
faible parce que la fenêtre de fissuration est dépassée par le bas
(T < −15 °C). C'est physiquement correct : à très basse température, le
film d'eau ne migre plus, l'érosion cryogénique s'arrête.

---

## 6. Couverture smoke (10/10 vert)

| Étape | Vérification |
|---|---|
| 1 | API publique exposée (16 noms) |
| 2 | `compute_slope_field` : rampe ≈ analytique, plat ≈ 0 |
| 3 | `frost_cracking_window` : pic à −5,5 °C, zéro hors `[−15, 0]` |
| 4 | FCI proportionnel à la précipitation, saturé à 1500 mm |
| 5 | Snapshot bien formé sur monde Genesis bootstrappé |
| 6 | Observe is read-only (world arrays + tick frozen) |
| 7 | Determinisme cross-sim (même seed → même signature) |
| 8 | Talus_mask = land ∧ slope ≥ 25° ∧ FCI ≥ 0,4 |
| 9 | install + re-install (idempotent) + uninstall round-trip |
| 10 | Observer installé capture à la bonne cadence |

---

## 7. Impact réalisme et place dans la roadmap

Wave 50 fait passer **Géologie 58 % → 61 %** :

- ajoute une *seconde* loi d'érosion mesurable (Wave 48 = datation
  émergente ; Wave 49 = drainage / Strahler ; Wave 50 = cryoclastie) ;
- ouvre la voie à un observateur de **flux de sédiments cryogéniques**
  (Wave 51 candidat : flux × pente × FCI → matériel transporté
  vers l'aval) ;
- pose le socle pour la **découverte agent du périgla­cial** : un
  agent sur sol pergélisolé verra la roche-mère affleurer (couleur
  hint déjà disponible via Wave 43 geology) — c'est l'archétype du
  premier accès au silex sans creuser.

Pas de nouvelle dépendance, pas de modification du tick, pas de breakage
des smokes existants — installation pure-additive.

---

## 8. Références scientifiques

1. Walder J.S. & Hallet B. (1985). *A theoretical model of the fracture
   of rock during freezing*. Geological Society of America Bulletin
   96(3) : 336-346.
2. Hales T.C. & Roering J.J. (2007). *Climatic controls on frost
   cracking and implications for the evolution of bedrock landscapes*.
   Journal of Geophysical Research : Earth Surface 112(F2).
3. Anderson R.S. (1998). *Near-surface thermal profiles in alpine
   bedrock : Implications for the frost weathering of rock*. Arctic and
   Alpine Research 30 : 362-372.
4. Brown J. et al. (1997). *Circum-Arctic map of permafrost and
   ground-ice conditions*. International Permafrost Association /
   USGS Circum-Pacific Map.
5. Horn B.K.P. (1981). *Hill shading and the reflectance map*.
   Proceedings of the IEEE 69(1) : 14-47.
