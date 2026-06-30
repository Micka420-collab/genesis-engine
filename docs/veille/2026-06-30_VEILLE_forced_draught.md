# Veille technologique — 2026-06-30 (Morning Routine v3.0, étape 0)

> Veille-first. 5 axes lancés en parallèle **avant** toute ligne de code. Genesis est *cargo-less*
> (Python 3.14 / numpy seul, ADR-0008), *no-LLM-brain* (ADR-0002), déterministe. Un combo n'est
> « intégrable aujourd'hui » que s'il respecte ces trois contraintes **et** l'émergence pure
> (0 arbre tech scripté, [feedback emergence-only]).

## Les 5 axes

### Axe 1 — IA & agents
- *Memory for Autonomous LLM Agents* (arxiv 2603.07670), *Generative Agents* memory/reflection,
  *Agentic LLM survey* (2503.23037), *Sentipolis* (2601.18027). **Gated** : Genesis n'utilise
  **aucun LLM comme cerveau d'agent** (ADR-0002 — cognition déterministe). Inapplicable à l'arc.

### Axe 2 — Rust / ECS / moteur
- *Bevy 0.18 ECS scheduler + GPU-driven rendering*. **Gated** : conditionné à P1 (scaffolding Rust
  vert) — `cargo` absent de l'environnement. Déjà au backlog P5.

### Axe 3 — Cryptographie & sécurité (CVE)
- **CVE-2026-3298** — `asyncio.ProactorEventLoop.sock_recvfrom_into()` OOB write (Windows), HIGH,
  divulguée 2026-04-21. **Aucune surface Genesis** : l'arc est numpy-seul, sans sockets asyncio.
- **Supply-chain *litellm*** (PyPI, mars 2026) — payload voleur de secrets à l'import. **Aucune
  dépendance Genesis** sur litellm. → **CVE_ACTIVES : aucune critique pour l'arc.**

### Axe 4 — Infra & data
- ClickHouse / NATS JetStream / Neo4j vectoriel / WebGPU. **Gated** : conditionnés au déploiement
  Observatory Phase 5+ (pas d'endpoint nouveau aujourd'hui).

### Axe 5 — Papers arXiv du jour
- *Fill–Spill–Merge: flow routing in depression hierarchies* (Barnes/Callaghan, NSF par.10263903 ;
  Springer 2025 « numerical consistency for classical flow routing »). **Applicable** à la couche
  World (hydrologie, Wave 64 `river_discharge`).
- *EvoSkills / AutoSkill / MUSE-Autoskill* (auto-évolution de skills LLM). **REJETÉ** : un arbre de
  skills piloté par LLM viole l'émergence-only (pas d'arbre tech scripté).
- *Emergence World* (2606.08367) — éval autonomie long-horizon. **Gated** (Phase 5 LLM, déjà backlog).

## SYNTHÈSE VEILLE (format obligatoire)

```
DÉCOUVERTE_1: Fill–Spill–Merge (depression-hierarchy flow routing) · couche World (hydrologie/Wave 64) · gain: lacs endoréiques émergents
DÉCOUVERTE_2: Emergence World long-horizon eval · couche Observatory/Social · gain: banc autonomie (déjà couvert Wave 58/60)
DÉCOUVERTE_3: EvoSkills/AutoSkill (skills LLM auto-évolutifs) · couche Agentic · REJETÉ (viole emergence-only)
CVE_ACTIVES: aucune critique pour l'arc (CVE-2026-3298 asyncio-Windows + supply-chain litellm — hors surface numpy-seule)
PAPER_DU_JOUR: Fill–Spill–Merge — applicable couche World, mais touche du code testé → COMBO_BACKLOG (pas cette session)
```

## Moteur de combinaison (étape 1)

```
COMBO_RETENU: C11 forced_draught (substrat depuis J+8) × la chaîne d'appareillage de la boucle agent
  Gain:         16ᵉ bouchée D12 (16/20) ; 2ᵉ appareillage agent ; vitrification kaolin + seuil cuivre vécus
  Coût:         ~2 h · complexité 2 · risque régression 1 (purement additif : new ActionKind/seek/smoke/tests)
  Couche:       Agentic (cognition)
  Intégration:  append "(forcedraught, _seek_forcedraught)" après kilnbuild ; gate has_built_kiln × inv_fuel
  ADR requis:   NON (affordance in-situ non-mutante, D10 gelé — pas de geo.mine_at)

COMBO_BACKLOG: Fill–Spill–Merge (lacs endoréiques) → ROADMAP P5. Touche river_discharge.py + son test de
               couplage → Wave World dédiée avec garde-fou non-régression, pas une session non surveillée.
COMBO_REJETÉ:  EvoSkills/AutoSkill — arbre de skills LLM = tech tree scripté, viole l'émergence-only.
```

## Décision

Pas de combo externe intégrable aujourd'hui (tous gated cargo/LLM/endpoint). Le combo retenu est
**interne** : câbler C12 `forced_draught` dans la boucle agent (D12 wire #16). Détail d'exécution :
[`../sprints/2026-06-30_D12-WIRE-C12-forced-draught.md`](../sprints/2026-06-30_D12-WIRE-C12-forced-draught.md).
