# SPRINT 2026-05-14 — P-NEW.21 path (b) : chunk mask cache + flags

**Priorité attaquée**: P-NEW.21 path (b) — réduire `_scan_chunk` sous 40 µs/call
via cache de masques bool par chunk + invalidation explicite.

**Statut**: ✅ livré
**Résultat**: 69.3 s → **63.1 s** (−9 % cumulé / −12.4 % vs baseline 72 s)

---

## Contexte

Après optim #3b (dense bool-mask avec `d2` partagé, sprint précédent),
`_scan_chunk` était à **54 µs/call** soit 30.7 s sur 300 ticks. Le
profile montrait que ~50 % de ce coût venait de la création répétée des
trois masques `chunk.water > 5`, `chunk.food_kcal > 5`, `shelter_mask`
pour chaque agent percevant le même chunk dans un tick.

Idée : cacher les trois masques **par chunk** (pas par tick), avec
invalidation **explicite** à chaque mutation des champs concernés. La
cohérence est gardée bit-perfect tant qu'on instrumente correctement
les sites d'écriture.

---

## Implémentation

### 1. Cache sur le Chunk (`engine/world.py`)

```python
@dataclass
class Chunk:
    ...
    def __post_init__(self):
        self._mask_cache = None  # (water, food, shelter, hw, hf, hs) | None


def invalidate_resource_masks(chunk):
    chunk._mask_cache = None
```

### 2. Lecture cachée (`engine/cognition.py`)

```python
def _chunk_resource_masks(chunk):
    cached = chunk._mask_cache
    if cached is not None:
        return cached
    water_mask = chunk.water > np.float32(5.0)
    food_mask = chunk.food_kcal > np.float32(5.0)
    shelter_mask = (
        (chunk.wood > 30.0) | ((chunk.stone > 25.0) & (chunk.height > 800.0))
    )
    entry = (water_mask, food_mask, shelter_mask,
             bool(water_mask.any()), bool(food_mask.any()), bool(shelter_mask.any()))
    chunk._mask_cache = entry
    return entry
```

Le tuple porte **aussi** les 3 flags `has_*` (Python bool, ~0 cost à
lire), pré-calculés une fois par cache-miss, consommés par les `if`
gates de `_scan_chunk`. Les premières tentatives (sans flags cachés)
remplaçaient le coût de création de masques par +2M `.any()` calls, ce
qui annulait quasiment le gain.

### 3. Invalidation aux 10 sites de mutation

| Fichier | Site | Action |
|---|---|---|
| `cognition.py:524` | `DRINK` writes `chunk.water[cy,cx]` | ✅ |
| `cognition.py:550` | `FORAGE` writes `chunk.food_kcal[cy,cx]` | ✅ |
| `world.py:447,452` | `regenerate_chunk_resources` writes food + water | ✅ |
| `sim_lift.py:253` | `tick_vegetation` writes `chunk.wood[:]` | ✅ |
| `sim_lift.py:302` | `tick_erosion` decays `chunk.wood[cy,cx]` | ✅ |
| `sim_5cd_integration.py:541` | wood foraging | ✅ |
| `sim_5cd_integration.py:554` | stone foraging | ✅ |
| `ecology.py:163` | sea-level flood writes `chunk.water` | ✅ |
| `realism.py:140` | river injection writes `chunk.water` | ✅ |

### Validation déterminisme

```
run1 / run2 (même seed, 120 ticks, pop=20→...) :
  → SHA-256(alive+pos+hunger+thirst) = 5ea89da1466e4c318766e74e81a2ef2a
  → BIT-IDENTIQUE entre runs ET avec la version pré-cache
```

Tout site de mutation est instrumenté → pas de stale-mask possible.

---

## Profile (300 ticks à pop=175, warmup 800 ticks)

| Variante | Total | `_scan_chunk` tot | per-call | `.any()` |
|---|---|---|---|---|
| Pré-baseline (optim #2)         | 72.0 s | 31.4 s | 52 µs | 2.4M |
| Optim #3 sparse ⚠                | 114.3 s | 71.1 s | 125 µs | 1.5M |
| Optim #3b dense+shared d2       | 69.3 s | 30.7 s | 54 µs | 2.3M |
| Optim #3c sans flags cachés     | 68.1 s | 22.8 s | 40 µs | 4.3M ⚠ |
| **Optim #3c avec flags cachés** | **63.1 s** | **22.5 s** | **40 µs** | **2.3M** ✅ |

**Cible <60 s manquée de 3.1 s** mais on touche le plancher numpy
pratique sur grid 64×64 à pop=175 :

- `_scan_chunk` : 40 µs/call (de 54 µs → −26 %)
- `_chunk_resource_masks` : 1.7 s tottime sur 569k calls = 3 µs/call
  moyen (cache hit majoritaire)
- Les `.any()` qui restent (2.3M ≈ niveau pré-baseline) sont presque
  tous l'intersection `in_r & mask` et le test final `m.any()` — non
  cachables car dépendants de la position de l'agent

---

## Pistes restantes pour <60 s (P-NEW.21)

| Approche | Gain estimé | Effort |
|---|---|---|
| (a) batch perceive — partager `d2` entre les agents d'un même chunk | ~−5 s | Refactor |
| (c) cython/numba sur `_scan_chunk` | ~−15 s | Build chain |
| (d) `r_chunks=2` → réduire perception 60 m à 50 m | ~−3 s | Semantic change |

Le path (a) reste le plus propre. (c) demande d'ajouter une toolchain.
(d) change la sémantique gameplay.

---

## Fichiers touchés

```
runtime/engine/cognition.py            (+30 LOC — flag cache + has_* gates)
runtime/engine/world.py                (+15 LOC — __post_init__ + invalidate)
runtime/engine/sim_lift.py             (+2 LOC  — 2 sites invalidés)
runtime/engine/sim_5cd_integration.py  (+2 LOC  — 2 sites invalidés)
runtime/engine/ecology.py              (+2 LOC  — 1 site invalidé)
runtime/engine/realism.py              (+2 LOC  — 1 site invalidé)
runtime/journals/profile_tick.txt      (regen)
docs/sprints/2026-05-14_PHASE8-MASK-CACHE.md   (ce fichier)
NEXT-SPRINT.md                         (P-NEW.21 path (b) archivé)
```

---

## Référence

- ADR-0005 / P-NEW.20 (sprint précédent) — endpoint capabilities
- Sprint P-NEW.17 — `docs/sprints/2026-05-14_PHASE7-PROFILE-OPTIM3b.md`
- `runtime/engine/cognition.py:189` — `_chunk_resource_masks`
- `runtime/engine/cognition.py:224` — `_scan_chunk` (optim #3c)
- `runtime/engine/world.py:invalidate_resource_masks`
