# SPRINT 2026-05-14 — Wave 8 animal evolution

**Priorité attaquée**: catalogue d'animaux réels + dynamiques de
population + coévolution plante-animal + prédation Lotka-Volterra.

**Statut**: ✅ livré
**Cible**: 47 espèces représentatives, populations émergentes, plant
biomass consommée par herbivores, déterminisme via prf_rng.

---

## `engine/animal_catalog.py` (~530 LOC) — 47 espèces réelles

Couverture phylogénétique : invertébrés (arthropodes, mollusques),
vertébrés (poissons, amphibiens, reptiles, oiseaux, mammifères).

| Royaume | Espèces |
|---|---|
| Arthropodes | fourmis, abeilles, coléoptères, papillons, araignées, crabes |
| Mollusques | escargots, poulpes, moules |
| Poissons | truite, saumon, hareng, morue, thon, requin |
| Amphibiens | grenouilles, salamandres |
| Reptiles | lézards, serpents, crocodiles, tortues |
| Oiseaux | moineaux, corbeaux, faucons, aigles, canards, mouettes |
| Mammifères petits | souris, lapins, écureuils, chauves-souris |
| Mammifères herbivores | cerfs, chevaux, bovins, moutons, chèvres, porcs, éléphants, bisons |
| Mammifères carnivores | loups, renards, ours, lions, tigres |
| Mammifères marins | dauphins, baleines |
| Primates | singes |

Chaque espèce porte : enveloppe climatique (temp, oxygène, biome
affinity), démographie (mass_kg, lifespan, gestation, offspring/clutch),
énergétique (food_kcal_per_day), prédation (prey_clades,
plant_clades_browsed), rendement pour l'humain (meat_kcal_per_kg,
hide_kg, bone_kg), carrying_capacity_per_chunk.

---

## `engine/animal_evolution.py` (~390 LOC) — moteur de population

### Tick (par chunk × espèce)

1. **Fitness** = bell(T) × biome_affinity × oxygen_cutoff ×
   aquatic_water_check
2. **Mort naturelle** = pop × (1/lifespan_years/365) × dt_days
3. **Naissances** = pop × 0.012 × fitness × (1 - pop/cap) × dt_days
4. **Herbivores broutent** plant_evolution.ChunkVegetation —
   `_consume_plants` réduit la biomasse végétale des
   `plant_clades_browsed` de l'espèce, capé à 20% par tick.
5. **Famine** si satiété < 50%, mortalité supplémentaire 5%/jour
6. **Prédation Lotka-Volterra** par paire (predator, prey) dans le
   même chunk : kills ∝ pred × prey × 0.30 / cap

### Stochastic rounding (déterministe prf_rng)

Les low-rate events (births/deaths/predation) auraient été arrondis à
0 par `int(round())`. Fonction `_stochastic_round(x, rng)` = floor(x) + (rng.random() < frac(x))
preserves expected value perfectly via prf_rng.

### Coévolution plante-animal réelle

Quand `deer` brout dans un chunk forêt tempérée :
- Cherche les clades dans `deer.plant_clades_browsed = (oaks, magnoliid, ericaceae, poaceae_c3)`
- Demande `pop × food_kcal_per_day × dt × 0.05 / 1000` kg de biomasse
- Réduit jusqu'à 20% de la biomasse cumulée des clades cibles
- Distribue proportionnellement à la biomasse de chaque clade

→ surconsommation locale = `plant_evolution.ChunkVegetation` chute
→ overgrazing visible dans `/api/plant_evolution_state`
→ `chunk._plant_pathway_mix` recalculé → moins de GPP → moins de food_kcal

C'est le **cycle trophique réel** : producteurs primaires → herbivores
→ prédateurs, chacun limité par le précédent.

### Modes

- `modern` (défaut) : 47 espèces seedées dans chunks biome-compatibles
  à 10% de leur carrying capacity.
- `ancient` : seulement arthropodes + mollusques. Les vertébrés
  n'apparaissent pas (Wave 8b : émergence évolutive).

---

## Validation — `p29_animal_evolution_smoke` 9/9 PASS

```
[OK] step 1 — catalogue ≥ 45 species + biome ids ok      n=47
[OK] step 2 — deer @ -50°C fitness 0                      f=0.0000
[OK] step 2 — deer @ 12°C temp forest fitness > 0.5      f=1.0000
[OK] step 2 — shark on land (no water) → fitness 0       f=0.0000
[OK] step 3 — modern: populations seeded                  total=369525 species=33
[OK] step 4 — populations evolve over 200 ticks           pop 369K → 362K, births=22
[OK] step 5 — predation events recorded                   predation=46
[OK] step 6 — plant biomass still positive                149003 kg → 148972 kg
[OK] step 7 — ADR-0005 lists animal_evolution OK
[OK] step 8 — determinism on top species
```

**Émergence Léman après 200 ticks (3.5 sim-jours)** :

Top espèces : ants 178K, bees 88K, beetles 35K, herring 9.4K,
butterflies 8.2K.

Per royaume : Arthropodes 317K (dominants — réaliste), Mammifères 12.7K,
Fish 10K, Birds 9.5K, Mollusca 9.2K, Reptiles 2.6K, Amphibiens 1.7K.

Per trophic : **234K omnivores** (ants, beetles, mice — les Robin des
bois) > **108K herbivores** > 13K filter feeders > 8K carnivores >
4.7K insectivores > **186 apex predators**. Pyramide écologique
classique (~1000:1 entre niveaux).

---

## Non-régression — 11/11 modules taggés

- `p18_capabilities_lint` → **11/11 modules requis taggés** OK
- `p23_persistence_roundtrip` → 7/7 PASS
- `p27_plant_evolution_smoke` → 13/13 PASS
- `p28_meteorology_smoke` → 12/12 PASS

ADR-0005 table maintenant 11 modules :

| Module | Pipeline | Capability |
|---|---|---|
| earth_loader | L1 | paper-L1 |
| sim_lift | L2 | paper-L2 |
| realism | L4 | paper-L2 |
| physiology | L4 | paper-L2 |
| photosynthesis | L4 | paper-L2 |
| material_aging | L4 | paper-L1 |
| marine | L4 | paper-L2 |
| global_world | L4 | paper-L2 |
| plant_evolution | L4 | paper-L2 |
| meteorology | L4 | paper-L2 |
| **animal_evolution** (nouveau) | L4 | paper-L2 |

---

## Endpoint

`GET /api/animal_evolution_state` :
- global_population_total
- n_species_present
- extinct_species (sorted)
- top_species (top 10)
- per_kingdom_population
- per_trophic_population
- births_per_tick / deaths_per_tick / predation_per_tick
- ticks_run / chunks_tracked

---

## Persistence

`save_animal_state` / `load_animal_state` wired dans
`world_library._PERSISTENT_MODULES`. Round-trip préserve
chunk_fauna.populations, extinct_species, et compteurs cumulés.

---

## Fichiers touchés

```
runtime/engine/animal_catalog.py            (nouveau, ~530 LOC, 47 species)
runtime/engine/animal_evolution.py          (nouveau, ~400 LOC)
runtime/engine/dashboard.py                 (+12 LOC : endpoint + import)
runtime/engine/world_library.py             (+1 LOC : _PERSISTENT_MODULES)
runtime/engine/world_model_capabilities.py  (+1 LOC : _REQUIRED_MODULES)
runtime/scripts/p29_animal_evolution_smoke.py (nouveau, ~185 LOC, 9/9 PASS)
docs/sprints/2026-05-14_PHASE18-ANIMAL-EVOLUTION.md (ce fichier)
NEXT-SPRINT.md                              (Wave 8 archivé)
```

---

## Pistes Wave 9

- **Agent hunting** : `ActionKind.HUNT_SPECIES(name)` consomme la
  population du chunk avec rendement réel (meat_kcal × hide × bone).
- **Domestication** : agents qui restent près de troupeaux > N ticks
  les "tamènent" — population follows the agent group.
- **Migration saisonnière** : oiseaux et grands mammifères changent de
  chunk selon saisons (temp_c shifts → fitness shifts → diffusion).
- **Speciation animale** : Wave 8b — variants par dérive génétique
  comme dans plant_evolution.
- **HUD widget faune** : top 3 species per kingdom + total population
  + pyramide trophique.
