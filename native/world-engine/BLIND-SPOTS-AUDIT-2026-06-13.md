# Genesis World Engine — Audit "Angles morts" 2026-06-13 (soir)

**Mode :** scheduled task `analyse-le-projet-regarde-si-il-y-a-des-amelioration`, run du soir.
**Statut :** **complément**, pas substitut, de [`NEXT-LEVEL-AUDIT.md`](./NEXT-LEVEL-AUDIT.md) (2026-05-16, 503 lignes) et du delta J+3 [`AUDIT-DELTA-2026-06-13.md`](./AUDIT-DELTA-2026-06-13.md) (matin).
**Contrainte env :** `cargo` absent — Rust = lecture seule.

---

## 0. Pourquoi ce document existe

L'audit "next-level" est **valide, exhaustif sur sa portée, et déjà cité 4 fois** par les delta J+0…J+3. Le rejouer en boucle est du gaspillage. Le vrai gap n'est plus *analytique* — c'est *exécutif* (D7) **et** *de cadrage* : l'audit du 16/05 a 6 angles morts non couverts qui sont devenus pertinents en 28 jours.

Ce document n'ouvre pas un nouveau Phase A/B/C. Il liste **uniquement** ce que l'audit existant rate ou n'a pas vu, avec une recommandation par item.

---

## 1. Angles morts non couverts par NEXT-LEVEL-AUDIT.md

### M1 — La crate `genesis-geology` n'existe pas dans NEXT-LEVEL-AUDIT

Vérifié : `grep -c "genesis-geology" NEXT-LEVEL-AUDIT.md` → **0**. Pourtant :
- Wave 43 (2026-05-28) a créé la crate (1095 lignes, palette RGB, minéraux, roches, chimie).
- Wave 44 a ajouté un canal olfactif (chimie + vent).
- J+28 plus tard, elle reste **dead-code Rust** (référencée par 0 autre `Cargo.toml`, cf. grep des Cargo.toml ce soir : seule sa propre `name = "genesis-geology"` matche).
- ADR-0007 (J+3 matin) tranche : conservée comme **oracle de contrat** lu par un test Python, câblage moteur reporté CI.

**Conséquence pour l'audit :** la section §1.1 « Inventaire des crates » (15 crates) est obsolète depuis Wave 43 → **23 crates** aujourd'hui, dont 4 (`geology`, `weather`, `physics`, `laws`) **non listées** dans l'audit. L'évaluation "✅/⚠/❌" de chacune n'a jamais été produite.

**Recommandation R1 :** étendre la matrice d'inventaire NEXT-LEVEL-AUDIT.md §1.1 aux **8 crates ajoutées hors audit** (`geology`, `weather`, `physics`, `laws`, `intent`, `mesh`, `studio`, `macro-bridge`). Critère : un mainteneur doit pouvoir dire en 30 s "active / dormant / orpheline" pour chacune. Aujourd'hui c'est impossible sans lire les sources.

### M2 — Le canal olfactif n'a jamais été audité

L'audit traite voxel/SDF/vision (axes 1, 4, 5). Il ne mentionne **jamais** :
- L'olfaction (Wave 44 : signaux chimiques + vent).
- L'audition (qui devra exister pour la chasse, l'alerte, la communication animale).
- La perception multi-modale en général.

Pourtant l'invariant racine du projet (cf. `feedback_no_scripting`, `[[water_potability]]`) est **"le monde ne ment jamais"** — donc chaque canal sensoriel ajouté doit être déterministe, perceptible localement et sans cheat. C'est un axe à part entière, manquant.

**Recommandation R2 :** ajouter un **Axe 7 — Perception multimodale** au schéma §5. Inclure : (a) propagation sonore (atténuation par densité bloc + obstacle), (b) canal chimique déjà existant à formaliser, (c) thermique perceptible (signal IR à courte portée, utile herbivores nocturnes). Stub `proposals/axis7_perception/`.

### M3 — La frontière Python/Rust n'est jamais arbitrée

L'audit traite "le moteur" comme la **stack Rust**. Mais en 28 jours :
- **0 ligne mergée** côté Rust contre les items Phase A/B.
- **3 capacités complètes** (lithic outcrop, water potability, combustible outcrop) livrées côté **Python** (`runtime/engine/`), avec leurs propres palettes, leurs tests, leurs invariants.

C'est documenté dans les delta-audits comme "pattern D6" mais l'audit "next-level" ne pose **jamais** la question : *quelle est la frontière correcte entre `native/world-engine/crates/` et `runtime/engine/` ?* Aujourd'hui :
- Rust = source de vérité voxel/heightmap/biome.
- Python = source de vérité **toutes les nouvelles capacités émergentes**.
- Le test cross-language (J+3) gèle la divergence côté palettes, **pas** côté logique.

**Recommandation R3 :** ouvrir un ADR-0008 (frontière Python/Rust) listant : (i) ce qui DOIT vivre côté Rust (déterminisme bit-exact, perf chunk-gen, mémoire), (ii) ce qui PEUT vivre côté Python (capacités émergentes, scoring, observateurs paresseux), (iii) le critère de migration Python→Rust (e.g. "≥ N % CPU dans le hot loop"). Sans cette frontière nommée, le pattern D6 va se répéter à chaque capacité C5, C6, C7.

### M4 — `pybindings` n'est jamais examinée

L'audit cite la crate (§1.1 : « pas lue en détail ») et ne revient jamais dessus. Or :
- C'est le **seul pont vivant** entre les capacités Python livrées et les 23 crates Rust.
- Le `wheel genesis_world` (cf. memory `project_wave42_rust_integration.md`) est installé, donc le pont existe.
- Mais aucune des capacités C1–C4 (Python) ne traverse `pybindings` : elles dérivent toutes de `engine.geology.chunk_geology` (Python pur).

**Conséquence :** `pybindings` est *fonctionnelle* mais *contournée*. Le grep de la session J+3 confirme : 3 sessions, 3 capacités, 0 nouveau symbole exporté côté `pybindings`.

**Recommandation R4 :** auditer `pybindings/src/lib.rs` pour mesurer la **largeur** de l'API exposée à Python aujourd'hui (combien de fonctions ? lesquelles sont appelées par `runtime/engine/` ?), et compléter avec ce que les capacités Python attendraient. Item Phase A bis (« A8 — `pybindings` coverage audit »).

### M5 — Pas de stratégie pour le mode `cargo-less` (D7)

L'audit suppose implicitement un environnement de dev complet. La réalité documentée (cf. `reference_env_no_cargo` en memory, et §0 de tous les delta-audits) :
- L'environnement de production de cette automation est **Python 3.14 seul**.
- `cargo` / `rustc` ne sont **pas installables ici** — le CI est seule source de vérité Rust.
- Sur 28 jours, ça a produit une **vélocité asymétrique** : Python = 3 capacités, Rust = 2 items Phase A.

C'est le **vrai bloqueur** du roadmap. Et il n'est pas dans NEXT-LEVEL-AUDIT.

**Recommandation R5 — la plus importante de ce document :** trancher la **stratégie de déblocage D7**. Trois options :
- (a) **Session cargo dédiée** : un humain provisionne un poste avec `cargo`, exécute une session focalisée Phase A (`A1` mergé, reste : `A3 spatial_index rstar`, `A4 raycast chunk-aware`, `A5 GPU erosion wiring`). Coût : 1 journée humain. Débloque ≥ 3 items.
- (b) **Bot CI auto-merge sur PR draft** : ouvrir un PR draft contenant `proposals/axis*/spatial_index.rs` → `crates/agent-api/src/`, laisser le CI compiler. Si vert, auto-promote. Coût : config CI (1 jour).
- (c) **Acter** que Phase A Rust est gelée et basculer le roadmap moteur sur **Python first** pour 90 jours, en assumant. Coût : 0. Risque : la divergence Python/Rust devient permanente.

À J+28 sans option choisie, l'inaction = option (c) par défaut. Le **dire** est plus honnête que de continuer à incrémenter J+N.

### M6 — Métriques "cibles" §7 jamais mesurées

L'audit §7 fixe 11 métriques cibles (chunk gen p50, cache hit rate, spatial index < 100 µs…). **Aucune** n'a de baseline mergée en 28 jours. Le `BENCHMARKS.md` existe mais le delta-audit J+3 ne le cite plus. Conséquence : on ne peut pas prouver que la roadmap fait *avancer* une métrique — uniquement qu'elle livre des items.

**Recommandation R6 :** publier une **dashboard métrique unique** (1 fichier `METRICS.md`, mis à jour à chaque commit Rust, vide pour l'instant), avec colonnes : `cible | baseline | actuel | delta | date`. Tant qu'elle est vide, ne pas affirmer "perf améliorée" dans les commit messages.

---

## 2. Ce que ce document **ne** dit pas

- Il ne re-priorise pas Phase A/B/C. La priorisation de l'audit du 16/05 reste correcte.
- Il ne propose pas de nouveau stub Rust. Les 14 stubs `proposals/axis*/` sont **toujours valides** et **toujours non mergés**.
- Il ne dit pas que l'audit du 16/05 est "à jeter". Au contraire : c'est la référence, à patcher sur 6 points.

---

## 3. Action minimum proposée pour J+4 (2026-06-14)

Une seule décision compte demain matin : **trancher M5 (option a / b / c).** Tout le reste (M1-M4, M6) est de la documentation patchable en arrière-plan. La décision M5 est ce qui transforme ou non le mois prochain en "Phase A mergée" vs "Phase A J+58".

Si personne ne tranche M5 d'ici J+5, ce document recommande d'**acter (c) par défaut** dans CONTRIBUTING.md, et de reformuler la roadmap moteur comme "Python first + Rust read-only oracle" — au moins ce sera honnête.

---

## 4. Fichier livré

```
créé :   native/world-engine/BLIND-SPOTS-AUDIT-2026-06-13.md  (ce document)
modifié : aucun
```

Aucun stub, aucun commit code. Document de cadrage stratégique pur.
