# SPRINT 2026-05-14 — Wave 6 plant evolution (catalogue + émergence + divergence IA)

**Priorité attaquée**: ajouter toutes les plantes existantes sur Terre,
avec leur vraie histoire phylogénétique préhistorique, mais avec
**divergences possibles** selon les choix des IA et l'évolution du CO2
/ O2 / climat.

**Statut**: ✅ livré
**Cible**: 35+ clades végétaux scientifiquement calibrés, conditions
d'émergence/extinction réalistes, spéciation aléatoire déterministe.

---

## Livré — deux modules + couplage photosynthèse

### `engine/plant_catalog.py` (~530 LOC) — 39 clades réels

Phylogénie d'après APG IV (2016) et tolweb.org, ages d'apparition
d'après Knoll 2008, Niklas 2016, Magallón 2015. Chaque entrée
`PlantClade` immuable porte :

- **Identité** : `name`, `common_name` (en français), `kingdom` (7 royaumes)
- **Phylogénie** : `parent_clade` (vraie filiation), `first_appearance_ma`
- **Photosynthèse** : `pathway` (C3 / C4 / CAM)
- **Enveloppe climatique** : `temp_min`/`temp_opt`/`temp_max`, `water_min`,
  `min_oxygen_pct`, `max_co2_ppm`
- **Affinité biome** (frozenset)
- **Traits** : `height_m`, `edible_kcal_per_kg`, `wood_yield_kg_per_kgbio`,
  `growth_kg_per_day_opt`

Les 39 clades couvrent **toute l'histoire évolutive végétale** :

| Royaume | Clades | Apparition |
|---|---|---|
| Prokaryotes | cyanobactéries | 3500 Ma |
| Algues | green / red / brown / diatomées | 1400 → 250 Ma |
| Bryophytes | hépatiques, anthocérotes, sphaigne, mousses | 470 → 300 Ma |
| Ptéridophytes | lycopodes, sélaginelles, prêles, **fougères** | 410 → 360 Ma |
| Gymnospermes | cycadales, ginkgo, pinacées, cyprès, podocarpes, gnétales | 300 → 145 Ma |
| Monocots | magnolias, graminées C3+C4, palmiers, lis, orchidées | 140 → 30 Ma |
| Dicots | chênes, érables, légumineuses, rosacées, composées, lamiacées, brassicacées, solanacées, cactus, crassulacées, éricacées, renonculacées, cucurbitacées, apiacées | 140 → 35 Ma |

**Point-clé** : les **graminées C4** (maïs, sorgho, canne) ont
`max_co2_ppm = 600` parce qu'elles **ont réellement évolué** quand le
CO2 chuta de 1000 ppm à 280 ppm il y a 30 Ma. Dans le moteur, si les
agents émettent du CO2 jusqu'à >700 ppm, **les graminées C4 meurent
émergemment**.

### `engine/plant_evolution.py` (~530 LOC) — moteur d'évolution

**État** : `PlantEvolutionState` attaché à `sim._plant_state` :

- `chunk_vegetation : Dict[coord → ChunkVegetation]` — biomasse kg par
  clade par chunk
- `available_clades : Set[str]` — clades émergents globalement
- `extinct_clades : Set[str]` — clades disparus globalement
- `synthetic_clades : Dict[str, PlantClade]` — variants spéciés mutants
- `oxygen_kg_delta` — accumulation O2 atmosphérique (cyanobactéries
  pompent l'oxygène)
- `speciation_log : List[SpeciationEvent]`

**Deux modes de boot** :

1. **`mode="modern"`** (défaut) — toutes les 39 clades seedées dans
   les chunks compatibles avec leur affinité biome. C'est "Terre
   Holocène". Divergence par changements environnementaux.
2. **`mode="ancient"`** — seulement cyanobactéries seedées. O2 monte
   progressivement par photosynthèse, les autres clades émergent
   quand leur `min_oxygen_pct` est atteint + parent présent. C'est
   le **replay contrefactuel de l'évolution végétale terrestre**.

**Fitness** = bell-curve(température) × seuil(eau) × cutoff(O2) ×
cutoff(CO2) × affinité_biome.

**Croissance logistique** : `biomass *= (1 - biomass/capacity)` —
saturation à 5000 kg/chunk.

**Spéciation** : tout clade présent en continu pendant
`SPECIATION_INCUBATION_TICKS` (30 sim-jours) peut muter avec proba
`1/(30 jours)` par tick, en perturbant ±10% temp_opt, water_min,
max_co2_ppm, growth. Le variant `oaks_mut_1`, `oaks_mut_2`... rejoint
`available_clades` et peut lui-même spécier.

**Extinction** : clade non vu globalement pendant
`EXTINCTION_WAIT_TICKS` (30 sim-jours) → marqué `extinct`. Reapparition
possible via migration inter-régions (Phase 15).

### Couplage photosynthèse

Chaque chunk avec biomasse mesurable reçoit un attribut
`chunk._plant_pathway_mix = (C3, C4, CAM)` pondéré par les clades
réellement présents. `engine.photosynthesis.compute_chunk_gpp` lit cet
attribut en priorité sur `BIOME_PATHWAY_MIX`. **L'émergence
contrefactuelle de plantes différentes modifie donc l'output Farquhar
mesurable**, qui modifie `chunk.food_kcal`, qui modifie ce que les
agents trouvent.

---

## Validation — `p27_plant_evolution_smoke` 13/13 PASS

```
[OK] step 1 — biome ids in sync
[OK] step 1 — phylogeny acyclic               no cycles
[OK] step 1 — catalogue ≥ 35 clades           n=39
[OK] step 2 — pinaceae @ -60°C → fitness 0    f=0.0000
[OK] step 2 — cycads at 10% O2 → fitness 0    f=0.0000
[OK] step 2 — oaks in temp forest → f > 0.5   f=1.0000
[OK] step 3 — modern: 39 clades seeded
[OK] step 3 — modern: positive global biomass biomass=160 169 kg
[OK] step 3 — modern: ≥ 1 clade in top        top=8
[OK] step 4 — chunk._plant_pathway_mix written mix=(0.999, 5.4e-6, 4e-6)
[OK] step 5 — C4 grass @ 800 ppm CO2 → f=0    normal=1.000 high=0.000
[OK] step 6 — ancient mode starts cyanobact   initial={'cyanobacteria'}
[OK] step 6 — ancient: O2 climbs              O2=0.2910%
[OK] step 7 — ADR-0005 plant_evolution OK
[OK] step 8 — determinism                     5a4e59ce4b0c30c9
```

**Résultat émergent** :
- Mode `modern`, Léman 1.5km, 100 ticks : **160 tonnes biomasse**,
  8 clades dominantes (top : pinacées, fougères, oaks selon biome).
- Mode `ancient`, 200 ticks : O2 atmosphérique passe de 0.1% → 0.29%
  par activité photosynthétique des cyanobactéries seules. À ce
  rythme, les bryophytes (min_O2 5%) émergeraient après ~3000 ticks.

---

## Non-régression — tout Wave 1-5 et P1/P3/P5 PASS

- `p18_capabilities_lint` → **9/9 modules requis taggés** OK
- `p21_photosynthesis_smoke` → 7/7 PASS (pathway override fonctionne)
- `p23_persistence_roundtrip` → 7/7 PASS (plant_evolution persiste)
- `p25_marine_smoke` → 6/6 PASS

ADR-0005 mapping table maintenant :

| Module | Pipeline | Capability |
|---|---|---|
| earth_loader | L1 | paper-L1 Predictor |
| sim_lift | L2 | paper-L2 Simulator |
| realism | L4 | paper-L2 Simulator |
| physiology | L4 | paper-L2 Simulator |
| photosynthesis | L4 | paper-L2 Simulator |
| material_aging | L4 | paper-L1 Predictor |
| marine | L4 | paper-L2 Simulator |
| global_world | L4 | paper-L2 Simulator |
| **plant_evolution** (nouveau) | L4 | paper-L2 Simulator |

---

## Comment l'IA fait diverger l'évolution végétale

Trois leviers concrets que les agents (ou le god avatar) peuvent
actionner :

1. **CO2 atmosphérique** — émissions par construction, cuisson, feu de
   bois. `ecology.atmosphere.emit()` augmente `co2_ppm`. Au-dessus de
   600 ppm, **graminées C4 meurent globalement** → savanes
   disparaissent, dominance C3 (légumineuses, broad-leaf).
2. **Déforestation** — `chunk.wood` détruit par les agents (foraging,
   construction). La biomasse arborée diminue → moins de
   photosynthèse → O2 cesse de monter → plafond évolutif.
3. **Pratique du feu** — savanes favorisent les graminées C4 ; sans
   feu, les forêts envahissent. Cette boucle est implicite dans la
   sélection par fitness.

Possible **runs comparatifs** :
- Run A : agents pacifiques végétariens → équilibre forêt + prairie
- Run B : agents agriculteurs intensifs → C4 à 600 ppm domine, puis
  effondre quand CO2 grimpe
- Run C : civilisation industrielle → O2 plafonne, ferns + gymnospermes
  régressent, dicots résistent
- Run D : `mode="ancient"` 100K ticks → replay évolutif terrestre

Chacun produit une **bibliothèque de matériaux et de calories
différente**, donc une **trajectoire technologique différente**. C'est
exactement la "contingence historique falsifiable" de H1.

---

## Fichiers touchés

```
runtime/engine/plant_catalog.py             (nouveau, ~530 LOC, 39 clades)
runtime/engine/plant_evolution.py           (nouveau, ~530 LOC)
runtime/engine/photosynthesis.py            (+15 LOC : pathway override)
runtime/engine/world_library.py             (+1 LOC : _PERSISTENT_MODULES)
runtime/engine/world_model_capabilities.py  (+1 LOC : _REQUIRED_MODULES)
runtime/engine/dashboard.py                 (+12 LOC : endpoint + import)
runtime/scripts/p27_plant_evolution_smoke.py (nouveau, ~225 LOC, 13/13)
docs/sprints/2026-05-14_PHASE16-PLANT-EVOLUTION.md (ce fichier)
NEXT-SPRINT.md                              (Wave 6 archivé)
```

---

## Pistes Wave 7

- **Animals catalogue** : ~50 espèces d'animaux réels avec aire de
  répartition, régime alimentaire, prédation. Câblé sur `realism.wildlife`.
- **Plant-animal coevolution** : pollinisateurs ↔ angiospermes,
  herbivores ↔ graminées, frugivores ↔ rosacées.
- **Cultivation par les agents** : `ActionKind.PLANT` + `ActionKind.HARVEST`.
  Les agents *choisissent* quels clades semer. Pression de sélection
  artificielle.
- **HUD widget plant_evolution** : top clades, oxygen %, biomass totale,
  recent speciations.
- **Overlay `plants`** dans le render : colorer par royaume dominant.
