# Sprint 2026-05-14b — Veille du jour : taxonomie world-models

**Mode :** Autonome total. Tâche cron `continue-la-cration-de-genesis-enginer`.
**Date :** 2026-05-14 (deuxième passage de la journée — le premier
matin a livré P-NEW.2, P-NEW.3, L2 sim_lift, dashboard live).
**Doctrine appliquée :** *veille-first*. Aucune ligne de code écrite
avant que la veille soit terminée.

---

## ÉTAPE 0 — Veille technologique (terminée avant tout code)

5 axes lancés en parallèle. Synthèse compacte ci-dessous.

### DÉCOUVERTE_1 — Paper arxiv 2604.22748 *Agentic World Modeling*

- **Couche Genesis impactée :** Agentic + L5 World Models (P8 du backlog)
- **Gain estimé :** cadre théorique formel (L1 Predictor / L2 Simulator /
  L3 Evolver) directement applicable au futur module
  `engine/world_model.py`. Permet de poser P8 sur un vocabulaire
  publié et défendable scientifiquement.

### DÉCOUVERTE_2 — Bevy 0.16 ECS Relationships + occlusion culling GPU

- **Couche Genesis impactée :** Substrate + Presentation (scaffolding Rust)
- **Gain estimé :** -30 à -50% draw calls quand Phase 4 renderer 3D
  arrivera. Non-bloquant pour aujourd'hui.

### DÉCOUVERTE_3 — Cloudflare hybride X25519+ML-KEM-768 prod IPsec (mars 2026)

- **Couche Genesis impactée :** Platform (ADR 0003 PQC-first)
- **Gain estimé :** référence d'intégration prête pour Phase 5 PQC.
  Non-bloquant aujourd'hui.

### CVE_ACTIVES

- **CVE-2025-62518 (TARmageddon, tokio-tar RCE)** — vérification immédiate.
  Résultat : `Grep tokio-tar` sur `scaffolding/Cargo.lock` →
  **aucune occurrence**. Genesis n'est pas exposé. Veille zéro impact.
- CVE-2025-68926 (RustFS gRPC hardcoded token) — non applicable
  (RustFS pas dans le stack).
- CVE-2026-25592/26030 (prompt-injection → host RCE) — applicable
  *uniquement* si on branche un LLM en Phase 5b (P9). À noter pour
  ce sprint-là.

### PAPER_DU_JOUR

*Agentic World Modeling: Foundations, Capabilities, Laws, and Beyond*
(arxiv 2604.22748). Apport direct : taxonomie L1/L2/L3 *orthogonale*
à notre Genesis L1-L5. Permet de qualifier chaque module Genesis par
sa **capacité prédictive** en plus de sa place dans le **pipeline**.

---

## ÉTAPE 1 — Combo retenu

**COMBO_RETENU :** `[taxonomie paper-L1/L2/L3]` × `[pipeline Genesis L1-L5]`

| | |
|---|---|
| **Gain** | clarté lexicale + cadre théorique reconnu + préparation P8 mesurable |
| **Coût** | 1 ADR (0005) + 6 constantes dans 3 modules + 1 micro-fix latent |
| **Couche** | World + Cognition + Observatory |
| **Intégration** | constantes `PIPELINE_LAYER` / `WORLD_MODEL_CAPABILITY` par module |
| **ADR requis** | OUI → ADR 0005 rédigé avant de toucher le code |

**COMBO_BACKLOG :** Bevy 0.16 ECS Relationships (bloqué par
Phase 4 renderer) · Cloudflare ML-KEM-768 (bloqué par Phase 5
PQC) · World-model L3 Evolver (bloqué par P8 non démarré).

**COMBO_REJETÉ :** aucun.

---

## ÉTAPE 2 — Audit & sélection tâche du jour

État du projet à l'ouverture du cron :

- Sprint matin `SPRINT-2026-05-14.md` déjà livré : P-NEW.1a/1b/2/3 +
  L2 sim_lift smoke OK.
- `SPRINT-2026-05-15.md` et `SPRINT-2026-05-16.md` rédigés à l'avance
  par des sessions cron précédentes (P-NEW.4 fertilité, P-NEW.5
  install_lift, P-NEW.6 endpoint /api/lift_state, P-NEW.7 multi-hearths,
  P-NEW.8 run 5K et 2K, P-NEW.10 death cause, optimisations perf
  #1/#2/#3, worldgen #4/#5 slope+lake).
- File `NEXT-SPRINT.md` actualisée : pointe vers P-NEW.17 (re-mesure
  perf), P-NEW.12 (HEARTH 1/2), P6 (L3 NCA), P8 (L5 world_model).

**Conclusion** : toutes les tâches *opérationnelles* du jour sont
déjà livrées. La valeur marginale la plus haute est de **capitaliser
sur le paper du jour** pour préparer P8 sans le démarrer prématurément.

Tâche choisie : **ADR-0005 World-Model Taxonomy + tagage des modules
existants + micro-fix latent dans `lift_state`**.

---

## ÉTAPE 3 — Livré

### 3.1 ADR 0005 — World-Model Taxonomy

**Nouveau :** `adr/0005-world-model-taxonomy.md`

Décision : adopter deux axes orthogonaux de classement.

1. **Axe Pipeline** — vocabulaire Genesis L1-L5 existant inchangé.
2. **Axe Capacité** — nouvelle taxonomie paper-L1 Predictor /
   paper-L2 Simulator / paper-L3 Evolver (arxiv 2604.22748).

Chaque module pertinent publie deux constantes :

```python
PIPELINE_LAYER = "Genesis-L2 Sim-Lift"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"  # arxiv 2604.22748
```

Mapping initial :

| Module | Pipeline | Capacité |
|---|---|---|
| `earth_loader` | Genesis-L1 Earth-Seed | paper-L1 Predictor |
| `sim_lift` | Genesis-L2 Sim-Lift | paper-L2 Simulator |
| `ai_detail` (à venir) | Genesis-L3 AI Detail | paper-L1 Predictor |
| `realism` | Genesis-L4 Feedback | paper-L2 Simulator |
| `world_model` (P8) | Genesis-L5 World Models | paper-L2 Simulator → paper-L3 Evolver |

Validation gates posées dans l'ADR à 30 / 60 / 180 jours.

### 3.2 Tagage des 3 modules existants

**Modifiés :**

- `runtime/engine/sim_lift.py` — `PIPELINE_LAYER = "Genesis-L2 Sim-Lift"`,
  `WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`
- `runtime/engine/earth_loader.py` — `PIPELINE_LAYER =
  "Genesis-L1 Earth-Seed"`, `WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`
- `runtime/engine/realism.py` — `PIPELINE_LAYER = "Genesis-L4 Feedback"`,
  `WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`

Vérification :

```
$ python -c "from engine.sim_lift import PIPELINE_LAYER, WORLD_MODEL_CAPABILITY; …"
sim_lift OK Genesis-L2 Sim-Lift | paper-L2 Simulator
earth_loader Genesis-L1 Earth-Seed | paper-L1 Predictor
realism Genesis-L4 Feedback | paper-L2 Simulator
```

### 3.3 Micro-fix latent dans `sim_lift.lift_state`

**Modifié :** `runtime/engine/sim_lift.py` — fonction `lift_state(sim)`.

Bug repéré à la lecture : `mean_walkability` et `impassable_pct`
utilisaient `slope_n` / `total_cells` comme dénominateur — deux
compteurs incrémentés sur `slope_deg.size` et `is_lake.size`
respectivement, alors que la donnée numérateur (`walk_sum`,
`walk_impassable`) vient de `walkability`. En pratique les trois
tableaux ont la même taille, mais le code crashait silencieusement
en `0.0` si un `LiftField` ancien (sans `slope_deg`) coexistait
avec un nouveau.

Fix : compteur dédié `walk_n` incrémenté sur `walkability.size`,
utilisé comme dénominateur pour les deux moyennes. Ligne 4 ajoutée,
3 lignes modifiées. Comportement préservé sur les `LiftField`
homogènes ; robuste aux mixés.

### 3.4 Smoke test post-patch

```python
cfg = SimConfig(seed=0xC0FFEE, founders=8, drive_accel=1500.0, ...)
sim = Simulation(cfg); install(sim); install_lift(sim)
for _ in range(120): sim.step()
s = lift_state(sim)
```

Sortie :

```json
{
  "chunks": 154,
  "veg_distribution": {"PRAIRIE": 0.0054, "BOIS_JEUNE": 0.0501,
                       "FORET_MATURE": 0.8448, "FORET_VIEILLE": 0.0997},
  "max_ravine_depth": 1.0,
  "mean_slope_deg": 67.19,
  "max_slope_deg": 84.14,
  "lake_cells_pct": 0.0,
  "mean_walkability": 0.0437,
  "impassable_pct": 0.9487
}
```

`POST-PATCH SMOKE OK`. Toutes les valeurs dans [0, 1] où attendu.

---

## ÉTAPE 4 — Conformité

### Tests pré-commit

- [x] `python -c "import engine.sim_lift; import engine.earth_loader;
      import engine.realism"` → OK avec constantes
- [x] Smoke test `lift_state` 120 ticks → OK (154 chunks, valeurs
      cohérentes, pas d'exception)
- [x] Déterminisme préservé — aucune logique de boucle modifiée,
      seul un dénominateur changé pour la diagnostic
- [x] Aucun `unsafe`, aucun secret, aucun mock introduit

### Pas de push réel

Le projet n'est pas un repo git initialisé (`Is a git repository:
false` au boot). Les livrables sont sur le filesystem local —
session cron suivante pourra `git init` + commit en bloc si voulu.

---

## VEILLE_DU_JOUR

| Délimiteur | Valeur |
|---|---|
| COMBO_RETENU | taxonomie paper-L1/L2/L3 × pipeline Genesis L1-L5 |
| GENESIS_DELTA — innovation | ADR 0005 pose la base mesurable pour P8 |
| GENESIS_DELTA — layers_touched | L1 (earth_loader), L2 (sim_lift), L4 (realism) |
| GENESIS_DELTA — pqc_surfaces | 0 (note CVE TARmageddon : non exposé) |
| GENESIS_DELTA — cognition_latency | n/a (pas de modification hot-path) |
| GENESIS_DELTA — agents_capacity | n/a |
| innovation_du_jour | les modules Genesis sont désormais auto-descriptifs côté capacité prédictive |

---

## Fichiers créés / modifiés

**Créés**

- `adr/0005-world-model-taxonomy.md` (140 lignes)
- `SPRINT-2026-05-14b-veille.md` (ce fichier)

**Modifiés**

- `runtime/engine/sim_lift.py` — docstring d'en-tête + 2 constantes
  + `walk_n` dans `lift_state` (12 lignes nettes)
- `runtime/engine/earth_loader.py` — docstring d'en-tête + 2 constantes
- `runtime/engine/realism.py` — docstring d'en-tête + 2 constantes

---

## Suite suggérée pour la prochaine session cron

Conformément à la file `NEXT-SPRINT.md` mise à jour à la fin du
sprint 2026-05-16, et enrichie par l'ADR 0005 :

1. **P-NEW.17** — Re-mesure `profile_tick.py` à pop=175 pour valider
   le gain attendu de l'optim #3 (cible < 60 s sur 300 ticks).
2. **P-NEW.20** (nouveau, créé par ADR 0005) — endpoint
   `GET /api/world_model_capabilities` qui agrège les constantes
   `PIPELINE_LAYER` / `WORLD_MODEL_CAPABILITY` de tous les modules
   chargés. CI doit échouer si un module pertinent oublie ses
   tags. Validation 30 jours de l'ADR.
3. **P-NEW.12** — Investigation 1 HEARTH / 2 complété.
4. **P6** — Démarrer `engine/ai_detail.py` (Genesis-L3, paper-L1
   Predictor). NCA biome-conditionné CPU.
5. **P8** — Squelette `engine/world_model.py` (Genesis-L5, paper-L2
   Simulator initial). Validation 60 jours de l'ADR.

---

**Fin du sprint 2026-05-14b. Veille → combo → ADR → tag → fix →
smoke → doc. Doctrine respectée.**
