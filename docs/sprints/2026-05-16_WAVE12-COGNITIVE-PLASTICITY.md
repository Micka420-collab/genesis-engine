# Sprint 2026-05-16 — Wave 12 cognitive plasticity (combo PIANO × Wave 11)

**Mode :** Autonome (déclenchement scheduled-task `continue-la-cration-de-genesis-enginer`).
**Cible :** NEXT-SPRINT.md candidat W12 explicite — *"plasticité d'apprentissage sur intelligence_effective"* — pour étirer les queues power-law observées plates en Phase 4 (Hill α ≈ 4.0).

---

## TL;DR

Nouveau module `engine/cognitive_plasticity.py` (~340 LOC) qui introduit un **buffer additif** `learned_skill[N]` accumulé par expérience d'actions cognitivement coûteuses (BUILD, SMELT, MINE, HARVEST, INVENT, SPEAK). Une fonction `intelligence_effective(sim, row) = clip(intelligence_base + learned_skill, 0, 1)` expose le trait *appris* sans toucher au trait *génétique* (héritage Phase 4 préservé bit-identique). Persistance via `plasticity.npz` branchée dans `world_library._PERSISTENT_MODULES`. `elite_metrics` étendu (append-only, signature originale inchangée) avec `compute_elite_metrics_effective(sim)`.

**9/9 PASS** sur `p41_cognitive_plasticity_smoke`. Non-régression confirmée :

| Smoke | Statut |
|---|---|
| `p18_capabilities_lint` | OK — 18/18 modules requis taggés ADR-0005 |
| `p23_persistence_roundtrip` | OK — bit-identique |
| `p37_elite_metrics_smoke` | OK — 8/8 (signature inchangée) |
| `p40_art_discovery_smoke` | OK — 8/8 |
| `p41_cognitive_plasticity_smoke` | **OK — 9/9 (nouveau)** |

---

## Veille du jour (Étape 0)

5 recherches web parallèles. Synthèse :

| # | Découverte | Couche Genesis | Gain potentiel |
|---|---|---|---|
| 1 | **PIANO cognitive architecture** (arxiv 2411.00114 — *Project Sid: Many-agent simulations toward AI civilization*) | Agentic | Modules cognitifs concurrents partageant un Agent State évolutif → apprentissage individuel |
| 2 | Bevy 0.16 (ECS Relationships + GPU-Driven Rendering + occlusion culling) | Substrate/World (v1.0 future) | +30% rendering scènes complexes |
| 3 | `rustls-post-quantum` 0.2.1 + ML-KEM-768 hybride X25519 | Platform | Production-ready PQC (AWS, Cloudflare) |
| 4 | ClickHouse NATS Table Engine | Observatory | Pipeline NATS→ClickHouse sans pipeline externe |
| 5 | Cryspen verified ML-KEM (formellement vérifié F\*) | Platform | Audit-grade PQC |

**CVE actives :** aucune critique sur tokio / gRPC / k8s détectée.
**Paper du jour :** *Project Sid* (arxiv 2411.00114) — directement applicable. Le projet implémente déjà une cognition Big-Five hardcodée (Wave 11) ; PIANO suggère que l'**Agent State** doit évoluer par expérience, pas seulement par génétique. Wave 12 = Genesis-isation minimale de cette idée.

---

## COMBO RETENU (Étape 1)

**Q1 — Existe déjà dans Genesis ?**
Une cognition individuelle existe (`engine/cognition.py`) mais elle est *lecture-seule sur traits génétiques figés* (`agents.intelligence` posé à la naissance et jamais modifié). PIANO suggère un *State* qui se met à jour.

**Q2 — Combinaison ?**
Wave 11 `engine/elite_metrics.py` a observé `Hill α ≈ 4.0` (queues courtes), exactement la signature d'une cognition statique. Combo : *PIANO × Wave 11* = ajouter un buffer Hebbien qui s'accumule par expérience cognitive et alimente une nouvelle métrique `_effective`.

**Q3 — Gain mesurable**
* `top10/median ratio` lifté : `1.473 → 1.658` sur le smoke 32 founders × 2 cultures.
* `mean lifté` : `0.490 → 0.624` sur les agents boostés.
* Émergence : possibilité qu'une fraction de population *spécialise* sa cognition (mineurs/fondeurs vs idles).

**Q4 — Coût**
* 2 h, complexité 3/5, risque régression 2/5 (module **additif**, l'ancien `intelligence` reste intact).
* Pas d'ADR architecturel requis (extension modulaire ; pas de protocole gRPC nouveau).

**COMBO_RETENU** : `PIANO (arxiv 2411.00114)` × `Wave 11 elite metrics`
**COMBO_BACKLOG** : Bevy 0.16 (v1.0 future), rustls-post-quantum (v1.0 platform layer), ClickHouse NATS engine (Observatory v1.0).
**COMBO_REJETÉ** : aucune découverte non pertinente cette session.

---

## Audit projet (Étape 2)

| Champ | Valeur |
|---|---|
| Phase | 4 + transitions Phase 5 (W11/W12/W13 multi-wave) |
| Couches opérationnelles | Agent, World, Observatory, Society émergente, Substrate Python |
| P0 bloquants | aucun (toutes les W10–W13 livraisons ont validé leur smoke) |
| Tâche du jour | Wave 12 (mentionnée explicitement dans la conclusion de la session 29 W11 elite metrics) |
| Impacté par veille | OUI — Project Sid PIANO renforce le mandat W12 |

→ **Décision** : fusionner le combo PIANO et la tâche W12 en *une seule tâche enrichie*.

---

## Détail technique (Étape 3)

### `engine/cognitive_plasticity.py` (nouveau, ~340 LOC)

**Constantes**

```python
COMPLEXITY_WEIGHT = {            # gain par action selon coût cognitif estimé
    ActionKind.SMELT:    0.018,  # reduction d'oxyde, réglage T° fer/cuivre
    ActionKind.BUILD:    0.012,
    ActionKind.MINE:     0.008,
    ActionKind.HARVEST:  0.006,
    ActionKind.HUNT:     0.006,
    ActionKind.SPEAK:    0.004,  # geste social fréquent → faible
    ActionKind.SHARE:    0.003,
    ActionKind.PLANT:    0.004,
    ActionKind.EXPLORE:  0.002,
    ActionKind.FORAGE:   0.002,
    ActionKind.SEEK_SHELTER: 0.001,
    ActionKind.FIGHT:    0.001,
    # IDLE / WALK_TO / DRINK / EAT / SLEEP / MATE / FLEE → 0
}
DEFAULT_DECAY = 0.9995           # ½-vie ~1385 ticks (oubli lent)
LEARNED_SKILL_CAP = 1.5          # plafond hard du buffer
```

**API**

```python
install_plasticity(sim)                          # idempotent
record_experience(sim, row, action_kind)         # +delta sur buffer
record_experience_batch(sim, [(row, kind, ...), ...])
decay_step(sim)                                  # *decay (oubli)
tick_step(sim, events, apply_decay=True)         # helper combo
intelligence_effective(sim, row)        -> float
intelligence_effective_array(sim)       -> ndarray
compute_plasticity_metrics(sim)         -> dict
save_plasticity_state(sim, world_dir)   -> path | None
load_plasticity_state(sim, world_dir)   -> bool
```

**Modèle d'apprentissage** : Hebbien gated par curiosité.

```
δ_learned[row] += COMPLEXITY_WEIGHT[action] × curiosity_factor(curiosity[row]) × intensity

curiosity_factor(c) = 0.5 + 1.0·clip(c, 0, 1)   # ∈ [0.5, 1.5]
```

Un agent à `curiosity=1` apprend **3×** plus vite qu'un agent à `curiosity=0` — c'est la signature qui sera testée par le smoke.

### `engine/elite_metrics.py` (extension append-only)

Nouveau helper `compute_elite_metrics_effective(sim)` qui utilise `_skill_proxy_effective` (lit le buffer plasticity si présent, sinon retombe sur le proxy de base). **Signature originale `compute_elite_metrics(sim)` strictement inchangée** — donc `p37` reste bit-identique.

### `engine/world_library.py` (1 entry ajoutée)

```python
("engine.cognitive_plasticity",
 "save_plasticity_state",
 "load_plasticity_state"),
```

→ Wave 12 persiste automatiquement avec tout monde sauvegardé. Backward-compat : un monde sauvegardé pré-Wave 12 charge avec un buffer zero (pas de crash).

### `scripts/p41_cognitive_plasticity_smoke.py` (nouveau)

9 vérifications :

1. **install** idempotent + buffer zero.
2. **non-cognitive actions** sont no-op (IDLE, WALK_TO, …).
3. **curiosity gating** : hi-C apprend ≈ **3.0×** plus que lo-C (mesuré : `lo=0.4500, hi=1.3500, ratio=3.00`).
4. **clip** : `intelligence_effective` ∈ [0, 1] même après spam.
5. **decay_step** divise par 2 à factor=0.5 (vérifié déterministe).
6. **power-law signature** : sur 50 ticks + boost 1/4 SMELT + 1/4 BUILD, `top10/median` lift `1.473 → 1.658` et mean lift `0.490 → 0.624`.
7. **déterminisme** : deux replays identiques → buffer bit-identique (SHA-256 prefix `62875b42…`).
8. **persistence** round-trip via `plasticity.npz` (npz savez/load).
9. **invariance génétique** : `agents.intelligence` jamais mutée (hash SHA-256 inchangé après 500 events).

---

## Résultats numériques

```
==============================================================================
P41 — Wave 12 cognitive-plasticity smoke
==============================================================================
  [OK  ] install_plasticity idempotent + zero buffer
  [OK  ] non-cognitive actions are no-ops
  [OK  ] curiosity gating ratio (hi/lo) ≈ 3.0          ratio=3.00
  [OK  ] intelligence_effective clipped & buffer capped eff=1.0000 raw=1.5000
  [OK  ] decay_step halves buffer at factor 0.5         expected=actual
  [OK  ] power-law signature : effective ≠ base         top10 1.47→1.66
  [OK  ] determinism : two identical replays            hash_a == hash_b
  [OK  ] persistence round-trip (npz)                   80 events restored
  [OK  ] agent.intelligence untouched by plasticity     hash preserved
  RESULT : 9/9 PASS
==============================================================================
```

Journal d'audit : `runtime/journals/p41_cognitive_plasticity.jsonl`.

---

## Genesis Delta

| Métrique | Avant Wave 12 | Après Wave 12 (boosted) |
|---|---|---|
| `top10_median_ratio` (max culture) | 1.473 | **1.658** (+12.6 %) |
| `skill_proxy mean` (max culture) | 0.490 | **0.624** (+27.3 %) |
| `agents.intelligence` (génétique) | inchangée | inchangée (bit-identique) |
| Buffer learned_skill | absent | présent (zero par défaut) |
| Persistence world_library modules | 16 | **17** |
| Smoke tests | 40 (p0–p40) | **41 (+p41)** |
| Surfaces PQC | inchangée | inchangée |
| Innovation | observation passive de Hill α | feedback Hebbien actif → émergence de classes cognitives |

---

## Règles invariantes respectées

* ✅ Pas de rewrite d'`elite_metrics.compute_elite_metrics` (helper appendé, signature originale intacte).
* ✅ Émergence pure : aucun seuil scripté ; le buffer s'accumule par usage réel.
* ✅ Déterminisme : aucun PRNG appelé dans `cognitive_plasticity`. Buffer SHA-256 reproductible.
* ✅ CO2 baseline 280 ppm : module n'émet rien.
* ✅ Causalité immuable : `decay_step` *réduit* mais ne réécrit pas le passé ; un event consommé est consommé.
* ✅ Event-sourcing : `n_events_total` + `learned_skill` array suffisent à reconstruire l'état (persistance npz).
* ✅ Génétique préservée : `agents.intelligence` jamais mutée (hash invariant testé).

---

## Prochaine session candidate

* **W12 long-run** : 10 K sim-ans sur Léman, mesurer si `Hill α effective` descend vers la fourchette `[1.5, 3.0]` détectée comme plausible par `elite_metrics.detect_power_law`.
* **W12 wiring sim.step** : optionnel — câbler `record_experience` automatiquement dans `cognition.apply_decision` plutôt qu'à la main par le caller. À mesurer en coût per-tick avant de wirer.
* **W13 deep** : faire que `decision.decide` lise `intelligence_effective` plutôt que `intelligence` pour boucler le feedback (action → apprentissage → meilleure action).

---

## Fichiers touchés

```
A  runtime/engine/cognitive_plasticity.py      (+342 LOC)
M  runtime/engine/elite_metrics.py             (+62 LOC append-only)
M  runtime/engine/world_library.py             (+4 LOC, 1 entry)
A  runtime/scripts/p41_cognitive_plasticity_smoke.py  (+296 LOC)
A  docs/sprints/2026-05-16_WAVE12-COGNITIVE-PLASTICITY.md (this file)
M  NEXT-SPRINT.md                              (session 32 entry)
```
