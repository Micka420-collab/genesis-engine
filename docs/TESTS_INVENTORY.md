# Genesis Engine — Inventaire des Tests Réalisés

Synthèse de tous les tests / expériences / smokes déjà exécutés sur le moteur, avec résultats clés.

Sources : `runtime/artifacts/`, `runtime-phase5/artifacts/`, `runtime/exports/`, `runtime/journals/`.

---

## 1. Phase 1-4 — Expériences canoniques

Fichier : `runtime/artifacts/all_experiments_summary.json`

| Exp                  | Ticks | TPS   | Vivants finaux | Naissances | Morts | Gen max | Mating | Cause mort #1   |
|----------------------|-------|-------|----------------|------------|-------|---------|--------|-----------------|
| exp1_scarcity        | 250   | 25.3  | 49             | 54         | 5     | 8       | 44     | EXHAUSTION      |
| exp2_food_pressure   | 200   | 4.7   | 137            | 200        | 63    | 10      | 150    | EXHAUSTION      |
| exp3_two_cultures    | 250   | 8.4   | 196            | 200        | 4     | 13      | 176    | EXHAUSTION      |
| exp4_catastrophe     | 200   | 9.0   | 136            | 153        | 17    | 14      | 123    | DEHYDRATION     |
| stress_100           | 150   | 3.7   | 255            | 258        | 3     | 4       | 158    | DEHYDRATION     |

**Observations** :
- ✅ Reproduction démontrée jusqu'à **génération 14** (exp4_catastrophe).
- ⚠️ **0 conflits et 0 shares** sur toutes ces runs → couches sociales pas activées en phase 1-4.
- ⚠️ TPS s'effondre dès qu'on dépasse ~150 agents (de 25 → 3.7).
- ✅ Le moteur tient une catastrophe : 17 morts sur 153 naissances, pop stabilisée à 136.

---

## 2. Phase 4 — Scaling + culture

Fichier : `runtime/artifacts/phase4_summary.json`

| Run                  | Founders | Ticks | TPS   | Vivants | Vocalisations | Compétitions | Groupes formés |
|----------------------|----------|-------|-------|---------|---------------|--------------|----------------|
| phase4_smoke_60      | 60       | 80    | 7.48  | 88      | 280           | 344          | 1              |
| phase4_scale_100     | 100      | 50    | 4.85  | 125     | 316           | 393          | 4              |
| phase4_scale_200     | 200      | 30    | 2.36  | 214     | **0**         | 576          | **0**          |
| phase4_two_cultures  | 48       | 80    | 6.65  | 73      | 203           | 330          | 3              |

**Observations** :
- 🔴 **Régression critique à 200 founders** : aucune vocalisation, aucun groupe → couche langage/social effondrée sous charge.
- ✅ À 60-100 founders, **groupes émergent spontanément** (1 à 4).
- ✅ `distinct_lex_signatures == vocalisations` → chaque vocalisation est unique (pas encore de convergence lexicale).
- ⚠️ TPS ~2.36 à 200 agents = inutilisable pour long run.

---

## 3. Phase 5 — Boucle 5CD (Cognition/Communication/Culture/Décision)

Fichier : `runtime-phase5/artifacts/phase5_summary.json`

| Exp                  | Ticks | TPS   | Vivants | Vocs | Compét. | Groupes (formés/dissous) | Shares | Mating | Affinité moy. |
|----------------------|-------|-------|---------|------|---------|--------------------------|--------|--------|---------------|
| exp1_scarcity        | 150   | 25.88 | 44      | 162  | 28      | 1 / 0                    | 136    | 34     | +0.0625       |
| exp2_food_pressure   | 100   | 6.47  | 152     | 516  | 197     | 5 / 2                    | 388    | 102    | +0.0541       |
| exp3_two_cultures    | 120   | 5.64  | 210     | 761  | 125     | 12 / 0                   | 339    | 162    | +0.0606       |
| exp4_catastrophe     | 120   | 7.65  | 99      | 600  | 145     | 10 / 0                   | 177    | 94     | +0.0507       |
| phase5_stress_100    | 50    | 4.19  | 135     | 313  | 397     | 3 / 0                    | **0**  | 35     | **-0.0027**   |

**Observations** :
- ✅ **Saut qualitatif vs Phase 4** : les *shares* apparaissent (jusqu'à 388 dans exp2). Comportement coopératif activé.
- ✅ **Groupes nombreux** : 12 dans two_cultures, dissolutions observées (5 formés / 2 dissous) → dynamique sociale réelle.
- ✅ **Affinité positive** dans toutes les expériences normales (+0.05 à +0.06).
- ⚠️ **stress_100 reste régressif** : affinité négative, 0 shares → la couche sociale décroche encore en haute densité.
- ⚠️ **max_generation = 1** dans Phase 5 (vs 8-14 en Phase 1-4) → boucle 5CD ralentit la reproduction, à investiguer.
- 🔴 **0 morts** dans 4 exp sur 5 → mortalité désactivée ou seuils trop bas en Phase 5.

---

## 4. Multi-région — Validation géographique

Fichier : `runtime/exports/multi_region_summary.json`

| Région     | Anchor (lat,lon)     | Founders | Tick | Vivants | Végétation dominante | Projets/Structures | Artefacts inventés |
|------------|----------------------|----------|------|---------|----------------------|--------------------|--------------------|
| Lausanne   | 46.51 / 6.633        | 20       | 400  | 142     | GARRIGUE 60%, FORET 28% | 1 / 1            | **flint_grind** ✅ |
| Sahara     | 25.7 / 29.0          | 12       | 400  | 129     | PRAIRIE 100%         | 1 / 1              | 0                  |
| Amazon     | -3.11 / -60.02       | 18       | 400  | 246     | GARRIGUE 89%, FORET 9% | 2 / 0            | 0                  |
| Reykjavik  | 64.14 / -21.94       | 14       | 400  | 135     | GARRIGUE 72%, FORET 19% | 1 / 1            | 0                  |

**Observations** :
- ✅ **Premier artefact culturel émergent** : `flint_grind` apparaît spontanément à Lausanne (taille de silex).
- ✅ Démographie cohérente par biome : Amazon (forêt humide) supporte 246 agents, Sahara (prairie/aride) en sature 129.
- ✅ Cache L1 100% hit rate (453-485 hits, 0 miss) → cache chunks Earth-loader stable.
- ⚠️ Sahara modélisé comme 100% PRAIRIE → **biome desert manquant** dans la couche L2.
- ⚠️ Amazon a 0 structures finalisées sur 400 ticks → temps de construction trop long ou ressources rares dans ce biome.
- ⚠️ `mean_slope_deg = 0` pour Sahara/Amazon/Reykjavik → **terrain plat artificiel**, données topo manquantes pour ces régions.

---

## 5. Smokes & validations isolées

Journaux : `runtime/journals/`

| Fichier                          | Type                     | Status implicite |
|----------------------------------|--------------------------|------------------|
| p0_smoke.jsonl                   | Bootstrap Phase 0        | ✅ run           |
| p3_earth_smoke.jsonl             | Earth-loader smoke       | ✅ run           |
| p4_leman_10k_stdout.log          | Lac Léman 10k ticks      | ✅ long run      |
| p4_leman_5k_stdout.log           | Lac Léman 5k ticks       | ✅ run           |
| p4_leman_2k_verif.log            | Lac Léman 2k vérif       | ✅ run           |
| p5_lift_smoke.jsonl              | Phase 5 lift             | ✅ run           |
| p7_hunt_smoke.jsonl              | Chasse                   | ✅ run           |
| p8_trails_smoke.jsonl            | Pistes / trails          | ✅ run           |
| p9_timewarp_smoke.json           | Time warping             | ✅ run           |
| p11_observatory_smoke.out        | Observatoire             | ✅ run           |
| p12_integration.jsonl            | Intégration globale      | ✅ run           |
| phase5a_leman.jsonl              | Léman + 5CD              | ✅ run           |
| sprint_a4_genome.jsonl           | Génome sprint A4         | ✅ run           |
| sprint_b4_statics.jsonl          | Statics sprint B4        | ✅ run           |
| profile_tick.txt                 | Profiling tick           | ✅ run           |

---

## 6. Tests unitaires Python

| Fichier                              | Couverture                  |
|--------------------------------------|-----------------------------|
| `runtime/tests/test_engine.py`       | Moteur core                 |
| `runtime/tests/test_earth_loader.py` | Chargement données Earth    |
| `runtime/tests/test_god_avatar.py`   | Avatar / God-mode           |
| `runtime/tests/test_sim_5cd_integration.py` | Intégration 5CD       |
| `runtime-phase5/tests/test_engine.py`| Engine Phase 5              |

---

## 7. Bilan global

### ✅ Validés
- Moteur fonctionnel **jusqu'à tick 400** sur 4 régions Terre réelles.
- Reproduction → **gen 14** atteinte (Phase 1-4).
- Émergence sociale en Phase 5 : groupes, shares, affinité positive.
- **Premier artefact culturel émergent** : `flint_grind` (Lausanne).
- Cache Earth-loader stable (100% hit rate).

### ⚠️ Régressions / points faibles
- TPS s'effondre à 200+ agents (de 25 → 2.4).
- Phase 4 scale_200 : langage et groupes **disparaissent** sous charge.
- Phase 5 stress_100 : affinité négative, **0 shares**.
- Max generation = 1 en Phase 5 vs 14 en Phase 1-4 → reproduction freinée.
- 0 morts dans 4/5 exp Phase 5 → mortalité à recalibrer.

### 🔴 Trous de couverture
- **Aucun conflit** observé (fights_cum = 0 partout) → couche agression jamais déclenchée.
- **Biome desert absent** : Sahara modélisé comme prairie.
- **Topographie plate** pour Amazon/Sahara/Reykjavik (mean_slope = 0).
- Pas de test de **longue durée + multi-région simultané** (>10k ticks combinés).
- Pas de test **reproductibilité seed-à-seed** documenté.

---

## 8. Prochains tests recommandés

1. **Stress + 5CD combiné** : refaire stress_100 avec la boucle 5CD activée, comprendre pourquoi shares=0.
2. **Recalibrage mortalité Phase 5** : faire tourner exp1-3 longtemps (500+ ticks) pour voir si la mortalité émerge ou reste à zéro.
3. **Profiling TPS** : identifier la fonction qui passe de 25→2.4 TPS entre 50 et 200 agents.
4. **Test conflit** : forcer un scénario de rareté extrême pour valider la couche fights.
5. **Run 1k ticks multi-région** simultané (4 régions × 1000 ticks) → cohérence atmosphère + diffusion culturelle entre régions.
6. **Reproductibilité** : même seed sur 2 machines, diff bit-à-bit des artifacts.
