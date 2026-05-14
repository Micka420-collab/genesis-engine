# SPRINT 2026-05-14 — Wave 10 geology (strates + minerais)

**Priorité attaquée**: ultra-réaliste sous-sol/strates/minerais pour
permettre aux agents de **miner des minerais réels** + construire des
maisons en matériaux réels (pierre, argile, bois) + alimenter
material_synthesis avec des éléments extraits.

**Statut**: ✅ livré
**Cible**: 36 minéraux + colonne stratigraphique par chunk + extraction
déterministe + bridge vers Wave 1/2 chemistry.

---

## `engine/mineral_catalog.py` (~580 LOC) — 36 minéraux réels

Catégorisés selon les 10 grandes familles minéralogiques (Mineralogy
Database mindat.org, USGS) :

| Catégorie | Exemples | Tech tier |
|---|---|---|
| **Native elements** (6) | or, argent, cuivre, soufre, graphite, diamant | 0-2 |
| **Oxydes** (5) | hématite, magnétite, bauxite, cassitérite, rutile | 1-3 |
| **Sulfures** (5) | chalcopyrite, galène, sphalérite, pyrite, cinabre | 1-2 |
| **Halides/sels** (3) | sel gemme, sylvite, gypse | 0-2 |
| **Carbonates** (2) | calcite, dolomie | 0-1 |
| **Silicates** (3) | quartz, feldspath, mica muscovite | 0-1 |
| **Roches ignées** (3) | granite, basalte, obsidienne | 0 |
| **Roches sédimentaires** (3) | calcaire, grès, schiste | 0 |
| **Roches métamorphiques** (3) | marbre, ardoise, gneiss | 1 |
| **Organiques** (3) | tourbe, charbon, schiste bitumineux | 0-3 |

Chaque `Mineral` porte :
- Formule chimique, densité (g/cm³), dureté Mohs
- `biome_affinity` (où il apparaît)
- `min_depth_m` / `max_depth_m` (fenêtre d'extraction)
- `elevation_bias` (+1 = montagnes, -1 = plaines)
- `rarity` (0 commun → 1 très rare)
- **`yields_per_kg_ore`** : kg d'éléments produits par kg d'ore (bridge
  vers Wave 1 chemistry). Ex : hematite Fe₂O₃ → 70 % Fe, 30 % O
- `tech_tier` (0 = ramassage Stone Age, 3 = mine industrielle)

---

## `engine/geology.py` (~410 LOC) — strates + extraction

### Génération stratigraphique réaliste

Pour chaque chunk, **colonne verticale 0-1000 m** avec 4-5 couches
selon le contexte :

```
Topsoil    0 →  1 m       shale         (clay + humus)
Regolith   1 →  5 m       sandstone     (weathered fragments)
Sediment   5 → 200 m      limestone/sandstone/shale (lowland only)
Bedrock  200 → 1000 m     granite/basalt (igneous baseline)
Deep    1000 → 3000 m     gneiss        (mountains only, > 1200 m)
```

Le choix du rock_type par couche dépend du biome :
- OCEAN, TUNDRA, HOT_DESERT → basalt baseline (volcanique)
- TEMPERATE/BOREAL_FOREST, GRASSLAND → granite + limestone sédimentaire
- Mountains → gneiss profond

### Ore deposits déterministes

`_select_ore_mix(rng, biome, elevation, depth_top, depth_bottom)` :
- Filtre les minéraux par biome_affinity + depth window
- Score par `elevation_bias` × `(1 - rarity)`
- Échantillonne **3-4 minéraux par couche** sans replacement
- Assigne fractions 0.001-0.20 (cap total 0.30 par couche)
- Reste = matrice inerte

**Exemple Léman (46.5°N, 6.6°E, lowland forest)** :
```
0-1m     shale         hematite 4.4% + granite 6.1%
1-5m     sandstone     hematite + basalt + calcite
5-200m   limestone     native_gold 0.48% + quartz + pyrite
200-1000 granite       sandstone + basalt + granite
```

### Extraction

```python
mine_at(sim, row, target_depth_m, kg_to_extract=5.0)
  → find_layer_at(depth)
  → extract kg × ore_mix[mineral] for each mineral
  → cap at MAX_EXTRACT_KG_PER_CALL=50 kg
  → cap at layer.remaining_mass_kg()
  → credit agent inv_metal / inv_stone selon mineral category
  → return {mineral_name → kg}
```

### Bridge Wave 1/2 chemistry

Chaque kg extrait se convertit en éléments via
`mineral.yields_per_kg_ore`. Exemple :

```
Mine 1 kg de feldspar (KAlSi3O8) →
  K: 0.14 kg, Al: 0.10 kg, Si: 0.30 kg, O: 0.46 kg
```

Ces éléments peuvent être fed directement dans
`material_synthesis.synthesize` pour produire des matériaux dérivés.

---

## Validation `p34_geology_smoke` **8/8 PASS**

```
[OK] step 1 — catalogue ≥ 30 minerals + biome ids ok        n=36
[OK] step 2 — strata column has ≥ 3 layers                  layers=4
[OK] step 3 — mine_at extracts ore                          {feldspar, slate, limestone}
[OK] step 3 — at least one mineral found in column
[OK] step 4 — agent inventory credited                      inv_metal=0.507 inv_stone=0.787
[OK] step 5 — element yields computed from ore              {K, Al, Si, O, Fe, Ca, C}
[OK] step 6 — ADR-0005 lists geology OK
[OK] step 7 — persistence round-trip preserves geology
```

Mining 1.3 kg de roche → 1.3 kg d'éléments répartis sur 7 éléments
différents (K, Al, Si, O, Fe, Ca, C) — directement consommables par
`material_synthesis.synthesize`.

---

## ADR-0005 → 15 modules requis taggés

| # | Module | Pipeline | Capability |
|---|---|---|---|
| 1 | earth_loader | L1 | paper-L1 |
| 2 | sim_lift | L2 | paper-L2 |
| 3 | realism | L4 | paper-L2 |
| 4 | physiology | L4 | paper-L2 |
| 5 | photosynthesis | L4 | paper-L2 |
| 6 | material_aging | L4 | paper-L1 |
| 7 | marine | L4 | paper-L2 |
| 8 | global_world | L4 | paper-L2 |
| 9 | plant_evolution | L4 | paper-L2 |
| 10 | meteorology | L4 | paper-L2 |
| 11 | animal_evolution | L4 | paper-L2 |
| 12 | agriculture | L4 | paper-L2 |
| 13 | writing | L4 | paper-L2 |
| 14 | polity | L4 | paper-L2 |
| **15** | **geology** (nouveau) | **L1 Earth-Seed** | **paper-L1** |

Geology est le 2e module L1 (Earth-Seed) après earth_loader — le
sous-sol est statique tout comme la topographie/biome.

---

## Boucle de rétroaction complète

```
Earth DEM + biome (Wave L1)
        ↓
chunk strata (Wave 10 NEW)
        ↓
agent mines → ore extracted (Wave 10 NEW)
        ↓ yields_per_kg_ore (Wave 1 chemistry)
elements available to agent
        ↓
material_synthesis.synthesize (Wave 1/2)
        ↓
new SynthesizedMaterial → MaterialRegistry
        ↓
material_aging tracks instance integrity (Wave 4)
        ↓
agent inscribes recipe on stone (Wave 9b writing)
        ↓
6000 ans plus tard, futurs lisent → mining + smithing intact
```

**C'est exactement la boucle pré-industrielle d'extraction minière
historique** : prospection → extraction → fonte → alliage → transmission.

---

## ActionKind.MINE ajouté

```python
class ActionKind(IntEnum):
    ...
    PLANT = 15
    HARVEST = 16
    MINE = 17     # NEW Wave 10
```

Hookup cognition pour autonomie agent : prévu en Wave 9d.b (analogue à
PLANT/HARVEST wiring).

---

## Non-régression

- `p18_capabilities_lint` → **15/15** OK
- `p23_persistence_roundtrip` → 7/7 PASS
- `p33_cognition_wiring_smoke` → 5/5 PASS

---

## Fichiers touchés

```
runtime/engine/mineral_catalog.py            (nouveau, ~580 LOC, 36 mineraux)
runtime/engine/geology.py                    (nouveau, ~410 LOC)
runtime/engine/agent.py                      (+2 LOC : ActionKind.MINE)
runtime/engine/dashboard.py                  (+12 LOC : endpoint)
runtime/engine/world_library.py              (+1 LOC : _PERSISTENT_MODULES)
runtime/engine/world_model_capabilities.py   (+1 LOC : _REQUIRED_MODULES)
runtime/scripts/p34_geology_smoke.py         (nouveau, ~190 LOC, 8/8 PASS)
docs/sprints/2026-05-14_PHASE22-GEOLOGY.md   (ce fichier)
NEXT-SPRINT.md                               (Wave 10 archivé)
```

---

## Wave 11 candidats

- **Cognition MINE wiring** : router ActionKind.MINE dans
  `apply_decision` via dispatcher (pattern agriculture/physiology).
  Décision quand : inv_metal/inv_stone bas + agent sur chunk avec
  ore en strate accessible.
- **Veins / lodes** : remplacer `ore_mix` uniforme par des veines
  étroites (Bernoulli sur une grille 3D) — plus de pression pour
  prospecter.
- **Construction** : étendre `construction.py` (Phase 3) pour
  consommer des éléments réels via les yields des minerais.
- **Smelting** : action SMELT qui consomme combustible (coal/peat) +
  ore + outil → matériel pur (Fe pur ← hematite + C).
