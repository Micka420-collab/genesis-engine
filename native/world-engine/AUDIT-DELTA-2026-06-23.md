# AUDIT-DELTA-2026-06-23 (J+13) — « Qu'est-ce qu'il reste ? »

> Audit multi-agent (6 dimensions parallèles → synthèse → critique adverse), puis
> **corrigé** par vérification directe dépôt. Contexte : arc capacités à **C20**
> (`rock_canvas`), **pytest 803 passed** (re-vérifié vert cette session, exit 0),
> **Python actif / Rust gelé** (ADR-0008, env cargo-less confirmé).
> Méthode : `genesis-audit-j13` (8 agents). Les claims ci-dessous distinguent
> **[vérifié]** (re-checké dans le dépôt) de **[rapporté]** (déclaré par un doc).

---

## 0. Verdict global (une page)

**La découverte qui domine tout (nouvelle, P0/R0).** Le projet a **deux moitiés
qui ne se touchent pas** :
- un **arc de 20 capacités** émergentes C1→C20 (`runtime/engine/*.py`), riche, testé,
  discipliné — mais qui **se compose seulement lui-même** (C9 lit C5+C7, C19 lit C17,
  C20 lit C6…) et n'est **invoqué que par ses propres tests + smokes** ;
- une **boucle autonome** (`autonomous_world.py`) qui *tourne* et *mute* le monde
  (tectonique/érosion via `plate_tectonics_live`), mais qui **n'importe AUCUNE des 20
  capacités**.

**[vérifié]** : aucun module hors de l'arc (ni `world.py`, ni `agent*.py`, ni
`autonomous_world.py`, ni un dashboard, ni un registre) n'importe ou n'appelle une
capacité, ni ses points d'entrée agent (`best_*_near`, `discover_*_by_sight`,
`prospect_*`, `*_cue_for_chunk`, `smelt_at`, `bloom_at`). Il n'existe **aucun registre
de capacités**. → Les 20 capacités sont des **affordances véridiques mais sans
consommateur** : aucun agent ne **perçoit→choisit→agit** avec elles dans une boucle de
simulation. Ce n'est pas du code mort (les smokes les exercent sur le vrai monde
Genesis), mais c'est le **plus grand trou architectural** d'un « civ-sim où les agents
découvrent » : la découverte est *prouvée possible*, jamais *vécue*. **C'est ça, la
réponse #1 à « qu'est-ce qu'il reste ».**

**Ce qui marche vraiment (piste ACTIVE, saine).** L'artisanat de l'arc est réel et
vérifiable : 20 modules, chacun 1 test-file (15–26 tests) + 1 smoke **contigu p133→p152**,
règle d'émergence tenue (« le monde ne ment jamais », 11 mensonges rendus visibles),
contrat cross-langage CI-enforcé (`PY_TO_RUST=15`, 4 tells byte-exacts), garde-fous
**D9** (alternance feu/non-feu) et **D10** (mutation gelée au seul `geo.mine_at`),
déterminisme impeccable (prf_rng/PCG64 seul, 0 RNG non-semé).

**Ce qui est gelé ou stagnant.**
- **Substrat physique A–G : partiellement statique.** Le macro-monde (élévation, flow
  D8, vent, temp, précip rain-shadow) est calculé **une fois** dans `generate_world()`.
  ~6 « observateurs » (Waves 50–63) **mesurent** sans muter. Nuance **[vérifié]** : il
  existe BIEN une mutation d'`elevation_m` (`plate_tectonics_live.py:130`,
  `novel_operators.py:159`), câblée dans la boucle `autonomous_world` — donc l'élévation
  **n'est pas globalement immuable** ; mais cette boucle est **disjointe** du chemin
  agent/chunk et de l'arc. La « météo dynamique » côté chunk reste une horloge linéaire
  (branche `macro` → `0.0 + TODO`) ; rivières runtime = bande géométrique ; `cross_chunk_*`
  = stubs auto-déclarés. → **risque R0 (D11, re-scopé)**.
- **Backend Rust : gelé Wave 42.** **0 commit touchant `.rs` *depuis ADR-0008*** (1658e9c),
  0/20 items Phase A/B/C mergés en ~38 j. **[vérifié]** : 23 commits historiques touchent
  `.rs` (Waves 43/44, réactivation pont 7ac4280) — donc « 0 commit Rust » n'est vrai que
  *depuis ADR-0008*. Cohérent et daté (cargo/rustc absents) → choix réversible, pas
  pourriture silencieuse. `genesis-geology` orphelin (oracle lecture-seule).
- **Piliers d'émergence : 2 sur 5 IMMOBILES.** **Langage** et **bâtiments** ont une infra
  dormante (`communication.py`, `construction.py`, `building_discovery.py`, `statics.py`)
  mais **zéro capacité agent** dans l'arc. Le dessin vient de quitter zéro (C18 pigment +
  C20 support = 2 briques) — mais sans le **geste** agent-driven, lui aussi reste théorique.
- **Intégrité CI : trous nets [vérifié].** Le portail smoke s'arrête à **p139** (`Makefile`
  l.137 + `ci.yml`) → **13 smokes C9–C20 (p140→p152) dans AUCUN job CI**. `ruff` configuré
  mais **invoqué nulle part** (0 hit). `Cargo.lock` **untracked ET non-ignoré** (`??`).
- **Correction de l'auto-critique** : `FALSIFIABILITY.md` n'est **PAS vide** — c'est un
  **scaffold de 154 lignes** (cadre poppérien, 5 sections, table d'invariants **I-1..I-4
  remplie**) dont **les tables de claims n'ont aucune ligne de données**. Le vrai constat :
  *ledger structuré présent, 0 claim émergent enregistré* (les invariants ≠ claims).

**La réponse honnête à « qu'est-ce qu'il reste ? », dans l'ordre :**
1. **Brancher l'arc sur un agent** (P0) — sinon 20 capacités = bibliothèque sans joueur.
2. **Refermer les trous d'intégrité CI** (P0, cheap) — portail smoke→p152, ruff, Cargo.lock.
3. **Casser UN front immobile** (P1) — langage, OU climat dynamique côté chunk, OU rendre
   un observateur mutant sur le chemin agent.
4. **Corriger la brèche d'émergence vivante** (P1) — C3 ne stoppe **toujours pas** DRINK
   sur l'eau de mer : le monde *ment* en comportement, pas seulement en perception.

---

## 1. État par dimension

| Dimension | Piste | État | Note |
|---|---|---|---|
| Arc capacités C1→C20 | **ACTIVE mais SANS CONSOMMATEUR** | Sain / discipliné / **non branché** | 20 affordances testées ; aucun agent ne les invoque (D12/R0) |
| Couverture mission (6 axes / 5 piliers) | Mixte | Matériaux+outils avancés ; **langage+bâtiments immobiles** ; dessin naissant | 2/5 piliers à zéro depuis J+0 |
| Systèmes physiques A–G | **STAGNANT (chemin agent)** | Substrat figé côté chunk ; mutation réelle mais dans une boucle disjointe | Climat/hydro/écosystème non-simulés au runtime agent (D11/R0) |
| Frontière Python↔Rust | FROZEN (assumé, daté) | Pont **live** (backend=terrain), contrat vert | 0 commit Rust *depuis ADR-0008* ; Cargo.lock en limbo |
| Historique delta / registre risques | Géré | Treadmill nommé+géré (réactivement) | Méta-treadmill (routine à vide) flaggé J+12 |
| Tests / Déterminisme / CI / Falsifiabilité | Mixte | Déterminisme **excellent** ; CI **troué** | Smoke ≤p139, ruff off, ledger 0-claim |

---

## 2. Ce qui est FAIT (acquis vérifiés)

- **Arc complet C1→C20** : 20 modules, 1 test + 1 smoke contigu chacun (p133→p152) ;
  kinds cohérents (perception C1–C6, apparatus C11/C12, transformations C8/C9/C10/C13/C17/C19,
  opérateurs orthogonaux C14/C15/C18, axe symbolique C18/C20). **pytest 803 passed [vérifié vert cette session]**.
- **Garde-fous anti-treadmill réels** : D9 (alternance honorée jusqu'à C20) ; D10 (mutation
  gelée — *seuls* `smelt_at`+`bloom_at` appellent `geo.mine_at`, doc `MUTATION-FRONTIER.md`).
- **Contrat cross-langage CI-enforcé** : `PY_TO_RUST=15`, 4 tells byte-exacts, auto-découverte
  `*_outcrop._PROFILE` casse le build sur tell non-classé.
- **Pont Rust LIVE** : `bridge_status() → backend:terrain`.
- **Déterminisme** : prf_rng seul, 0 `thread_rng`, hash BLAKE2b.
- **Décisions documentées** : ADR-0007 (geology=oracle), ADR-0008 (Python actif/Rust gelé).
- **Falsifiabilité (cadre)** : `FALSIFIABILITY.md` scaffold + invariants I-1..I-4 remplis.

---

## 3. Ce qui RESTE — backlog priorisé (corrigé post-critique)

| # | Item | Prio | Dimension | Effort |
|---|---|---|---|---|
| 1 | **Brancher l'arc sur une boucle agent** : un agent perçoit (`discover_*_by_sight`/`best_*_near`), choisit, agit — au moins 1 capacité bout-en-bout dans un tick | **P0** | Arc / agent-loop | ~1 wave |
| 2 | Étendre le portail smoke CI p139 → p140..p152 (13 smokes non gardés) | **P0** | Tests/CI | ~1h |
| 3 | Brancher `ruff check runtime/` en CI + `make lint` (configuré, jamais exécuté) | **P0** | Tests/CI | ~30min |
| 4 | Corriger la brèche d'émergence vivante : C3 doit stopper DRINK sur eau de mer (le monde ment en comportement) | **P1** | Arc / écosystème | ~2h |
| 5 | Casser le front **langage** : 1ʳᵉ capacité agent forge+transmet un token lexical lié à un fait perçu (drift culturel, non scripté) | **P1** | Mission (pilier) | large |
| 6 | Rendre un observateur mutant **sur le chemin agent** (érosion abaisse `elevation_m` vu par les chunks) — casse D11 + observer-treadmill | **P1** | Physique A–G | ~1 wave |
| 7 | Climat dynamique côté chunk : recoupler l'atmosphère → `temp_c`/`precip_mm` (remplacer la branche `macro` → 0.0) | **P1** | Physique D / F3 | large |
| 8 | Rendre l'alternance D9 CI-enforced (check git-log) **ou** ratifier « fire-first » via ADR-0009 | **P1** | Treadmill | ~2–4h |
| 9 | R-J12-1 : gater la routine d'audit sur « ≥1 commit depuis le dernier delta » (méta-treadmill ~30k tok/j à vide) | **P1** | Méta | config tâche |
| 10 | Trancher `Cargo.lock` (committer **ou** .gitignore+raison) — hygiène, valeur faible en env cargo-less | **P2** | Frontière/CI | ~15min |
| 11 | Boucler le pilier **dessin** : capacité geste/marque agent-driven via `art_discovery` (pigment C18 + support C20 prêts) | **P2** | Mission | ~1 cap |
| 12 | Brancher le pilier **bâtiments** (`building_discovery`+`statics`) en capacité émergente (structure reconnue, sans recette scriptée) | **P2** | Mission | ~1 cap |
| 13 | Usage des métaux : forge à froid / recuit / coulée → l'outil métal devient jouable | **P2** | Arc | ~1 cap chacun |
| 14 | Peupler les **tables de claims** de `FALSIFIABILITY.md` : ≥1 claim émergent ancré (3 seeds + state_fingerprint) | **P2** | Falsifiabilité | moyen |
| 15 | Remplacer la bande-rivière + stubs `cross_chunk_*` par un transport de débit conservatif inter-chunks | **P2** | Physique A / F2 | large |
| 16 | Bronze : étain/`cassiterite` SANS tell de surface → verbe « prospection aveugle » + alliage Cu+Sn | **P2** | Arc | large |
| 17 | R-J4-2 : binding compilé `#[pyfunction] mineral_tells()` au lieu du contrat text-parse (F-D8-1) | **P3** | Frontière | ~½j (session cargo) |
| 18 | D5-wiring : `geology::sample_at()` dans `Chunk::generate()` (ADR-0007 step 2) | **P3** | Frontière | session cargo |
| 19 | Vérifier le build `genesis-scenario` (réputé non-compilant 2026-06-09) | **P3** | Frontière | session cargo |
| 20 | Nettoyer la numérotation smoke globale (p6/p116 manquants ; p73/p82 dupliqués) | **P3** | Tests | ~30min |
| 21 | Planifier UNE « session cargo » atomique pour vider le backlog Rust (R-J4-2, D5-wiring, A3/A4/A5, gpu, scenario, clippy) | **P3** | Frontière | large |

---

## 4. Registre des risques fusionné D1–D12 (corrigé)

| ID | Description | Sévérité | Statut |
|---|---|---|---|
| D1 | Observer treadmill originel (14 observateurs en 14 j) | R2 | **clos** (observer_budget + moratoire) |
| D2 | `maybe_evict` O(N) sans LRU ; jobs cargo non reproductibles localement | R2/R1 | stagnant/ouvert |
| D3 | `entities_in_radius` stub `Vec::new()` (bloque perception multi-agent Rust) | R2 | stagnant |
| D4 | Score « réalisme Terre » décorrélé du worldgen Rust (mesure la perception Python) | R2 | mitigé (ADR-0008 §4) |
| D5 | `genesis-geology` orphelin (oracle) | R2 | clos (ADR-0007) |
| D6 | Double source-of-truth géologie Python/Rust | R1 | clos (test contrat CI) |
| D7 | Vélocité asymétrique Python≫Rust (cargo absent) | R1 | mitigé (daté ADR-0008) |
| D8 | `PY_TO_RUST` single-point-of-truth ; résiduel F-D8-1 (text-parse, pas binding) | R2 | mitigé |
| D9 | Treadmill capacités/feu (transformations isomorphes) — géré **socialement**, pas CI | R1 | ouvert |
| D10 | Divergence d'état muté cross-langage (Python mute, Rust ignore) ; gelé-sûr 1 point removal-only | R2 | mitigé |
| D11 | **Substrat figé sur le chemin agent/chunk** : météo `macro`→0.0, rivières peintes, `cross_chunk_*` stubs. *Re-scopé* : `elevation_m` EST muté par `plate_tectonics_live`/`novel_operators`, mais dans la boucle `autonomous_world` **disjointe** du chemin agent | **R0** | ouvert |
| **D12** | **L'arc C1→C20 n'a aucun consommateur agent** : 20 affordances testées que personne n'invoque dans une boucle ; la « découverte » est prouvée possible, jamais vécue. Aucun registre de capacités | **R0** | **ouvert (nouveau)** |
| *(D-LANG)* | Pilier langage immobile ; `communication.py` enum structuré → risque de violer l'émergence si branché tel quel | R1 | ouvert |
| *(D-BUILD)* | Pilier bâtiments immobile ; `construction.py` recettes hardcodées → breach émergence si utilisé direct | R1 | ouvert |
| *(D-CI)* | Portail smoke ≤p139, ruff jamais exécuté, claim-tables FALSIFIABILITY vides, Cargo.lock untracked+non-ignoré | R1 | ouvert |

---

## 5. Recommandations — R-J13-x (corrigées)

### P0 — débloquer + protéger l'acquis
- **R-J13-1 (P0) — Brancher l'arc sur un agent.** Choisir 1 capacité (p.ex. C2 lithic ou
  C14 cryoclasty) et la câbler bout-en-bout dans un tick : l'agent `discover_*_by_sight` →
  `best_*_near` → agit (déplacement/collecte) → mémoire. Sans ça, l'arc reste une
  bibliothèque sans joueur (D12/R0). C'est la priorité #1 du projet, pas une de plus.
- **R-J13-2 (P0) — Portail smoke → p152.** Ajouter `p140..p152` au `Makefile` (`validate-all`,
  après l.137) **et** au tableau « Realism smokes » de `ci.yml`. 13 smokes C9–C20 sans garde.
- **R-J13-3 (P0) — Brancher ruff.** `ruff check runtime/` en step CI + `make lint` + ruff aux
  deps `[dev]`. Les « ruff clean » des sprints sont aujourd'hui non vérifiés.

### P1 — haut levier
- **R-J13-4 (P1) — Corriger la brèche d'émergence vivante.** C3 `water_potability` rend l'eau
  de mer imbuvable en perception mais le verbe DRINK l'hydrate quand même : c'est le **seul cas
  où le monde ment en comportement**. À corriger en priorité (cohérence de la règle sacrée).
- **R-J13-5 (P1) — Casser UN front immobile** (choix utilisateur, UN seul) : **langage**
  (plus haut levier, débloque L4) / **climat dynamique chemin-chunk** / **observateur mutant
  agent-visible**. Trancher en **ADR-0009**.
- **R-J13-6 (P1) — D9 CI-enforced ou ADR-0009 « fire-first ».** La gestion D9 est sociale et
  a été ignorée 3 j.
- **R-J13-7 (P1) — Cadence routine d'audit (R-J12-1).** Gater le run delta sur activité.

### P2/P3 — déféré (cohérent ADR-0008 / session cargo)
- **R-J13-8 (P2) — Peupler les tables de claims de `FALSIFIABILITY.md`** (≥1 claim émergent
  ancré). Le scaffold existe ; il lui manque les *données*.
- **R-J13-9 (P2) — Cargo.lock** : committer ou ignorer+raison (hygiène, faible impact en cargo-less).
- **R-J13-10 (P3) — Session cargo atomique** : vider R-J4-2 + D5-wiring + Phase A + gpu +
  scenario + clippy/audit en une fois.

> **Garde-fous pour toute nouvelle capacité** : émergence-only (« le monde ne ment jamais »),
> déterminisme prf_rng, D8 par composition (ne pas grossir `PY_TO_RUST`), alternance feu/non-feu
> (D9), mutation au seul `geo.mine_at` (D10), ADR-0008 cargo-less.

---

## 6. Corrections appliquées à la synthèse (traçabilité de l'auto-critique)

La critique adverse du workflow a relevé 5 erreurs **vérifiées et corrigées** ici :
1. `FALSIFIABILITY.md` n'est **pas vide** (scaffold 154 l. + invariants remplis ; seules les
   tables de claims sont sans lignes). « 0 claim » reformulé en « 0 claim *enregistré* ».
2. **D12 ajouté** (arc sans consommateur agent) — le trou architectural dominant, absent de la
   synthèse initiale. **[vérifié]** : 0 import/appel des capacités hors arc+tests+smokes.
3. **D11 re-scopé** : `elevation_m` EST muté (`plate_tectonics_live:130`, `novel_operators:159`,
   câblé `autonomous_world`) — mais boucle **disjointe** du chemin agent. R0 maintenu sur ce
   point précis (figement du chemin chunk + trou hydro), pas sur « immuabilité globale ».
4. « 0 commit Rust » **qualifié** : vrai *depuis ADR-0008* (1658e9c) ; 23 commits `.rs`
   historiques existent.
5. `Cargo.lock` P0 → **P2** : en env cargo-less, le lockfile protège un acquis non exerçable
   ce sprint ; c'est de l'hygiène, pas une urgence.
