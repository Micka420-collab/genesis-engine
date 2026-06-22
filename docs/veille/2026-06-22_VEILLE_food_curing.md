# Veille technologique — 2026-06-22 (J+12)

**Mode :** scheduled task (routine veille-first), run **automatique**, user
**absent**. **Contrainte env :** `cargo`/`rustc` absents
([ADR-0008](../../adr/0008-python-rust-frontier.md), D7) ; Python 3.14 seul ; CI =
vérité pour toute affirmation Rust. La veille **précède** tout code (règle d'or).

---

## ÉTAPE 0 — 5 axes de recherche

### Axe 1 — IA & agents (couche Agentic / Social)
Multi-agent civilization sims toujours actifs : *Project Sid* (PIANO, émergence de
lois/religion/économie dans Minecraft), *AgentSociety* (2502.08691), *AIvilization
v0* (2602.10429), *Emergent Social Intelligence Risks* (2603.27771). **Aucun
n'est intégrable cargo-less / sans LLM tier-2** → reste **BACKLOG P5** (déjà
inscrit). Genesis exploite l'émergence *substrat* (stone-age déterministe), pas
encore l'agent LLM — frontière inchangée.

### Axe 2 — Rust / ECS / moteur (Substrate / World)
**Bevy 0.18** (mars 2026) : editor preview, perf du scheduler ECS, pipeline
d'assets stabilisé, écosystème (input/UI/audio/physics) mûri. **Gated `cargo`**
(ADR-0008) → BACKLOG P5 ; ROADMAP mis à jour 0.16 → **0.18**.

### Axe 3 — Cryptographie & sécurité (Platform)
`ml-kem` (RustCrypto, FIPS 203, constant-time) sans audit indépendant. **Unique
CVE PQC** : `CVE-2026-22705` (ML-DSA, timing side-channel, **medium, patchée**
rc.2). **Aucune surface live Genesis** (PQC non compilée, aucun endpoint réseau).
Pas de CVE `tokio` active dans les sources. → BACKLOG (X-Wing KEM hybride déjà en P5).

### Axe 4 — Infra & data (Observatory / Platform)
**Signal neuf et pertinent : Deterministic Simulation Testing (DST)** — sessions
QCon London 2026 et FOSDEM 2026 (« seeds + state machines en Rust », TickLoom en
Java). Principe : exécuter le système sur un simulateur **mono-thread**, injecter
des fautes aléatoires, **rejouer la trace exacte depuis un seed**. C'est le **calque
direct de la discipline déterminisme/seed de Genesis** (signatures SHA-256, runs
seed-à-seed). Applicable **cargo-less** comme un mode du harnais
`runtime/experiments/run_all.py` (injection de fautes + replay seed). → **BACKLOG
devtools (axe 6)**, ROADMAP P5.

### Axe 5 — Papers arXiv du jour (Social / Agentic)
Sur le créneau « artificial life / émergence / agents » : rien de **nouvel
applicable sous 7 j** au substrat stone-age déterministe. Les ABM alimentaires
trouvés (Listeria en agro-industrie, acceptation de marché) ne concernent pas
l'émergence stone-age. **PAPER_DU_JOUR : rien d'applicable.**

---

## SYNTHÈSE VEILLE (format obligatoire)

- **DÉCOUVERTE_1 :** Deterministic Simulation Testing (QCon/FOSDEM 2026) · couche
  Observatory/devtools (axe 6) · gain : harnais de régression seed-reproductible,
  calque de la discipline existante · **combo INTERNE viable cargo-less** (~4 h).
- **DÉCOUVERTE_2 :** Bevy 0.18 · couche World (port Rust) · gain : perf ECS /
  editor · **gated `cargo`** → BACKLOG.
- **DÉCOUVERTE_3 :** multi-agent civ (Project Sid / AgentSociety / AIvilization) ·
  couche Social/Agentic · gain : bancs d'émergence long-horizon · **gated LLM
  tier-2** → BACKLOG.
- **CVE_ACTIVES :** `CVE-2026-22705` (ML-DSA timing, medium, **patchée**) —
  **aucune critique, aucune surface live Genesis**.
- **PAPER_DU_JOUR :** rien d'applicable sous 7 j.

## ÉTAPE 1 — COMBO-GENESIS

- **COMBO_RETENU (interne, le vrai combo du jour) :** `salt_evaporation` (C15 — le
  **produit** sel) **×** `physiology`/alimentation × le champ macro de température
  (climat). Effet 1+1>2 : le sel rendu récoltable par C15 devient l'**intrant** de
  la conservation ; sans lui, pas de préservation. → **Cap. C16 `food_curing`**
  (salaison). Couche : Substrate (perception/action). ADR requis : **NON**
  (composition, aucune frontière nouvelle ; D8 par composition, D10 gelé).
- **COMBO_BACKLOG :** DST → harnais `run_all.py` (ROADMAP P5, devtools).
- **COMBO_REJETÉ :** Bevy 0.18 / multi-agent LLM (gated cargo / LLM tier-2, hors
  ère cargo-less).

> Conclusion : la veille n'a produit **aucun combo externe intégrable** (tous
> gated). Le run exécute la reco d'audit `R-J9r2-3 (a)` (salaison) via le combo
> interne C15 × climat. Détail dans
> [`AUDIT-DELTA-2026-06-22.md`](../../native/world-engine/AUDIT-DELTA-2026-06-22.md).
