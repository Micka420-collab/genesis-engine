# Veille technologique — 2026-06-16 (J+6)

**Routine :** Morning Routine v3.0 — *veille-first*. Aucune ligne de code n'a été
écrite avant la clôture de cette veille.
**Mode :** scheduled task (user absent) · exécution autonome.

---

## ÉTAPE 0 — Veille (5 axes, recherches parallèles)

### Axe 1 — IA & agents
- **Memory for Autonomous LLM Agents** (arxiv 2603.07670, survey 2022→2026) ;
  **Multi-Agent LLM: From Emergent Collaboration to Structured Collective
  Intelligence** (Preprints 202511.1370) ; **Project Sid / PIANO** (arxiv
  2411.00114, civ 500–1000 agents). → Couche **Agentic/Social**. Pertinent mais
  conditionné à l'activation **LLM tier-2** (Phase 5), inactif en ère cargo-less.

### Axe 2 — Rust / ECS / moteur
- **Bevy 0.16** (GPU-driven rendering, ECS *entity relationships*, occlusion
  culling) et **0.17** (raytraced lighting, observers). → Couche **World (port
  Rust)**. Conditionné à **P1 scaffolding Rust vert** ; `cargo` absent ⇒ différé.

### Axe 3 — Crypto & sécurité
- **ML-KEM (FIPS 203)** : déploiements hybrides X25519+ML-KEM-768 en TLS 1.3/QUIC
  (Chrome/Firefox/Safari, CDN) ; Cisco FTD 10.5 fin 2026. Défenses **prompt
  injection** : *DefensiveTokens* (2507.07974), *Robustness via Referencing*
  (2504.20472). → **CVE_ACTIVES : aucune critique applicable** — Genesis n'expose
  *aucun endpoint réseau* en ère cargo-less (ADR-0008), donc aucune surface
  tokio/gRPC/PQC vivante ; l'invariant sandboxing tient (aucun agent LLM câblé).

### Axe 4 — Infra & data
- **NATS JetStream** : modèle de cohérence **linéarisable** en écriture (RAFT
  optimisé), intégration **ClickHouse** native (table engine + MV). → Couche
  **Observatory/Platform**. Conditionné au déploiement Observatory (Phase 5+).

### Axe 5 — Papers arXiv du jour
- **ARYA: A Physics-Constrained Composable & Deterministic World Model
  Architecture** (arxiv 2603.21340). → **PAPER_DU_JOUR.**
- **Emergence World: Long-Horizon Multi-Agent Autonomy** (arxiv 2606.08367) ;
  **Evolving Cognitive Architectures** (2601.05277) ; **Tri-Spirit / three-layer
  cognitive architecture** (2604.13757, déjà au backlog P5).

---

## SYNTHÈSE VEILLE (format obligatoire)

```
DÉCOUVERTE_1 : ARYA (world model composable + déterministe + physics-constrained)
               · couche World/Substrate · gain = cadre/validation de discipline
DÉCOUVERTE_2 : Emergence World (benchmark autonomie multi-agent long-horizon)
               · couche Social/Observatory · gain = métrique externe différée
DÉCOUVERTE_3 : DefensiveTokens (défense prompt-injection légère)
               · couche Agentic · gain = à activer avec le LLM tier-2 (Phase 5)
CVE_ACTIVES  : aucune critique applicable (0 surface réseau en ère cargo-less,
               ADR-0008 ; ML-KEM = standard, pas de CVE Genesis ; sandboxing tenu)
PAPER_DU_JOUR: ARYA (2603.21340) — *Physics-Constrained Composable & Deterministic
               World Model*. Apport DIRECT : sa thèse (déterminisme + composition
               sous contrainte physique) est exactement la discipline des capacités
               C1→C7. Valide la règle « C8 par composition pure, sans nouveau tell ».
```

---

## ÉTAPE 1 — Moteur de combinaison (COMBO-GENESIS)

```
COMBO_RETENU : ARYA (composabilité déterministe sous contrainte physique)
               × Cap. C8 lithic_tempering (transformation par composition)
  Gain        : valide/cadre la règle « transformation = composition de capacités
                déjà ground-truthées, 0 nouveau primitive » ; émergence (+1 capacité
                actionnable de transformation) ; +16 tests ; 0 surface réseau.
  Coût        : ~0 h d'intégration nette (le paper confirme le plan, pas un refactor)
                · complexité 1 · risque régression 1 (capacité additive, coût tick nul).
  Couche      : Substrate (runtime/engine Python).
  Intégration : C8 lit C2 (pierre) × C7 (feu) → tempered_quality déterministe borné ;
                aucune entrée PY_TO_RUST (garde-fou D8 par composition).
  ADR requis  : NON — confirme ADR-0005 (lecture L1) + ADR-0008 (frontière) existants.

COMBO_BACKLOG: Bevy 0.16/0.17 (World, conditionné P1) ; ML-KEM hybride (Platform,
               conditionné endpoint réseau) ; NATS/ClickHouse (Observatory, Phase 5+) ;
               Tri-Spirit / DefensiveTokens (Agentic, conditionnés LLM tier-2).
               → restent en ROADMAP P5 (garde-fou 60 j).
COMBO_REJETÉ : défenses prompt-injection *aujourd'hui* — aucun agent LLM câblé en
               ère cargo-less, surface inexistante (l'ajouter serait du code mort).
```

---

## ÉTAPE 2 — Audit & tâche du jour

- **PHASE :** 4 (émergence civilisationnelle) ; couches actives = Substrate +
  World (Python) + Observatory. **P0_BLOQUANTS : aucun.**
- **TÂCHE_JOUR** (audit J+5 §7) : **(b)** `crates/STATUS.md` *puis* **(a)** Cap. C8
  transformation par composition.
- **IMPACTÉ_PAR_VEILLE : OUI** — le COMBO_RETENU (ARYA) *fusionne* avec la tâche (a) :
  C8 est précisément la « transformation composable déterministe » que le paper décrit.

Livré ce jour : **(b)** `native/world-engine/crates/STATUS.md` (ferme R1, 23 crates
classées) **+ (a)** Cap. C8 `engine.lithic_tempering` (16 tests + smoke `p140` 7/7).
```
