# ADR 0008 — Frontière Python/Rust : `runtime/engine` est la couche de simulation active de l'ère *cargo-less*

- **Statut** : Accepted
- **Date** : 2026-06-15
- **Décideurs** : Lead Engineer (morning-routine auto, J+5 du delta-audit)
- **Suite de** : [ADR-0007](0007-d5-geology-orphan-resolution.md) (oracle de contrat géologie) ·
  ferme **BLIND-SPOTS R3** et la recommandation **R-J4-2 / §7** de
  [`AUDIT-DELTA-2026-06-14.md`](../native/world-engine/AUDIT-DELTA-2026-06-14.md)

## Contexte

Depuis Wave 42 (2026-05-11, intégration PyO3 / wheel `genesis_world`), **toute la
livraison passe par Python** :

- ~15 Waves d'observateurs read-only (Wave 43 → 63) ;
- 6 capacités agent (C1 `surface_mineralization` → C6 `limestone_outcrop`) ;
- **0 commit Rust** dans `native/world-engine/` (hors documents d'audit) en
  **29 jours** (`git log --since="2026-05-17" -- native/world-engine/ ':!*AUDIT*' ':!*BLIND*'`
  → vide).

La cause est structurelle et nommée **D7** : **`cargo`/`rustc` sont absents de
l'environnement d'exécution** (cf. memory `reference_env_no_cargo`). Aucune ligne
Rust ne peut être compilée, testée ou liée *ici* ; la CI reste la seule source de
vérité Rust. Conséquence cumulée, quantifiée par les delta-audits :

- **D4 (décorrélation score ↔ moteur)** — le score « réalisme » Python est passé
  de 75 à 78 sur la géologie en 4 jours, **sans qu'aucun voxel ne soit généré
  différemment** par le moteur Rust. Le score mesure aujourd'hui la **couche
  perception agent (Python)**, pas la qualité du monde produit (Rust).
- **D7 (vélocité asymétrique)** — ratio Python/Rust = **6/0** sur les capacités
  en 29 j. La crate `genesis-geology` reste dead-code, conservée comme **oracle
  de contrat lecture-seule** (ADR-0007).

Les trois derniers audits (`AUDIT-DELTA-2026-06-1{2,3,4}.md`,
`BLIND-SPOTS-AUDIT-2026-06-13.md`) escaladent la **même question non tranchée**
(BLIND-SPOTS R3, AUDIT J+4 §7) :

> À ce rythme (1 capacité/jour côté Python, 0 côté Rust), `runtime/engine/`
> devient *de facto* la couche de simulation principale. **Ne pas trancher la
> frontière revient à décider par défaut** que Python est la couche de
> simulation. C'est une décision lourde, non documentée — *« le plus grand
> silence stratégique du projet »*.

Cet ADR met fin au silence : il **nomme la frontière**, la rend **réversible
sous conditions explicites**, et corrige l'asymétrie d'honnêteté du score (R-J4-1).

## Décision

### 1. Couche de simulation active = `runtime/engine/` (Python, déterministe)

Pour **l'ère *cargo-less*** (tant que `cargo`/`rustc` ne sont pas dans
l'environnement de développement principal), `runtime/engine/` (numpy +
`prf_rng`, bit-déterministe) est **la couche de simulation et de perception agent
active** et la **source de vérité du comportement émergent** : cognition,
géologie de surface perçue, hydrologie, climat dérivé, capacités C1→Cn.

C'est un constat **assumé**, pas subi : la vélocité Python est réelle, testée
(513+ tests verts), et conforme à l'invariant d'émergence absolue.

### 2. `native/world-engine/` = substrat worldgen **gelé** + oracle de contrat

`native/world-engine/` (23 crates Rust) reste le **substrat de génération de
monde**, **gelé depuis Wave 42**. Le wheel `genesis_world` demeure le producteur
de chunks **quand il est présent** (pont réactivé le 2026-06-11,
`bridge_status() → {native: True, backend: "terrain"}`). La crate
`genesis-geology` reste **oracle de contrat lecture-seule** (ADR-0007), **non
câblée** dans `streaming::generate`.

Aucun item Phase A/B nécessitant `cargo` n'est **abandonné** — ils sont
**différés** à une session outillée (cf. §5), pas annulés.

### 3. Frontière = le contrat de *tells* géologie, durci par garde-fou D8

Le **seul** couplage Python↔Rust qui DOIT tenir sans `cargo` est le contrat de
palette « tell » géologie
(`runtime/tests/test_geology_cross_language_contract.py`). Il est, à cet ADR,
**durci par le garde-fou D8 (R-J4-3)** : tout matériau qu'une capacité
`*_outcrop` surface à un agent doit être **classé** (mappé `PY_TO_RUST` ou
explicitement waivé `PY_CATALOGUE_ONLY`), et tout nouveau fichier
`engine/*_outcrop.py` doit être **enregistré**. Le moratoire CONTRIBUTING.md
*« toute capacité enrichit le contrat »* passe ainsi de **règle sociale** à
**porte CI** : la divergence ne peut plus croître en silence, une capacité à la
fois.

### 4. Sémantique honnête du score (R-J4-1)

Le pourcentage « réalisme » **mesure la couche perception Python**, **pas** le
worldgen Rust. `PROJECT-STATUS.md` doit le **dire explicitement** pour qu'un
nouveau contributeur ne lise pas « 80 % » comme « le moteur Rust est à 80 % ».

### 5. Réversibilité — conditions de réactivation Rust

Cette frontière est **conditionnelle**, pas définitive. Le Rust redevient couche
co-équivalente / primaire dès qu'une **« session cargo »** (CI dédiée ou
toolchain locale) permet d'exécuter `cargo test --all-features` / `clippy -D
warnings` / `cargo audit`. Sont alors **réactivables** (ordre indicatif) :

- **R-J4-2** — promouvoir le contrat de *tells* de « parse texte » vers un binding
  compilé : `#[pyfunction] fn mineral_tells() -> Vec<(String,[u8;3])>` dans
  `crates/pybindings/`, consommé côté test via `from genesis_world import
  mineral_tells` (élimine F-D8-1, le parsing fragile) ;
- **D5-wiring** (ADR-0007 étape 2) — `geology::sample_at()` dans
  `Chunk::generate()` + hash dans le content-key worldgraph ;
- **Phase A** — A3 (spatial index `rstar`), A4 (raycast accéléré), A5 (GPU erosion
  auto-fallback) ; **Phase B** — B1→B8.

Tant que ces items ne sont pas verts en CI, **on ne prétend pas que le moteur
Rust sert la géologie / la simulation** (honnêteté ADR-0007).

## Conséquences

### Positives
- Le **plus grand silence stratégique** (BLIND-SPOTS R3) est levé : la frontière
  est nommée, datée, et la dérive « Python par défaut » devient un **choix
  documenté et réversible**.
- Le garde-fou D8 (R-J4-3) ferme **F-D8-2** : le moratoire devient technique. La
  prochaine capacité (C7) ne peut plus diverger du contrat sans casser le build.
- Le score réalisme cesse d'être ambigu : la ligne R-J4-1 dans `PROJECT-STATUS.md`
  distingue *couche perçue (Python)* de *couche générée (Rust)*.
- Les contributeurs Rust futurs ont une **porte claire** (la « session cargo »)
  et une **liste d'items réactivables** non perdus.

### Négatives
- On **assume** que, jusqu'à la session cargo, le moteur Rust ne progresse pas.
  La dette de câblage (ADR-0007 étape 2) et Phase A/B **reste due** — seule sa
  *nature* change (différée explicitement, plus « stagnante en silence »).
- Le contrat reste vérifié par **parsing texte** du Rust (F-D8-1) jusqu'à R-J4-2 ;
  un refactor Rust changeant la *forme* (macro `enum_dispatch`) casserait le
  parse sans casser le contrat. Mitigation : R-J4-2 listé §5, échéance « session
  cargo ».
- Risque de **lock-in perception** : à mesure que Python s'enrichit, recâbler le
  Rust coûte plus cher. Atténué par le contrat de *tells* (la palette reste un
  point de jonction stable et testé).

## Alternatives considérées

- **Câbler le Rust maintenant.** Impossible/dangereux : `cargo` absent → on
  pousserait du Rust non compilé, violant *« tests avant commit »* (même
  raisonnement qu'ADR-0007).
- **Archiver `native/world-engine/`.** Rejeté : perd 23 crates et le futur GPU
  worldgen ; et le pont natif `terrain` **fonctionne** (réactivé 2026-06-11).
- **Statu quo (ne pas décider).** Rejeté : c'est *décider par défaut* que Python
  est la simulation, sans le dire — exactement le silence que 3 audits flèchent
  comme inacceptable.
- **Geler C7 jusqu'à une session cargo.** Rejeté : pénalise la seule vélocité
  réelle du projet sans rien débloquer côté Rust ; le garde-fou D8 rend C7 sûre.

## Validation

- **Immédiat** : `pytest runtime/tests/test_geology_cross_language_contract.py`
  vert, incluant les **3 nouveaux tests D8** (registre des capacités, tells tous
  classés, ensembles disjoints/réels/vivants). ✅ à la date de l'ADR.
- **Continu** : ajouter `engine/<x>_outcrop.py` sans l'enregistrer **casse le
  build** → la frontière (le contrat de tells) est défendue par CI.
- **Échéance § réversibilité** : à la première **session cargo**, exécuter R-J4-2
  (binding `mineral_tells`) puis D5-wiring ; tant que `cargo test -p
  genesis-streaming` ne montre pas `geology::sample_at` appelé, **ne pas prétendre
  que le moteur Rust sert la simulation**.
