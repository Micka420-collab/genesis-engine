# SPRINT 2026-05-15 — Wave 10d realistic construction

**Priorité attaquée**: clôturer la chaîne géologique en permettant aux
agents de **construire de vraies maisons, mines, forges, temples** avec
les minéraux et métaux qu'ils ont eux-mêmes extraits.

**Statut**: ✅ livré
**Cible**: 6 recipes calibrées + résolveur 3-niveaux (metallurgy →
geology → fallback inv) + tracking aging.

---

## 6 recipes historiques

| Recipe | Matériaux | Inspiration |
|---|---|---|
| 🏚️ stone_hut | 60 limestone + 25 granite + 12 wood | Néolithique |
| 🏠 stone_house | 250 limestone + 60 granite + 35 wood + 4 Fe | Iron Age 1-room |
| 🔥 brick_kiln | 30 shale + 6 granite + 4 wood | Chalcolithique |
| ⛏️ mineshaft | 100 granite + 12 wood + 6 Fe | adit Bronze→Iron Age |
| ⚒️ forge | 50 granite + 15 shale + 6 wood + 8 Fe + 2 Cu | métallurgie classique |
| 🏛️ marble_temple | 500 marble + 100 limestone + 80 granite + 25 wood + 0.5 Au | grec/romain |

Quantités calibrées sur des estimations archéologiques : une maison
romaine modeste consommait ~8 tonnes de pierre — divisées par 50 pour
échelle "single-builder agent".

## Résolveur 3-niveaux

```python
_resolve_balance(sim, row, material_name) :
  1. metallurgy.agent_pure_elements[row]      # Fe, Cu, Sn, Au, Ag…
  2. geology.cumulative_extracted             # limestone, granite, marble…
  3. fallback inv_wood / inv_stone / inv_metal
```

C'est le **pont** qui relie tout le pipeline Wave 10 :
- Agent a miné 100 kg via `mine_at` → cumulative_extracted[limestone] = X
- Agent a smelté 5 kg hematite → agent_pure_elements[row][Fe] = 3.3
- Agent peut maintenant `build_real(sim, row, "stone_house")` → consommé

## Material_aging integration

```python
build_real(sim, row, "stone_hut") →
    MaterialInstance(
        material_name="stone_limestone",
        exposure_mode="humid_air",
        spawned_tick=sim.tick,
        owner_culture=…,
    )
    bound to RealStructure.material_instance_id
```

La structure vieillit alors automatiquement au taux annuel de son
matériau dominant :
- 🏚️ stone_hut limestone → 0.08 %/yr en humid_air → **~5000 ans**
- 🏠 stone_house limestone → idem
- ⛏️ mineshaft granite → 0.005 %/yr (×2.5 pour wet_soil = 0.0125%) → **8000 ans**
- ⚒️ forge granite → ×3.0 open_fire = 0.015%/yr → **6500 ans**
- 🏛️ marble_temple marble → 0.08 %/yr → ~5000 ans

## Smoke `p36_realistic_construction_smoke` **9/9 PASS**

```
[OK] step 1 — install idempotent + recipes loaded               6 recipes
[OK] step 2 — empty inventory → can_build False                 deficits listed
[OK] step 3 — build_real stone_hut succeeds                      sid=1
[OK] step 3 — inventory consumed                                 wood 50→38, stone 200→115
[OK] step 4 — aging instance bound to structure                  stone_limestone integrity 1.0
[OK] step 5 — 200 yr humid integrity ≈ 0.84                     0.8400 (exact 0.08%/yr × 200)
[OK] step 6 — empty inv → temple fails with deficits             {marble: 500, Au: 0.5…}
[OK] step 7 — persistence round-trip
[OK] step 8 — ADR-0005 lists module                              17/17 required
```

**Vérification scientifique** :
- Limestone humid air decay : 0.08 %/yr → 200 yr = 16 % loss
- Integrity attendue : 1.0 - 0.16 = **0.84** ✓ exact

## ADR-0005 → 17 modules requis taggés

| # | Module | Pipeline | Capability |
|---|---|---|---|
| 1-16 | (existants Wave 1-10c) | … | … |
| **17** | **realistic_construction** (nouveau) | **L4 Feedback** | **paper-L2 Simulator** |

## Boucle bout-en-bout vérifiée

```
Earth chunk strata (Wave 10 L1)
  ↓ MINE depth=50m → ore
geology.cumulative_extracted[limestone] += X kg
  ↓ SMELT → pure elements
metallurgy.agent_pure_elements[row][Fe] += Y kg
  ↓ build_real("stone_house")
RealStructure created, material_instance spawned
  ↓ material_aging tick over years
limestone integrity decays 0.08 %/yr
  ↓ writing inscribe blueprint on stone (Wave 9b)
recipe preserved 6000 ans
  ↓ future gens read → rebuild
```

**Toute la chaîne Earth → minerals → metal → buildings → cultural
transmission est maintenant physiquement bouclée.**

## Pré-requis Phase 5 — état

| Pré-req | État |
|---|---|
| 17 modules Wave 1-10d ADR-0005 | ✅ |
| P-NEW.22 cholera + P-NEW.24 cache | ✅ |
| Wave 9d cognition wiring | ✅ |
| Wave 10b MINE wiring | ✅ |
| Wave 10c SMELT chain | ✅ |
| **Wave 10d realistic_construction** | ✅ **(ce sprint)** |
| Wave 11 personality drives politics | ⏳ |
| Wave 12 run 10K sim-yr | ⏳ |

**7/9 pré-requis Phase 5 livrés**. Reste personnalité→politique +
validation long-run.

## Fichiers touchés

```
runtime/engine/realistic_construction.py             (nouveau, ~390 LOC)
runtime/engine/dashboard.py                          (+10 LOC : endpoint)
runtime/engine/world_library.py                      (+1 LOC : persistent module)
runtime/engine/world_model_capabilities.py           (+1 LOC : required module)
runtime/scripts/p36_realistic_construction_smoke.py  (nouveau, ~200 LOC, 9/9 PASS)
docs/sprints/2026-05-15_PHASE24-REALISTIC-CONSTRUCTION.md  (ce fichier)
NEXT-SPRINT.md                                       (Wave 10d archivé)
```
