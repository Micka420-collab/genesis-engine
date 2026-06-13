# ADR 0007 — Résolution du géologie-orphelin (D5) : contrat cross-langage avant câblage

- **Statut** : Accepted
- **Date** : 2026-06-13
- **Décideurs** : Lead Engineer (morning-routine auto, J+3 du delta-audit)

## Contexte

Les delta-audits moteur des 2026-06-10 → 2026-06-12
(`native/world-engine/AUDIT-DELTA-2026-06-1{0,1,2}.md`) ont escaladé deux
risques liés et restés **non tranchés** trois jours de suite :

- **D5 — `genesis-geology` orphelin.** La crate Rust
  `native/world-engine/crates/geology` (1095 lignes : `mineral.rs`, `rock.rs`,
  `chemical.rs`, `visual.rs`) n'est importée par **personne** hors
  auto-référence. C'est le plus gros poste de dette latente du moteur.
- **D6 — double source de vérité géologie.** Trois sessions consécutives, trois
  capacités émergentes (C1 `surface_mineralization`, C2 `lithic_outcrop`,
  C3 `water_potability`) dérivent leur signal de `engine.geology` /
  `engine.mineral_catalog` (**réimplémentation Python**) — jamais de la crate
  Rust. Le couplage minéraux ↔ palette « tell » est de fait *un protocole non
  documenté* : *« sans test cross-langage, rien ne le garantit »* (§3.3).

La procédure de l'audit fixait au **J+3 (= aujourd'hui)** la **décision D5** :
option (a) promouvoir la crate (câbler dans `streaming::generate` + exposer la
palette via `pybindings`, ~2 j) **ou** option (b) archiver formellement (~1 h).
**Cap. C4 est interdite par contrat tant que D5 n'est pas tranché.**

Force déterminante du contexte d'exécution : **`cargo`/`rustc` sont absents de
l'environnement** (risque structurel D7 — vélocité Rust = 0 sur 27 j). Le
câblage Rust complet de l'option (a) **ne peut être ni écrit ni vérifié ici** ;
la CI reste la seule source de vérité Rust.

## Décision

**Option (a) retenue — on NE PAS archive `genesis-geology` — mais scindée en
deux étapes pour respecter la contrainte `cargo`-absent :**

1. **Verrou de contrat — fait aujourd'hui, vérifiable sans toolchain.**
   La crate Rust devient un **oracle lecture-seule** : un test Python
   (`runtime/tests/test_geology_cross_language_contract.py`) parse
   `crates/geology/src/mineral.rs` et **fige le contrat D6** —
   - identité de l'enum `Mineral` (16 variantes + `MINERAL_COUNT`) ;
   - chaque minéral « tell » du runtime Python live mappe vers une variante
     Rust réelle (`PY_TO_RUST`), nom vérifié des deux côtés ;
   - le **tell cuivre/malachite** `(80,140,70)` reste byte-exact entre
     `surface_mineralization` et `Mineral::Malachite::surface_color()` ;
   - le contrat intra-Python sel (croûte C1 == saumure C3) est exécuté.
   Toute dérive d'un côté **casse le build**. La divergence linéaire que D6
   redoutait (§3.3 : ~4000 lignes à C10 sans garde) est désormais impossible.

2. **Câblage moteur — déféré à une session `cargo`/CI.** Ajout dep dans
   `crates/streaming/Cargo.toml`, appel `geology::sample_at()` dans
   `Chunk::generate()`, hash dans le content-key worldgraph, exposition palette
   via `pybindings`. Reste un item **Phase A** ouvert (cf. ROADMAP), à exécuter
   par feature + cycle CI complet quand un dev `cargo` est disponible.

**Pourquoi (a) et pas (b) :** la vélocité observée (3 capacités en 3 sessions)
rend très probable C4–C7 dans le mois ; archiver gaspillerait 1095 lignes et le
besoin futur d'une palette servie côté GPU (debug overlay coloré). Refermer la
divergence **maintenant** coûte ~0 (le test), refermer à C10 coûterait une
semaine.

**Levée conditionnelle du moratoire C4 :** la barrière « C4 interdite » existait
pour empêcher D6 de devenir permanent *sans garde*. Le verrou de contrat (étape 1)
est précisément cette garde. **Cap. C4 redevient autorisée** dès lors que :
(i) ce test est vert en CI, **et** (ii) toute nouvelle capacité ajoute son
minéral-tell à `PY_TO_RUST` (ou le justifie dans `RUST_ONLY`). Le câblage Rust
(étape 2) **n'est plus un bloqueur** de C4 — il reste un item Phase A à part.

## Conséquences

### Positives
- D6 passe de *« protocole non documenté »* à *« contrat CI-enforced »* sans
  attendre `cargo`. Le risque #1 du moteur est neutralisé aujourd'hui.
- D5 cesse de stagner : décision prise et datée, crate conservée avec un rôle
  actif (oracle de contrat) au lieu d'être dead-code pur.
- Le moratoire est levé **par garde**, pas par renoncement : la prochaine
  capacité doit enrichir le contrat, donc la dette ne peut plus croître en
  silence.

### Négatives
- Le contrat est vérifié par **parsing texte** du Rust, pas par binding compilé :
  un refactor Rust qui changerait la *sémantique* sans changer les noms/couleurs
  ne serait pas attrapé. Mitigation : le test fige aussi `MINERAL_COUNT` et la
  complétude de la palette.
- L'étape 2 (vrai câblage) reste due ; la palette Rust n'alimente toujours pas
  le rendu. La dette de câblage existe encore — seule la dette de *divergence*
  est fermée.

## Alternatives considérées

- **Option (b) — archiver `genesis-geology`.** Rejetée : gaspille 1095 lignes,
  perd le futur overlay GPU, et la vélocité Python plaide pour C4–C7 imminents.
- **Câbler le Rust ici, sans CI.** Impossible/dangereux : `cargo` absent, on
  pousserait du Rust non compilé → viole la discipline « tests avant commit ».
- **Statu quo (ne rien décider).** C'est exactement la stagnation J+1→J+2 que
  l'audit a fléchée comme inacceptable.

## Validation

- **Immédiat** : `pytest runtime/tests/test_geology_cross_language_contract.py`
  vert (7/7) et inclus dans la suite (448/448). ✅ à la date de l'ADR.
- **Continu** : le test casse si l'enum Rust ou la palette Python dérivent —
  signal observable en CI à chaque push.
- **Échéance étape 2** : item Phase A « D5-wiring » dans ROADMAP ; bon si, à la
  prochaine session `cargo`, `cargo test -p genesis-streaming` montre
  `geology::sample_at` appelé dans `Chunk::generate` + un test
  `geology_pass_deterministic` vert. **Tant que non fait, ne pas prétendre que
  le moteur Rust sert la géologie.**
