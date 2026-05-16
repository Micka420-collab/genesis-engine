# Index complet du blueprint Genesis Engine

> Vue arborescente avec 1 ligne de description par fichier.

```
genesis-engine/
│
├── README.md                         Index général + démarrage
├── EXECUTIVE-SUMMARY.md              Résumé exécutif 1 page
├── INDEX.md                          ← (ce fichier)
│
├── docs/                             Vision et concepts
│   ├── 01-vision-and-philosophy.md       3 lois fondatrices, anti-patterns
│   ├── 02-system-overview.md             7 sous-systèmes + boucle de tick
│   ├── 03-agent-cognition.md             Pile cognitive 7 couches
│   ├── 04-world-engine.md                Génération procédurale, climat, biomes
│   ├── 05-emergent-systems.md            Économie, politique, culture, conflits
│   ├── 06-observation-and-tooling.md     Mode GOD, dashboards, replay
│   ├── 07-glossary-and-conventions.md    Glossaire + conventions
│   ├── PROJECT-VIABILITY.md              Contrat d'installation + portes de viabilité
│   ├── research/                          Publications scientifiques
│   │   └── 2026-05-15_OSF-preregistration.md   Pre-reg OSF Wave 11/12 (Registered Report)
│   ├── security/                          Sécurité opérationnelle
│   │   └── 2026-05-15_threat-model.md     STRIDE + LINDDUN + risk register
│   └── compliance/                        Conformité RGPD
│       └── 2026-05-15_AIPD.md             AIPD/DPIA v1.1 (post Wave 11)
│
├── architecture/                     Architecture technique
│   ├── system-architecture.md            Diagramme global + plans logiques
│   ├── tech-stack-2026.md                Stack 2026 complète
│   ├── ai-stack-and-world-models.md      DreamerV3, DINOv3, Triton, world models
│   ├── data-model.md                     Entités + tiers de stockage
│   └── infrastructure-and-scale.md       Topologie, K8s, autoscaling, FinOps
│
├── security/                         Sécurité
│   └── quantum-resistant-security.md     PQC + Zero Trust + HE + audit
│
├── specs/                            Spécifications détaillées
│   ├── avatar-pipeline-spec.md           Pipeline avatar utilisateur (E2E)
│   ├── procedural-world-spec.md          Génération monde + paramètres
│   └── streaming-and-lod-spec.md         Streaming, LOD, cognition LOD
│
├── adr/                              Architecture Decision Records
│   ├── TEMPLATE.md                       Modèle MADR 4.0
│   ├── 0001-rust-cuore-vs-unity.md       Cœur Rust, pas Unity/Unreal
│   ├── 0002-no-frontier-llm-as-agent-brain.md
│   ├── 0003-pqc-first-from-day-one.md
│   └── 0004-cockroachdb-vs-postgres.md
│
├── ethics/                           Éthique & gouvernance
│   ├── agent-moral-status.md             5 tiers de protection
│   └── governance-and-eu-ai-act.md       Conformité EU AI Act + governance
│
├── protocol/                         Science
│   ├── founding-experiment.md            Protocole « 2 agents fondateurs »
│   └── measurement-framework.md          Métriques + null model + pré-registration
│
├── ops/                              Opérations
│   ├── runbook-incidents.md              Sev 1–4, 7 scénarios
│   └── runbook-determinism-drill.md      Drill mensuel determinism
│
├── roadmap/
│   └── mvp-roadmap.md                    Phases 0 → 4, KPI, équipe
│
├── diagrams/
│   └── architecture-diagram.md           Mermaid : C1, C2, séquences, sécurité
│
├── runtime/                          Runtime Python opérationnel (Phase 3+)
│   ├── engine/                           8 modules (Phase 4 : + spatial.py)
│   ├── experiments/                      5 scripts exp + run_all
│   ├── journals/                         Journaux d'événements JSONL
│   └── artifacts/                        Résumés JSON par run (+ phase4_summary)
│
└── scaffolding/                      Code starter (squelette Rust)
    ├── Cargo.toml                        Workspace Rust 2024
    ├── Makefile                          Top-level make
    └── crates/                           6 crates (ge-core, ge-world, ge-agents,
                                          ge-cognition, ge-ann, ge-api)
```

## Comptage

```
22+ documents Markdown · 6 crates Rust + 9 modules Python runtime · 1 .proto · 2 yaml config · 1 yaml K8s · 1 Cargo workspace · 1 Makefile
```

## Mises à jour

- **2026-05-11** : Phase 1 scaffolding terminé pour `ge-world`, `ge-agents`,
  `ge-cognition`, `ge-ann`, `ge-api`. Voir `PHASE1-PROGRESS-2026-05-11.md`.
- **2026-05-11 (PM)** : Phase 2 — boucle de simulation réellement exécutable,
  determinism check vert. Voir `PHASE2-PROGRESS-2026-05-11.md`.
- **2026-05-12** : Phase 3 — **reproduction** implémentée (composant
  `Fertility`, système `run_reproduction`, `HumanAgentBundle::offspring`,
  événement `Birth` complet avec lignée). Premier test de bout-en-bout
  vérifiant la naissance d'une génération 1. Document d'architecture
  consolidé v1.0 (.docx) livré.
  Voir `PHASE3-PROGRESS-2026-05-12.md` et
  `Genesis_Engine_Architecture_v1.0.docx`.
- **2026-05-12 (soir)** : audit & opérationnel — runtime Python complet
  livré sous `runtime/` (8 modules ≈ 1 800 LoC), 5 expériences exécutées,
  multi-générationnel jusqu'à G14 observé, fixes Rust appliqués. Voir
  `AUDIT-REPORT-2026-05-12.md`.
- **2026-05-13** : Phase 4 — **comportement émergent** : spatial hash
  grid, signal de compétition-affinité, recall mémoire (lieux d'eau/de
  nourriture connus), proto-langage (lexique 16-D qui dérive sur SPEAK
  et s'hérite à la naissance), détecteur de formation de groupes.
  Vocalisations, compétitions et groupes mesurables sur 4 expériences
  (1 à 4 groupes émergents, 200 à 316 signatures lexicales distinctes
  par run). Voir `PHASE4-PROGRESS-2026-05-13.md` et
  `runtime/artifacts/phase4_summary.json`.
- **2026-05-16** : **Cognition perf #3** — `r_chunks` resserré (49→25
  chunks par perceive) + cache d'indices clairsemés par (chunk, tick)
  sur `_scan_chunk`. Sparse `np.nonzero` au lieu de bool-mask
  4096-cells. Déterminisme bit-perfect préservé (SHA-256 A==B).
  À re-mesurer en pop saturée (P-NEW.17). Voir `SPRINT-2026-05-16.md`.
- **2026-05-15** : **Wave 11 — personality → polity** livré.
  Trois publications scientifiques officielles déposées :
  `docs/research/2026-05-15_OSF-preregistration.md` (Registered
  Report H1–H5 + analyse confirmatoire des 21 smokes Wave 1–11),
  `docs/security/2026-05-15_threat-model.md` (STRIDE/LINDDUN +
  registre risques quantifié L×I, 19 entrées, top-5 mitigations),
  `docs/compliance/2026-05-15_AIPD.md` (DPIA v1.1, conformité
  RGPD art. 35, plan d'action 6 mesures).

## Ordre de lecture suggéré (1re session)

1. `EXECUTIVE-SUMMARY.md` (10 min)
2. `docs/01-vision-and-philosophy.md` (15 min)
3. `architecture/system-architecture.md` (20 min)
4. `architecture/tech-stack-2026.md` (15 min)
5. `roadmap/mvp-roadmap.md` (10 min)
6. `security/quantum-resistant-security.md` (20 min)
7. `protocol/founding-experiment.md` (10 min)
8. `ethics/agent-moral-status.md` (10 min)
9. `AUDIT-REPORT-2026-05-12.md` + `PHASE4-PROGRESS-2026-05-13.md` (20 min)
