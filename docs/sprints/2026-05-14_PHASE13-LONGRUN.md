# Phase 13 — Long-Run Stability (100k ticks)

**Date :** 14 mai 2026
**Sprint :** P10 long-run stability sprint.
**Livrable :** `runtime/scripts/p24_long_run_stability.py`
**Journal :** `runtime/journals/p24_long_run.jsonl` (20 lignes, une par segment de 5000 ticks)
**Log brut :** `runtime/journals/p24_run.log`
**Result :** **PASS** (exit 0).

## Objectif

Toutes les smokes existantes (`p0`-`p23`) tournent sur 100 à 2000 ticks
seulement. La question : est-ce que le simulateur reste sain à
**100 000+ ticks** (60 jours-sim à `drive_accel=1500`) ? Trois axes :

1. **Mémoire** : croissance bornée (< 200 MB).
2. **Déterminisme** : même seed → même état après 5000 ticks, deux
   builds indépendants.
3. **Population** : pas d'extinction silencieuse, perf stable.

## Configuration

- Léman, anchor 46.510 N / 6.633 E, taille 2.0 km.
- 30 fondateurs, max_agents 200, drive_accel 1500, 2 cultures.
- seed `0xDEC0DE_42`.
- 20 segments × 5000 ticks = **100 000 ticks**.
- Modules installés en pile : `WorldBuilder` (Wave 1+2 via `install`,
  `install_lift`) + `install_physiology` (Wave 3) +
  `install_photosynthesis` + `install_material_aging` (Wave 4).

## Résultats — chiffres bruts

### Wall-clock

| Segment | Tick | Wall (s) | Mem (MB) | Alive | Hash16 |
|---|---|---|---|---|---|
| 01 | 5 000  | 756.65 | 226.9 | 10 | `143ba17ef510a024` |
| 02 | 10 000 | 720.37 | 233.8 | 10 | `bb067af9973ea459` |
| 03 | 15 000 | 482.03 | 233.2 |  6 | `7fb091c5b8160364` |
| 04 | 20 000 | 437.01 | 234.1 |  5 | `8948ed30d174dcd9` |
| 05 | 25 000 | 408.81 | 161.4 |  5 | `bf54dce1e17eb821` |
| 06 | 30 000 | 345.62 | 153.4 |  5 | `c8990286b8f843cb` |
| 07 | 35 000 | 345.36 | 149.1 |  5 | `6414ea6ed2ddd914` |
| 08 | 40 000 | 352.60 | 147.2 |  5 | `4801dd17faad0b48` |
| 09 | 45 000 | 362.04 | 143.5 |  4 | `cbd6ae2c6f558dea` |
| 10 | 50 000 | 319.77 | 144.1 |  4 | `924f036440f90fe5` |
| 11 | 55 000 | 295.14 | 144.5 |  4 | `5fdd7b980e3ac04c` |
| 12 | 60 000 | 246.58 | 142.9 |  4 | `ba69abd215569c2c` |
| 13 | 65 000 | 234.05 | 144.6 |  4 | `ea684d8c49530d1b` |
| 14 | 70 000 | 253.90 | 145.1 |  4 | `f77b56ada04757b3` |
| 15 | 75 000 | 277.70 | 141.7 |  4 | `ee4aca21ae6bcf06` |
| 16 | 80 000 | 277.73 | 136.9 |  4 | `e0cc5bcc64feb085` |
| 17 | 85 000 | 263.99 | 139.0 |  4 | `3c778d449c9d6a7a` |
| 18 | 90 000 | 246.99 | 140.9 |  4 | `9393195d9f5661e9` |
| 19 | 95 000 | 264.13 | 141.7 |  4 | `3eedab438f18395c` |
| 20 | 100 000| 273.35 | 145.6 |  4 | `51187fd76f27de51` |

Total : **7 163.8 s = 119.40 min** (sim) + 808.2 s = 13.5 min (det
check) → **~133 min wall-clock**.

### Mémoire (psutil RSS)

Courbe en trois phases :

1. **Bootstrap (seg 1-2)** : 226.9 → 233.8 MB. La population fondatrice
   est encore active (alive=10/200 spawned), les caches Wave 4
   (photosynthesis per-chunk, material_aging registry) se peuplent.
2. **Pic-puis-décroissance (seg 3-5)** : la population s'effondre
   (10 → 6 → 5 alive), le GC libère 234 → 161 MB en deux segments.
3. **Steady state (seg 6-20)** : oscillation serrée 137 – 154 MB.
   Final 145.6 MB.

**Δ seg1 → seg20 = -81.3 MB** (la mémoire est **plus basse à la fin**).
Aucune fuite détectée. Budget 200 MB respecté avec une marge énorme.

### Perf (wall-clock par 5000 ticks)

Pic 756 s au seg 1 → plateau ~250 s sur les derniers segments.
**Slowdown ratio (last3 / first3) = 0.400× — pas de slowdown, le
sim accélère à mesure que la population décline.** À population
constante (4 agents) sur les segments 13-20, le wall reste dans la
fourchette 234 – 278 s (cv ≈ 6 %). Pas de dérive perf.

### Population

- Founders : 30 alive.
- Bootstrap : 30 → ~200 (max_agents capé) en quelques milliers de ticks.
- Saturation : alive descend de 200 spawned mais seulement ~10
  encore vivants — la mortalité Wave 3 (choléra, etc.) tue rapidement.
- Steady-state : **4 agents survivants stables sur les 50 derniers
  km-ticks** (seg 9-20). Mean alive last 5 seg = **4.00 exact**.
- Pas d'extinction sur 100k ticks ; pas non plus d'explosion.

### Déterminisme

Hash SHA-256 sur (alive, pos, hunger, thirst, vitality) après
exactement 5000 ticks, **deux builds indépendants** :

```
first run  seg-1 hash : 143ba17ef510a024
repeat run seg-1 hash : 143ba17ef510a024
match = True
```

Bit-identique. Le déterminisme `engine.core.prf_rng` tient sur
toute la chaîne Wave 1+2+3+4 + WorldBuilder.

### Sub-system state — physiologie / photosynthèse / aging

À 100k ticks (seg 20, segment tail) :

- **Physio** : bladder 0.38, bowel 0.52, hygiene 0.43, body_fat 0.20,
  cholera_mean 0.18 / max 0.31 (chronique, pas guérie), 3/4
  infectés. Flu/wound 0 (jamais déclenchés sur 4 agents isolés).
  `relief_total=66 821`, `bathe_total=6 936` — cohérent avec 100k
  ticks × ~4 agents × baseline excrétion.
- **Photosynthesis** : seg 20 capture *à minuit* (PAR=0, donc
  GPP=0). En milieu de cycle (seg 1, PAR=1280.9), GPP global
  =511 989 kcal/tick, dominé par GRASSLAND (290 k) +
  TEMPERATE_FOREST (220 k). `chunks_tracked` : 531 (seg 1) → 701
  (seg 20) — les agents explorent et streament progressivement de
  nouveaux chunks. Pas une fuite : ce sont des chunks réels.
- **Material aging** : `alive_instances=0` en steady-state (les rares
  artefacts inventés au début se sont dégradés ; aucun atelier
  productif avec 4 agents qui survivent à peine).

## Conclusions

1. **Le sim survit 100k ticks** — pas d'extinction, pas de crash, pas
   de divergence numérique.
2. **Pas de fuite mémoire** — RSS finit *plus bas* qu'au seg 1.
3. **Pas de dérive perf** — slowdown 0.40× = on accélère avec moins
   d'agents, ratio cohérent avec O(N²) cognition. À population
   stable (seg 13-20), wall ~250-280 s, CV 6 %.
4. **Déterminisme bit-identique** vérifié sur 2 builds indépendants
   à 5000 ticks.

## Anomalies à flagger (P-NEW candidates)

### P-NEW.22 — Population se stabilise à 4 agents au lieu de saturer max_agents
La sim **bootstrap correctement** (alive=10 au seg 1) puis bleed-out
constant : 10 → 5 → 4 et plateau. Sur 100k ticks, **pas une seule
naissance** ne réussit à compenser. Hypothèse principale :

- Choléra endémique installé seg 1 (`infected_cholera=9` sur 10
  vivants) → `vitality` chronique basse → fertilité Wave 3 inhibée.
- Auto-contamination de l'eau (`contamination_chunks` 15 → 7 sur la
  durée), pas assez d'agents pour invertir le cycle.

Action proposée : sprint dédié reproductibilité du choléra ;
ajouter "well/spring" séparée des contamination_chunks pour permettre
boire propre. Voir Wave 5 dans NEXT-SPRINT.

### P-NEW.23 — Bootstrap GC libère 80 MB
Entre seg 4 et seg 5, le RSS chute de 234 → 161 MB (-73 MB) sans
intervention. Probable Python GC sur des références aux agents
morts (déjà 195/200 morts à ce moment). Pas un bug, mais une
observation : si l'on ajoute du multi-seed/multi-region, considérer
un `gc.collect()` explicite après chaque purge agent pour des
plateaux mémoire prévisibles.

### P-NEW.24 — Photosynthesis chunks_tracked monte progressivement (531 → 701)
Non bloquant mais à noter : Wave 4 `PhotosynthesisState.chunk_caches`
n'est pas LRU. Sur 1M ticks ce dict peut grossir indéfiniment si
les agents explorent une grande carte. Sur ces 100k ticks /
2 km × 2 km, croissance bornée par la géographie disponible —
plafond observé ≈ 700 chunks tracked. Pour bounded long-run sur
des cartes plus grandes : ajouter une éviction LRU au cache.

## Critères de sortie — checklist

- [x] 100k ticks atteint (vs all-dead) — `stop_reason=target-reached`
- [x] Memory delta < 200 MB — `-81.3 MB` (négatif, donc largement ok)
- [x] Determinism check passes — hash match
- [x] Exit 0
- [x] Trajectoire écrite ligne-par-ligne dans `runtime/journals/p24_long_run.jsonl`
- [x] Doc sprint écrite

## Pour rejouer

```bash
python runtime/scripts/p24_long_run_stability.py
```

Compter ~2 h de wall-clock (machine de référence : Windows 10, Python
3.14, 12-core). Le journal `p24_long_run.jsonl` est écrit segment
par segment — possible de couper après N segments si le budget
temps est plus court.
