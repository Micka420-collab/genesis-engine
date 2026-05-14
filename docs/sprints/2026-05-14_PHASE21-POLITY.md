# SPRINT 2026-05-14 — Phase 4 polity (Wave 9c) — État émergent

**Priorité attaquée**: 3e et dernier livrable de la **Phase 4 —
Émergence Civilisationnelle**.

**Statut**: ✅ livré
**Cible**: proto-gouvernement émergent avec leader, territoire, lois,
taxation et redistribution.

---

## 🎯 Phase 4 maintenant 100% complète

| Sprint | État |
|---|---|
| Wave 9 — Agriculture | ✅ session 22 |
| Wave 9b — Writing | ✅ session 23 |
| **Wave 9c — Polity (État)** | ✅ **session 24 (ce sprint)** |
| Wave 9d — Cognition wiring | ⏳ (optionnel, plus tard) |

Roadmap §44-49 :
- Phase 0 ✅
- Phase 1 ✅
- Phase 2 ✅
- Phase 3 🟡 (partiel)
- **Phase 4 ✅ (complète)**
- Phase 5 ⏳ Genesis-α Public

---

## `engine/polity.py` (~450 LOC)

### Mécanique

```python
@dataclass class Polity:
    polity_id: int
    name: str
    leader_row: int
    leader_culture: int
    territory_chunks: Set[coord]
    member_rows: Set[int]
    enforced_laws: Set[str]
    treasury_kcal: float
    founded_tick: int
    tax_collected_kcal, distributed_kcal, violations
```

### 4 sous-systèmes par tick

1. **Leader election** (toutes les 1000 ticks)
   - Score = `offspring_count + 0.5 × authored_inscriptions + age_bonus`
   - Tie-break déterministe via `prf_rng(polity_id, tick)`
2. **Tax** : 5% du `inv_food` de chaque membre → `treasury_kcal`
3. **Redistribute** : agents avec `hunger > 0.55` reçoivent food
   proportional à leur deficit, capé par `inv_capacity_kg`
4. **Law enforcement** : si polity adopte `"no_relief_upstream"`,
   compte les membres qui font relief sur chunks contaminés > 0.5

### Emergence automatique

```python
maybe_emerge_polity(sim, state)
  → si POLITY_MIN_FOUNDERS (4) agents dans
    POLITY_FOUNDING_RADIUS_M (200 m) ET pas déjà en polity
  → fonde une nouvelle polity automatiquement
```

Appelé chaque 100 ticks dans `tick_polity`.

### Disband

```python
_disband_if_collapsed
  → si len(member_rows) < POLITY_DISBAND_MEMBERS (2)
  → polity supprimée, agents libérés, territoire reset
```

---

## Couplages cross-module

| Lit | Mute |
|---|---|
| `sim.agents.offspring_count` | `sim.agents.inv_food` (tax) |
| `sim.agents.inv_capacity_kg` | `sim.agents.inv_food` (redistribute) |
| `writing.WritingState.culture_laws` | (none) |
| `physiology.PhysioFields.water_contamination` | (none) |
| `physiology.PhysioFields.bladder` | (none — violation detection) |

**Loi exemple : `"no_relief_upstream"`**. Si la culture l'adopte
(inscription LAW dans `writing`), polity enforce. Un membre qui relief
sur chunk contaminé > 0.5 avec bladder < 0.1 → **violation logged**.
Ouvre la voie à des sanctions (futurs sprints — pour l'instant
diagnostic seulement).

---

## Validation `p32_polity_smoke` — **8/8 PASS**

```
[OK] step 1 — install_polity idempotent
[OK] step 2 — found_polity creates polity with 5 members           pid=1
[OK] step 3 — tax: member inv_food drops, treasury rises           2.000→1.900, treasury 0→1250
[OK] step 4 — redistribute fills hungry members                    distributed=1250 kcal, hungry 1.900→2.150
[OK] step 5 — leader election picks highest prestige               leader=2 (offspring_count=5)
[OK] step 6 — polity disbands when members < threshold             polities=0
[OK] step 7 — ADR-0005 lists polity OK
[OK] step 8 — persistence round-trip preserves polity              treasury=123456, violations=3
```

**Vérifications scientifiques** :
- Tax 5 % × 2 kg = 0.1 kg drained → 0.1 × 2500 kcal/kg = **250 kcal**
  pour 5 membres = **1250 kcal** au treasury ✓
- Redistribution déterministe proportionnelle au besoin ✓
- Leader = agent avec le plus d'offspring_count (5 vs 0/0/0/1) ✓

---

## Boucle de rétroaction Phase 4 maintenant fermée

```
agent invente recette (Wave 1/2)
     ↓
inscrit sur tablette argile (Wave 9b writing)
     ↓
6000 ans passent, recette persiste
     ↓
nouvelle génération lit la tablette
     ↓ propagation
MaterialRegistry restored

   agent sème (Wave 9 agriculture)
     ↓
plant_evolution.ChunkVegetation += 40 kg
     ↓
harvest 50% biomasse → inv_food
     ↓ 
   polity émerge (Wave 9c NEW)
     ↓ tax 5%/tick
treasury_kcal accumule
     ↓ redistribute aux hungry
agents survivent même quand foraging échoue
     ↓
population stable → expansion
     ↓
plus de membres → plus de polities → division territoriale
```

C'est le **cycle néolithique → âge du bronze → premiers États** modélisé
mécaniquement, avec respect des lois physiques (Wave 1-8) + chaque
maillon vérifié par smoke.

---

## ADR-0005 → 14 modules requis taggés

| # | Module | Capability |
|---|---|---|
| 1 | earth_loader | paper-L1 |
| 2 | sim_lift | paper-L2 |
| 3 | realism | paper-L2 |
| 4 | physiology | paper-L2 |
| 5 | photosynthesis | paper-L2 |
| 6 | material_aging | paper-L1 |
| 7 | marine | paper-L2 |
| 8 | global_world | paper-L2 |
| 9 | plant_evolution | paper-L2 |
| 10 | meteorology | paper-L2 |
| 11 | animal_evolution | paper-L2 |
| 12 | agriculture | paper-L2 |
| 13 | writing | paper-L2 |
| **14** | **polity** (nouveau) | **paper-L2** |

---

## Non-régression

- `p18_capabilities_lint` → **14/14** OK
- `p23_persistence_roundtrip` → 7/7 PASS
- `p30_agriculture_smoke` → 10/10 PASS
- `p31_writing_smoke` → 12/12 PASS

---

## Fichiers touchés

```
runtime/engine/polity.py                          (nouveau, ~450 LOC)
runtime/engine/dashboard.py                       (+11 LOC : endpoint)
runtime/engine/world_library.py                   (+1 LOC : _PERSISTENT_MODULES)
runtime/engine/world_model_capabilities.py        (+1 LOC : _REQUIRED_MODULES)
runtime/scripts/p32_polity_smoke.py               (nouveau, ~220 LOC, 8/8 PASS)
docs/sprints/2026-05-14_PHASE21-POLITY.md         (ce fichier)
NEXT-SPRINT.md                                    (Phase 4 polity archivé)
```

---

## Phase 5 — Roadmap

Avec Phase 4 livrée, la roadmap §44-49 indique **Phase 5 — Genesis-α
Public** :
- **2 fondateurs, 10 années réelles = 10 000 années sim**.
- Cible : une civilisation complète émergente, observable jour par jour.

Pré-requis : tous les modules Wave 1-9c sont là. Reste à :
- Wave 9d : router les actions PLANT/HARVEST/READ/INSCRIBE dans
  `cognition.decide` pour que les agents les choisissent eux-mêmes.
- Wave 10 : agent personality drives politics (ambition → fonde des
  polities, agreeableness → accepte taxation).
- Wave 11 : optim run 10K sim-years sans crash. P-NEW.22/.24 corrigés ✓.
