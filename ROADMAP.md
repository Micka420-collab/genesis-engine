# Genesis Engine — Roadmap Viable

**Derniere mise a jour :** 2026-05-17

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
| **Bevy 0.16 ECS Relationships + GPU-Driven Rendering** | World (port Rust) | bevy.org/news/bevy-0-16 | archetype fragmentation reduite, big-scenes plus rapides | conditionne a P1 (scaffolding Rust vert) |
| **X-Wing KEM hybride X25519 x ML-KEM-768** | Platform | draft-ietf-mls-pq-ciphersuites + Cloudflare PQC TLS | un seul KEM standardise pour TLS / gRPC future-proof | conditionne a la sortie d'un endpoint reseau Genesis (~4h une fois necessaire) |
| **Neo4j Native Vector Type** | Observatory | neo4j.com/blog (mai 2026) | vecteurs natifs sans helpers, contraintes de shape/dtype | conditionne au deploiement Neo4j (Observatory Phase 5+) |
| **AgentSociety / Synthetic Social Graph** | Social | arxiv 2502.08691 + 2604.27271 | metriques d'emergence (cohesion + divergence) | **INTEGRE Wave 13 (2026-05-17)** -- `engine.social_resonance` |
| **AI Metropolis Out-of-Order Execution** | Agentic | arxiv 2411.03519 (veille 2026-05-28) | parallelisme tick LLM tier-2 par detection de fausses dependances inter-agents | conditionne a l'activation Phase 5 LLM tier-2 (~5h une fois LLM actif) |
| **Project Sid civilization benchmark** | Social | arxiv 2411.00114 (veille 2026-05-28) | comparaison externe metriques emergence (specialisation roles, transmission culturelle) | document `docs/benchmarks/PROJECT-SID.md` a programmer (~3h) |
| **Emergence World long-horizon benchmark** | Social/Agentic | arxiv 2606.08367 + AIvilization v0 (2602.10429) (veille 2026-06-19) | banc d'evaluation autonomie multi-agent long-horizon (normes, internalisation contrat social) — voisin Project Sid | conditionne a l'activation Phase 5 LLM tier-2 (~3h une fois LLM actif) |
| **Collusion / conformity observer** | Social | arxiv 2603.27771v2 (veille 2026-05-28) | detection emergence collusion-like / conformity sous contrainte ressources | overlap Wave 13 `social_resonance` -- a ouvrir si delta mesurable (~4h) |

Toutes les veilles matinales sont archivees dans [`docs/veille/`](docs/veille/).

