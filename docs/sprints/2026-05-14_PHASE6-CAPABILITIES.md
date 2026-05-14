# SPRINT 2026-05-14 — P-NEW.20 World-model capabilities endpoint

**Priorité attaquée**: P-NEW.20 (issue de la veille `2026-05-14b` → ADR-0005)
**Statut**: ✅ livré
**Cible ADR-0005 horizon 30j (2026-06-13)**: ATTEINTE.

---

## Contexte

L'ADR-0005 introduit deux axes orthogonaux de classement des modules
world-model :

- **Axe 1 — Pipeline** : `Genesis-L1` → `Genesis-L5` (d'où vient l'état du monde).
- **Axe 2 — Capability** : `paper-L1 Predictor` / `paper-L2 Simulator` /
  `paper-L3 Evolver` (arxiv 2604.22748 — capacité prédictive offerte à
  l'agent qui planifie).

Trois modules portaient déjà leurs constantes (`earth_loader`, `sim_lift`,
`realism`). Manquait l'agrégateur, l'endpoint, le HUD, et la garde CI
exigée par ADR-0005 (« Un linter CI : un module pertinent qui oublie ses
tags doit échouer la build »).

---

## Livrables

| Fichier | Rôle |
|---|---|
| `runtime/engine/world_model_capabilities.py` | Agrégateur introspectif des constantes des modules layer. Fournit `world_model_capabilities()` (table API-ready) et `audit_modules(strict=False)` (hook CI). |
| `runtime/engine/dashboard.py` (patch) | Nouvel endpoint `GET /api/world_model_capabilities` + import best-effort de l'agrégateur. |
| `runtime/engine/god_view_v2.html` (patch) | Section « WORLD-MODEL CAPABILITIES » dans le panneau `#observatory-panel` — pollée toutes les 3 s avec les 4 autres endpoints. Code-couleur (vert = tagué, gris = R&D, rouge = manquant/invalide). |
| `runtime/scripts/p18_capabilities_lint.py` | Linter CLI. Exit code 0 si tous les modules requis (`earth_loader`, `sim_lift`, `realism`) sont taggés avec une valeur allow-listée. Exit 1 sur violation, 2 sur erreur interne. Flag `--strict` étend la garde aux modules R&D présents mais sans tag. |
| `.github/workflows/capabilities-lint.yml` | Workflow GitHub Actions : déclenchement sur changement de `runtime/engine/*.py` ou de l'ADR. Job `audit` lance le linter sur Python 3.12 + numpy. |

---

## Validation

### Smoke unitaire de l'agrégateur

```
strict=False  required-tagged=3  missing=2  untagged=0  invalid=0
  OK engine.earth_loader               Genesis-L1 Earth-Seed         paper-L1 Predictor
  OK engine.sim_lift                   Genesis-L2 Sim-Lift           paper-L2 Simulator
  OK engine.realism                    Genesis-L4 Feedback           paper-L2 Simulator
  -- engine.ai_detail                  (R&D — not yet shipped)
  -- engine.world_model                (R&D — not yet shipped)

OK — all required modules carry valid ADR-0005 tags.
```

### Fail-cases du linter (vérifiés en mémoire)

- **PASS** — drop `PIPELINE_LAYER`/`WORLD_MODEL_CAPABILITY` sur `sim_lift`
  → `audit_modules` lève le drapeau `untagged` et `failures` est non-vide.
- **PASS** — set `WORLD_MODEL_CAPABILITY="bogus"` sur `sim_lift`
  → `audit_modules` retourne `invalid_capability`, échec déclenché.
- **PASS** — restoration → table reverte à 3/3 tagged sans failures.

### Smoke live de l'endpoint

```
GET http://127.0.0.1:8781/api/world_model_capabilities
HTTP/1.1 200 OK
{
  "axes": {"pipeline": "...", "capability": "..."},
  "modules": [5 rows],
  "summary": {"tagged": 3, "missing": 2, "untagged": 0, "invalid": 0},
  "adr": "0005"
}
```

Latence : <5 ms. Importation lazy : le dashboard reste compatible si
l'agrégateur disparaît (fallback `{}`).

### HUD

Le panneau `#observatory-panel` (top-left, 250 px de large) affiche une
sous-section sous "TOP PROGENITORS" :

```
WORLD-MODEL CAPABILITIES
● earth_loader
  L1 Earth-Seed · L1 Predictor
● sim_lift
  L2 Sim-Lift · L2 Simulator
● realism
  L4 Feedback · L2 Simulator
○ ai_detail (R&D)
○ world_model (R&D)
tagged 3 · ADR-0005
```

Tooltip affiche le `error` complet sur hover.

---

## Conséquences

### Positives

- ADR-0005 horizon 30 jours (cible 2026-06-13) : **atteint en J0**.
- Tout futur module Genesis-L* qui oubliera ses tags **fera échouer la
  build**, garantissant que la table reste auto-actualisée et fidèle.
- Le widget HUD documente le pipeline en live pour tout observateur du
  dashboard — utile pour démos « god mode ».
- `audit_modules(strict=True)` est prêt pour la prochaine échéance
  (60 jours — squelette `world_model.py` posé) : il suffira de basculer
  le flag dans le workflow quand `ai_detail`/`world_model` seront en
  scaffolding.

### Négatives

- Le workflow CI consomme un job par push sur `runtime/engine/**` —
  négligeable, le linter prend <1 s.
- Un module qui *importe* mais lève à l'import-time fera apparaître un
  faux `missing` plutôt qu'un `untagged`. Acceptable : on veut savoir.

---

## Fichiers touchés

```
runtime/engine/world_model_capabilities.py     (nouveau, 175 LOC)
runtime/engine/dashboard.py                    (+8 LOC, 1 endpoint)
runtime/engine/god_view_v2.html                (+50 LOC, 1 widget)
runtime/scripts/p18_capabilities_lint.py       (nouveau, 75 LOC)
.github/workflows/capabilities-lint.yml        (nouveau)
docs/sprints/2026-05-14_PHASE6-CAPABILITIES.md (ce fichier)
NEXT-SPRINT.md                                 (P-NEW.20 → archivé)
```

---

## État restant

- P-NEW.17 (re-measure profile_tick après optim #3) — prochain candidat.
- P-NEW.18 (cache invalidation explicite sur chunk writes) — backlog.
- P6 (`ai_detail.py` NCA) — R&D, déclenchera la 2e cible ADR-0005 (60j).
- P8 (`world_model.py` DreamerV3) — R&D, cible 60j + 180j d'ADR-0005.

---

## Référence

- ADR-0005 — `adr/0005-world-model-taxonomy.md`
- Veille source — `docs/sprints/2026-05-14_SPRINT-b-veille.md`
- Vision — `FUTURE-VISION.md` Pilier 1 « Bases du monde réel ».
