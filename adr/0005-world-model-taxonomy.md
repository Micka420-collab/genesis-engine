# ADR 0005 — World-Model Taxonomy (alignement avec arxiv 2604.22748)

- **Statut** : Proposed
- **Date** : 2026-05-14
- **Décideurs** : architecture cognition + world (veille auto)

## Contexte

La veille technologique du 2026-05-14 (matin, cron auto) a fait remonter le
paper *« Agentic World Modeling: Foundations, Capabilities, Laws, and
Beyond »* (arxiv 2604.22748) qui propose une taxonomie pratique des
modèles d'environnement utilisables par un agent autonome :

- **paper-L1 Predictor** — apprend un opérateur de transition one-step
  local. Étant donné `(s_t, a_t)`, prédit `s_{t+1}` ou une distribution
  sur lui. Pas de composition multi-step. Pas d'auto-révision.
- **paper-L2 Simulator** — compose les transitions L1 en rollouts
  multi-step, action-conditionnés, respectant les *lois* du domaine.
  Permet le planning par imagination.
- **paper-L3 Evolver** — révise *son propre* modèle quand ses prédictions
  divergent de l'évidence. Apprentissage continu en monde ouvert.

Genesis Engine a déjà son propre vocabulaire **Genesis-L1 → Genesis-L5**
documenté dans `PHASE5G-HYBRID-WORLDGEN.md` et `SPRINT-2026-05-14.md` :

| Genesis-Layer | Rôle | État au 2026-05-14 |
|---|---|---|
| Genesis-L1 Earth-Seed | DEM Copernicus + ESA WorldCover via /vsis3 | ✅ actif (492/492 hits) |
| Genesis-L2 Sim-Lift | Succession végétale + érosion foot-traffic | ✅ actif |
| Genesis-L3 AI Detail | NCA biome-conditionné, inférence CPU | ⏳ R&D |
| Genesis-L4 Feedback | Construction + atmosphère + invention → monde | 🟢 partiel |
| Genesis-L5 World Models | DreamerV3 par culture | ⏳ R&D (P8 du backlog) |

Les deux taxonomies sont **orthogonales** et coexistent :

- Genesis L1-L5 répond à *« d'où vient l'état du monde ? »*
- arxiv L1/L2/L3 répond à *« quelle capacité prédictive ce module offre-t-il
  à un agent qui veut planifier ? »*

Le risque concret est la confusion future quand on attaquera P8
(`engine/world_model.py`) qui est *à la fois* Genesis-L5 *et* doit
naître paper-L2 Simulator pour viser paper-L3 Evolver. Sans
disambiguation explicite, le code et la doc vont mélanger les deux.

## Décision

Adopter **deux axes de classement explicites** dans la documentation
et le code de Genesis :

### Axe 1 — Pipeline (Genesis L1-L5)

Inchangé. Décrit *d'où vient l'état du monde*. Vocabulaire conservé
tel qu'utilisé dans tous les documents existants.

### Axe 2 — Capacité (arxiv-paper L1/L2/L3)

Nouvel axe orthogonal. Décrit *ce qu'un module fournit à un agent*.

### Convention de code

Chaque module pertinent publie deux constantes en tête, immédiatement
après la docstring :

```python
# engine/sim_lift.py
PIPELINE_LAYER = "Genesis-L2 Sim-Lift"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"  # arxiv 2604.22748
```

Les valeurs autorisées pour `WORLD_MODEL_CAPABILITY` sont **exactement** :
`"paper-L1 Predictor"`, `"paper-L2 Simulator"`, `"paper-L3 Evolver"`,
ou `"n/a"` si non pertinent. Un module peut être tagué `"paper-L2
Simulator → paper-L3 Evolver"` si la trajectoire de feature est
publiquement engagée (cas de `world_model.py` P8).

### Mapping initial (2026-05-14)

| Module Genesis | Pipeline | Capacité (paper) | Justification |
|---|---|---|---|
| `earth_loader` | Genesis-L1 Earth-Seed | paper-L1 Predictor | Lookup `pos → biome/elev/water`. Pas de rollout. |
| `sim_lift` | Genesis-L2 Sim-Lift | paper-L2 Simulator | Markov succession 5-states + érosion par tick. Multi-step. Lois biophysiques. |
| `ai_detail` (à venir) | Genesis-L3 AI Detail | paper-L1 Predictor | NCA conditionné biome. One-step détail. |
| `realism` | Genesis-L4 Feedback | paper-L2 Simulator | Hydrologie + saisons + wildlife — rollouts multi-tick. |
| `physiology` (Wave 3) | Genesis-L4 Feedback | paper-L2 Simulator | Excrétion, hygiène, peau, pathogènes contagieux. Logistique non-linéaire. |
| `photosynthesis` (Wave 4) | Genesis-L4 Feedback | paper-L2 Simulator | Farquhar-von Caemmerer-Berry C3/C4/CAM. Lit Ca, PAR, T → kcal/cell/tick. |
| `material_aging` (Wave 4) | Genesis-L4 Feedback | paper-L1 Predictor | Corrosion / rot / fatigue per-instance. One-step decay par tick. |
| `marine` (Wave 5, P5) | Genesis-L4 Feedback | paper-L2 Simulator | Courants, marées M2, plancton → poisson → prédateur. Rollouts multi-tick. |
| `global_world` (Phase 15, P3) | Genesis-L4 Feedback | paper-L2 Simulator | Atmosphère + horloge + migration partagées entre N régions. Rollouts CO2 multi-régions respectent la conservation de masse. |
| `world_model` (P8) | Genesis-L5 World Models | paper-L2 Simulator → paper-L3 Evolver | DreamerV3 par culture. Naissance en Simulator pur ; cible Evolver. |

### Endpoint d'observation

Un futur endpoint **`GET /api/world_model_capabilities`** agrège la
table ci-dessus à partir des modules chargés. C'est testable en CI :
chaque module doit déclarer ses deux constantes ou échouer
explicitement le linter. Voir tâche **P-NEW.20** dans la file
post-sprint.

## Conséquences

### Positives

- Clarté lexicale : la collision « L1 Genesis » vs « L1 paper » est
  résolue par préfixage systématique.
- Cadre théorique reconnu : la capacité de chaque module est posée
  dans un vocabulaire publié et défendable scientifiquement.
- Préparation P8 : la cible Evolver est explicite et mesurable —
  on saura quand le module y est arrivé (révision active du
  rollout quand prédiction ≠ évidence sur N derniers ticks).
- Génération automatique de doc : `/api/world_model_capabilities`
  rend la table auto-actualisée, plus de drift entre code et ADR.

### Négatives

- Deux constantes de plus à maintenir par module concerné (faible
  surface, ~5 modules à terme).
- Risque de cargo-cult : taguer un module « Simulator » sans
  vérifier que les *lois* du domaine sont effectivement respectées.
  Atténué par : le critère de validation 60-jours ci-dessous.

## Alternatives considérées

- **Renommer la taxonomie Genesis L1-L5** pour éviter la collision —
  rejeté : trop disruptif, le vocabulaire L1-L5 est déjà fixé dans
  6 documents (`PHASE5G`, `SPRINT-2026-05-13/14/15/16`,
  `FUTURE-VISION`) et 4 modules.
- **Ignorer le paper** — rejeté : on perd l'opportunité de poser P8
  sur un cadre déjà validé par la communauté ; et la veille auto
  est censée fournir précisément ce type d'apport.
- **Une seule constante combinée** (ex. `LAYER = "Genesis-L2 /
  paper-L2"`) — rejeté : nuit à la machine-parseability et à la
  génération automatique du tableau de couverture.

## Validation

- **30 jours (cible 2026-06-13)** : P-NEW.20 livré — endpoint
  `/api/world_model_capabilities` actif, retourne la table de
  mapping construite à partir des constantes effectivement
  déclarées dans les modules.
- **60 jours (cible 2026-07-13)** : squelette `engine/world_model.py`
  posé (P8 du backlog). Cible test : 1 rollout 50-step imaginé vs
  ground-truth → écart < 30% sur food/water/wood. Tagué
  `WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`.
- **180 jours (cible 2026-11-13)** : `world_model.py` promu paper-L3
  Evolver. Critère opérationnel : sur un changement de régime
  (déforestation déclenchée par construction de masse, ou
  sécheresse atmosphérique), le modèle doit auto-corriger son
  rollout en < 200 nouveaux samples observés, mesurable via
  l'erreur de prédiction tick-to-tick avant/après la perturbation.

## Références

- arxiv 2604.22748 — *Agentic World Modeling: Foundations,
  Capabilities, Laws, and Beyond*.
- `docs/04-world-engine.md` — pipeline Genesis L1-L5.
- `PHASE5G-HYBRID-WORLDGEN.md` — choix de combiner Genesis-L1+L4.
- ADR 0002 — *Pas de LLM frontier comme cerveau*. Cohérent : on
  reste sur Simulator/Evolver internes (DreamerV3), pas LLM externes.
- `SPRINT-2026-05-14b-veille.md` — sprint qui a produit cet ADR.
