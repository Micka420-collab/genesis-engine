# Genesis Engine — Roadmap Viable

**Derniere mise a jour :** 2026-07-01

Ce fichier est la roadmap stable du projet. La file de sprint vivante reste
dans [`NEXT-SPRINT.md`](NEXT-SPRINT.md). Ici, l'objectif est simple :
faire passer Genesis Engine de laboratoire prometteur a projet reproductible,
installable et maintenable.

---

## Frontière Python/Rust (ADR-0008, 2026-06-15)

[ADR-0008](adr/0008-python-rust-frontier.md) tranche la frontière restée implicite :
pour l'ère **cargo-less** (env sans `cargo`/`rustc`), `runtime/engine/` (Python
déterministe) est la **couche de simulation/perception active** ; `native/world-engine/`
(Rust) est le **substrat worldgen gelé** (Wave 42) + oracle de contrat (ADR-0007).
La frontière est **réversible** : les items ci-dessous sont **différés** à une
« session cargo » (CI dédiée ou toolchain locale), **pas abandonnés**.

**Backlog « session cargo » (nécessite `cargo`) :**

- **R-J4-2** — binding compilé `#[pyfunction] fn mineral_tells()` dans
  `crates/pybindings/`, consommé par `test_geology_cross_language_contract.py`
  (élimine F-D8-1, le parsing texte fragile du contrat).
- **D5-wiring** (ADR-0007 étape 2) — `geology::sample_at()` dans `Chunk::generate()`
  + hash content-key worldgraph.
- **Phase A** — A3 (spatial index `rstar`), A4 (raycast accéléré), A5 (GPU erosion
  auto-fallback). **Phase B** — B1→B8 (tectonique dyn, hydro cross-chunk, advection
  humidité, saisons, SDF caves, boids, hot-reload biomes, debug overlay).

Tant que ces items ne sont pas verts en CI, **on ne prétend pas que le moteur Rust
sert la simulation** (le score réalisme mesure la couche perception Python, R-J4-1).

---

## Boucle agent : l'arc devient *vécu* (ADR-0009, 2026-06-24)

[ADR-0009](adr/0009-agent-consumer-loop.md) tranche **D12 / R0** (audit J+13) : l'arc
de 20 capacités C1→C20 n'avait **aucun consommateur agent** — découverte *prouvée
possible*, jamais *vécue*. La boucle de consommation canonique est
`perceive → decide → act → remember` (les 3 appels de `Simulation.step`), sous les
drives de survie, **sans arbre tech scripté** (le monde décide le résultat).

- **C3 / DRINK** (R-J13-4, `2d0ebd0`) — 1ʳᵉ bouchée : une action existante devient honnête.
- **C2 / KNAP** (R-J13-1, `7d4c748`) — 1ᵉʳ *comportement nouveau* : un agent curieux
  qui **voit** un affleurement taillable y va et **taille** un éclat ; `inv_tools` gagne
  un tranchant ∝ `knap_quality` réelle. 1ᵉʳ remplisseur de `inv_tools` de tout l'arc.
- **C14 / GATHER** (R-J14-1, 2026-06-25) — 3ᵉ capacité branchée, **opérateur orthogonal**
  (ramasser, pas casser) : là où le gel a déjà détaché des éclats sains en surface, un
  agent curieux **ramasse** un gélifract prêt à l'emploi (`ActionKind.GATHER`), sans
  percussion. Essayé **avant** KNAP dans `decide()` (le gel a fait le travail → ramasser
  prime). Rendement ∝ `clast_quality` (= base C2 × réponse de gel) : obsidienne froide →
  rasoir, granite froid → arène stérile (mensonge #5). Surface seule → D10 gelé.
- **C18 / GRIND** (R-J15-2, 2026-06-27) — 4ᵉ capacité branchée, **1ʳᵉ consommation agent
  du pilier SYMBOLIQUE** (immobile depuis J0). 9ᵉ opérateur orthogonal (broyer), sur un
  **inventaire dédié** (`inv_pigment`) : un agent curieux qui **voit** une terre rouille
  d'oxyde la **broie** (`ActionKind.GRIND`) en pigment ∝ `pigment_quality` réelle.
  Essayé **après** KNAP (l'outil d'abord, puis le symbole). Mensonge #9 : un gossan oxyde
  (hématite/magnétite) peint, le même chapeau rouille sur pyrite/plomb-zinc ne peint pas
  (rouille ≠ rouge). Surface seule → D10 gelé. (Le **GESTE** qui suit — tracer sur le
  `rock_canvas` C20 — est livré par **C20 / MARK** ci-dessous.)
- **C20 / MARK** (2026-06-28) — 5ᵉ capacité branchée et **2ᵉ consommation agent du pilier
  SYMBOLIQUE** : réalise le **GESTE** annoncé par C18, fermant la mini-chaîne *voir l'oxyde
  → broyer → pigment → **marquer***. Un agent curieux qui **tient** un pigment (C18) et
  **voit** une paroi carbonatée pâle (C20) y laisse une **marque** (`ActionKind.MARK`) — le
  *monde* décide si elle **dure** (`durability` = adhérence × persistance, lue de C20) et si
  elle se **voit** (contraste pigment/paroi). Mensonge #11 : une paroi SAINE garde la marque
  (voile de calcite) ; la **même** falaise carbonatée en climat humide (KARST) ou gelant
  (FROST) la prend puis l'**écaille** (« looks markable ≠ holds a lasting mark »). La couleur
  broyée est **portée** (`EpisodicMemory.last_pigment_hue`), posée par GRIND. Essayé **après**
  GRIND (la matière du symbole, puis sa marque). Le **sens** du tracé (la figure, l'archétype)
  reste émergent — `engine.art_discovery` (L4). **Non mutant** (la peinture ne consomme pas la
  roche → D10 gelé) ; D8 par composition (`PY_TO_RUST` reste 15). 11 tests + smoke p160 8/8.
- **C7 / IGNITE** (2026-06-28) — 6ᵉ capacité branchée et **la VOÛTE de l'arc** : la première
  fois qu'un agent **allume un feu**. Un agent curieux et survie-satisfaite, **frileux** (ou
  qui n'a **jamais** fait de feu), qui **voit** un site où une étincelle prend vraiment
  (`fire_ignition.best_firesite_near`) y va et **frappe** un feu (`ActionKind.IGNITE`). Le
  *monde* décide si l'étincelle prend : **PERCUSSION** là où la géologie porte un firestone
  pyrophorique (pyrite/gossan C1) + un percuteur dur (C2) sur amadou assez sec, **FRICTION**
  là où l'amadou très sec laisse prendre une braise d'archet sans aucun minéral ; une prairie
  **humide** *paraît* de l'amadou mais l'étincelle n'y prend pas (le mensonge du feu —
  `prospect_ignition` renvoie None). Contrairement à KNAP/GATHER/GRIND, IGNITE ne remplit
  **aucun inventaire portable** : le produit est la **CHALEUR** (le drive thermique de l'agent
  baisse) et le **savoir** (`has_made_fire`/`last_fire_method`) — la clé de voûte qui rend
  *actionnables* les matières C1→C6 (fondre, brûler, cuire, calciner). Essayé **après** KNAP/
  GATHER (la pierre d'abord) et **avant** GRIND/MARK (la chaleur avant l'art). **Auto-limité &
  honnête** : seulement quand on veut de la chaleur (ou à la 1ʳᵉ découverte) → pas de
  ré-allumage à chaque tick. **Non mutant** (frapper une étincelle ne consomme pas la roche →
  D10 gelé) ; D8 par composition (`PY_TO_RUST` reste 15, C7 sans `_PROFILE`). 11 tests +
  smoke p161 8/8.

- **C13 / SMELT** (2026-07-01, [ADR-0010](adr/0010-agent-driven-mutation.md)) — **18ᵉ wire → 18/20**, et
  **LA PREMIÈRE MUTATION DU MONDE PAR UN AGENT**. Après 17 wires non-mutants (D10 gelé, `g_before ==
  g_after`), un agent qui a **découvert le tirage forcé** (C12), **appris que le vert signifie cuivre**
  (PROSPECT/C1 — la fondation cognitive du wire #17 est ici dépensée) et **porte du charbon** (C4) **FOND**
  son minerai (`ActionKind.SMELT`, réutilisé du legacy — honnête comme DRINK). `smelt_at` → `geo.mine_at`
  **draine la colonne** (le minerai disparaît du sol) : D10 est **franchi par design**, borné au sous-arc
  métallurgique. Le monde décide du bouton : cuivre natif → métal (bouton `0.2375 kg`), la **même**
  chalcopyrite (sulfure) → **scorie seule** tant qu'elle n'est pas grillée (mensonge #4 vécu). D8
  (`PY_TO_RUST` reste 15), D9 0→1 (feu), déterministe. 13 tests + smoke p173 8/8.

**Reste (2 capacités C17 `iron_bloomery` / C19 `bloom_forging` + piliers langage/bâtiments)** : même
patron, une tranche verticale à la fois. C17/C19 franchiront D10 sous [ADR-0010](adr/0010-agent-driven-mutation.md)
(SSOT mutant audité + préconditions vécues). Le **registre de capacités** `_ARC_SEEKS` + budget de
perception (ADR-0009) porte déjà les 18 branchements.

---

## P0 — Reproductibilite locale

**Objectif :** un nouveau contributeur doit pouvoir installer et verifier le
runtime en moins de 10 minutes.

- `pyproject.toml` comme source d'installation Python.
- `requirements*.txt` pour les environnements simples.
- `make doctor`, `make compile-python`, `make test-python`.
- CI minimale qui installe `.[dev]` et lance les tests Python.

**Critere de sortie :**

```bash
python -m pip install -e ".[dev]"
make doctor
make test-python
```

---

## P1 — Rust scaffolding compilable

**Objectif :** le workspace Rust doit devenir un socle fiable, meme s'il n'a
pas encore la parite fonctionnelle avec le runtime Python.

- `cargo check --workspace` vert.
- `cargo test --workspace --all-features` vert.
- Supprimer les references Makefile vers des dossiers inexistants.
- Garder les crates sous la meme licence que le depot racine.

**Critere de sortie :**

```bash
cd scaffolding
cargo check --workspace
cargo test --workspace --all-features
```

---

## P2 — Source de verite runtime

**Objectif :** reduire la confusion entre les implementations.

- `runtime/engine` = runtime operationnel officiel.
- `scaffolding/crates` = port Rust long terme.
- `runtime/genesis` = prototype deprecie, a supprimer quand le filesystem le
  permet.
- `runtime-phase5` = a fusionner ou archiver apres comparaison des features.

**Critere de sortie :** README, CONTRIBUTING et docs d'architecture nomment les
entrees supportees sans contradiction.

---

## P3 — Discipline experimentale

**Objectif :** chaque experience doit etre rejouable, comparable et lisible.

- Manifeste de run : seed, commit, config, dependances, timestamp.
- Artefacts regenerables, pas melanges avec le source control.
- Tests de determinisme seed-a-seed documentes.
- Profiling TPS regulier pour 50, 100, 200 agents.

**Critere de sortie :** `runtime/experiments/run_all.py` produit un dossier
date avec manifest, journals et summary unique.

---

## P4 — Viabilite scientifique

**Objectif :** separer les claims prouves, les hypotheses et les plans.

- README limite aux capacites verifiees.
- [`docs/TESTS_INVENTORY.md`](docs/TESTS_INVENTORY.md) garde les observations chiffrees.
- Les limitations connues restent visibles : conflits absents, stress 100
  fragile, topographie plate dans certaines regions, mortalite Phase 5 a
  recalibrer.

**Critere de sortie :** aucun claim public majeur sans smoke test, artefact ou
doc de verification associe.

---

## P5 — Backlog veille techno (combos differes)

Combos identifies lors des veilles matinales mais trop couteux pour
etre integres dans la session courante. Garde-fou : un combo qui
n'avance pas a 60 jours doit etre soit promu (planning concret),
soit explicitement rejete (justification 1 ligne).

| Combo | Couche Genesis | Source veille | Gain estime | Cout |
|---|---|---|---|---|
| **Tri-Spirit Architecture** (planning / reasoning / reflex) | Agentic | arxiv 2604.13757 | structure cognitive 3-tiers, decoupage explicite de la cognition | refonte partielle `engine.cognition` (~6h) |
| **Bevy 0.18 ECS scheduler + GPU-Driven Rendering** | World (port Rust) | bevy.org/news/bevy-0-18 (veille 2026-06-22) | archetype fragmentation reduite, big-scenes plus rapides, editor preview | conditionne a P1 (scaffolding Rust vert) |
| **X-Wing KEM hybride X25519 x ML-KEM-768** | Platform | draft-ietf-mls-pq-ciphersuites + Cloudflare PQC TLS | un seul KEM standardise pour TLS / gRPC future-proof | conditionne a la sortie d'un endpoint reseau Genesis (~4h une fois necessaire) |
| **Neo4j Native Vector Type** | Observatory | neo4j.com/blog (mai 2026) | vecteurs natifs sans helpers, contraintes de shape/dtype | conditionne au deploiement Neo4j (Observatory Phase 5+) |
| **AgentSociety / Synthetic Social Graph** | Social | arxiv 2502.08691 + 2604.27271 | metriques d'emergence (cohesion + divergence) | **INTEGRE Wave 13 (2026-05-17)** -- `engine.social_resonance` |
| **AI Metropolis Out-of-Order Execution** | Agentic | arxiv 2411.03519 (veille 2026-05-28) | parallelisme tick LLM tier-2 par detection de fausses dependances inter-agents | conditionne a l'activation Phase 5 LLM tier-2 (~5h une fois LLM actif) |
| **Project Sid civilization benchmark** | Social | arxiv 2411.00114 (veille 2026-05-28) | comparaison externe metriques emergence (specialisation roles, transmission culturelle) | document `docs/benchmarks/PROJECT-SID.md` a programmer (~3h) |
| **Emergence World long-horizon benchmark** | Social/Agentic | arxiv 2606.08367 + AIvilization v0 (2602.10429) (veille 2026-06-19) | banc d'evaluation autonomie multi-agent long-horizon (normes, internalisation contrat social) — voisin Project Sid | conditionne a l'activation Phase 5 LLM tier-2 (~3h une fois LLM actif) |
| **Collusion / conformity observer** | Social | arxiv 2603.27771v2 (veille 2026-05-28) | detection emergence collusion-like / conformity sous contrainte ressources | overlap Wave 13 `social_resonance` -- a ouvrir si delta mesurable (~4h) |
| **Deterministic Simulation Testing (DST)** | Observatory / devtools (axe 6) | QCon London + FOSDEM 2026 (veille 2026-06-22) | harnais de test seed-reproductible avec injection de fautes (tick-loop mono-thread) — calque exact de la discipline determinisme/seed de Genesis ; rejoue toute regression depuis un seed | combo INTERNE viable cargo-less (~4h) : envelopper `runtime/experiments/run_all.py` d'un mode DST (fautes injectees + replay seed). A promouvoir si une regression non-deterministe apparait |
| **Fill–Spill–Merge** (flow routing en hierarchie de depressions) | World (hydrologie, Wave 64 `river_discharge`) | Barnes/Callaghan, NSF par.10263903 + Springer 2025 (veille 2026-06-30) | lacs endoreiques emergents : les cuvettes/depressions piegent le flux → lacs au lieu d'un routage purement descendant ; reste **physique pure** (pas un arbre tech) | combo INTERNE cargo-less mais touche du code TESTE (`engine.river_discharge` + `test_river_discharge_coupling`) → risque de regression > valeur d'une session non surveillee. A planifier comme **Wave World dediee** (~5h) avec garde-fou non-regression du couplage existant |

Toutes les veilles matinales sont archivees dans [`docs/veille/`](docs/veille/).

