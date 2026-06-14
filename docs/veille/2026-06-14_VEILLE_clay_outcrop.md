# Veille technologique — 2026-06-14

**Lead Engineer Genesis-α · Morning routine v3.0 · veille-first**
Sortie : **Cap. C5 `clay_outcrop`** (5ᵉ capacité agent — découverte émergente de l'argile).

---

## ÉTAPE 0 — Veille (5 axes)

### Axe 1 — IA & agents
- *Generative Agents / Smallville* reste la référence d'émergence sociale ; OASIS
  scale jusqu'à 1 M d'agents LLM (Twitter/Reddit sim).
- **Project SID** (PIANO) et **AIvilization v0** (arxiv 2602.10429, *unified agent
  architecture + adaptive profiles*) : émergence de lois / religion / économie
  dans des mondes multi-agents → benchmark externe pour l'émergence civilisationnelle.
- **Memory for Autonomous LLM Agents** (arxiv 2603.07670) + *State of AI Agent
  Memory 2026* (mem0) : la **mémoire** est désormais le facteur dominant —
  *MemoryArena* montre que "has memory vs not" pèse **plus** que le choix de
  backbone LLM (80 %→45 % sans mémoire). **Lien Genesis** : le mécanisme « tell »
  (couleur de surface → clé mémoire de l'agent) EST un mécanisme mémoire ;
  l'argile beige-ocre devient une clé « terre grasse près de l'eau → récipient ».

### Axe 2 — Rust / ECS / moteur
- **Bevy 0.16** : GPU-driven rendering, occlusion culling, transform propagation
  statique ; **Bevy 0.18** (2026) : multithread par défaut, asset system stabilisé,
  ECS Relationships. → reste **conditionné à P1** (scaffolding Rust vert) ; non
  intégrable ici (`cargo` absent de l'env).

### Axe 3 — Cryptographie & sécurité
- **X25519 + ML-KEM-768** hybride : GA chez Imperva/Thales début 2026, Google
  Cloud KMS quantum-safe 2026, draft IETF MLS PQ. ClientHello combiné 1216 o.
- **CVE_ACTIVES** : aucune CVE critique applicable à Genesis ce jour (pas de
  surface réseau active dans le runtime Python ; pas de dépendance tokio/gRPC/k8s
  exposée). PQC reste **différé** (P5 backlog) jusqu'à l'ouverture d'un endpoint.

### Axe 4 — Infra & data
- ClickHouse / NATS JetStream / Neo4j native vectors / WebGPU : pertinents
  Observatory/Platform Phase 5+, non bloquants aujourd'hui.

### Axe 5 — Papers arXiv
- **PAPER_DU_JOUR** : *Automating the Search for Artificial Life with Foundation
  Models* (arxiv 2412.17799) — « primordial soup → Cambrian explosion → artificial
  alien civilization ». Conforte H0 et la philosophie émergence-pure ; pas
  d'algorithme directement câblable en 7 j.
- Hors-veille IA mais décisif pour C5 : **limites d'Atterberg** (mécanique des
  sols, Atterberg 1911) — la fenêtre d'humidité plastique PL→LL d'une argile.
  Base scientifique de la porte de plasticité.

### Synthèse
- **DÉCOUVERTE_1** : *Agent memory as dominant factor* (mem0/arxiv 2603.07670) ·
  couche **Agentic/Social** · gain : valide le mécanisme « tell→clé mémoire ».
- **DÉCOUVERTE_2** : *AIvilization / Project SID* (arxiv 2602.10429 / 2411.00114) ·
  couche **Social** · gain : benchmark émergence (différé, P5 backlog).
- **DÉCOUVERTE_3** : *Atterberg limits* (soil mechanics) · couche **World/Substrate** ·
  gain : porte de plasticité véridique pour la découverte d'argile.
- **CVE_ACTIVES** : aucune critique.
- **PAPER_DU_JOUR** : ASAL (arxiv 2412.17799) — apport conceptuel, rien de câblable
  sous 7 j.

---

## ÉTAPE 1 — Moteur de combinaison (COMBO-GENESIS)

**COMBO_RETENU : `Atterberg plasticity window` × `Genesis geology (shale/FineClay)`**
- **Gain** : 5ᵉ capacité de découverte stone-age — l'argile, **clé de voûte**
  (récipient C3-eau, four C4-feu, creuset métal, brique) — devient perceptible et
  véridique. Ferme l'**orphelin `Mineral::FineClay`** du crate Rust (gap noté au
  contrat cross-langage depuis Wave 43). Géologie/relief 76→77 (≈ +0,15 % global).
- **Coût** : ~3 h · complexité 2/5 · risque régression 1/5 (capacité additive,
  dérivation pure ; le seul risque — perturbation de `_select_ore_mix` par le
  nouveau `fine_clay` — vérifié nul : C1/C2/C3 smokes verts, suite pytest verte).
- **Couche** : World/Substrate (lecture dérivée, comme C1–C4).
- **Intégration** : `engine.clay_outcrop` lit `chunk_geology` (shale lithologie +
  fine_clay ore) + humidité ambiante (biome + `chunk.water`) → cue véridique avec
  porte de plasticité (`too_dry_to_shape` / `workable_now` / `too_wet_slurry`) et
  porte céramique (`ceramic_grade` = kaolin uniquement).
- **ADR requis** : NON — couvert par **ADR-0007** (garde-fou : toute capacité
  enrichit `PY_TO_RUST` ; ici `fine_clay → FineClay`, orphelin fermé, tell
  `(180,140,110)` byte-exact verrouillé).

**COMBO_BACKLOG** : Bevy 0.16/0.18 (conditionné P1) ; X25519+ML-KEM-768
(conditionné endpoint réseau) ; AIvilization/SID benchmark (doc à programmer) —
tous déjà en P5 backlog `ROADMAP.md`, inchangés.

**COMBO_REJETÉ** : CVE tokio/gRPC/k8s — aucune surface concernée dans le runtime
Python ; WebGPU/ClickHouse/Neo4j — Observatory Phase 5+, hors scope du jour.

---

## ÉTAPE 2 — Audit & backlog

- **PHASE** : 3🟡/4✅ (émergence civilisationnelle) · couches opérationnelles :
  Substrate, Agentic, Social, World, Observatory, Presentation.
- **P0_BLOQUANTS** : aucun (pytest vert avant session).
- **TÂCHE_JOUR** : +1 capacité émergente / jour (anti-treadmill). Fusionnée avec
  le COMBO_RETENU → C5 `clay_outcrop`.
- **IMPACTÉ_PAR_VEILLE** : OUI — la veille (mémoire-comme-clé + Atterberg) a
  directement informé le design du tell et de la porte de plasticité.
- **Dette connue non touchée** (honnêteté audit) : câblage Rust réel (D5-wiring,
  Phase A) ; sous-score « capacité moteur Rust » reste 0/7 — `cargo` absent (CI =
  vérité). C5 est une capacité du **runtime Python live**.
