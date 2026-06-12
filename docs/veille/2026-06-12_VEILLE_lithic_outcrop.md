# Veille technologique — 2026-06-12

> Routine matinale v3.0 — veille-first. Aucune ligne de code avant clôture de
> cette étape. 5 axes en parallèle, accès internet libre.

## Synthèse veille (format obligatoire)

* **DÉCOUVERTE_1** : *open-endedness / évolution culturelle* — TerraLingua
  (arXiv 2603.16910) + *Modelling the emergence of open-ended cultural evolution*
  (2508.04828) · couche **Sociétés-agents / Observation IA** · gain = métriques
  d'émergence soutenue. **REJETÉ aujourd'hui** : Waves 58 (Bedau–Packard) + 60
  (MAP-Elites/QD) couvrent déjà l'axe ; un 3ᵉ observateur = *observer treadmill*
  (audit §D1). On code une **capacité**, pas une mesure de plus.
* **DÉCOUVERTE_2** : *ML-KEM-768 × X25519 hybride généralisé* — TLS 1.3 par
  défaut, Go 1.24, K8s PQC, drafts IETF MLS/HPKE PQ · couche **Platform** ·
  gain = surfaces réseau post-quantiques. **BACKLOG** : aucune surface réseau dans
  le runtime Python live ; le moteur réseau est Rust, **non compilable ici**
  (`cargo` absent, cf. `reference_env_no_cargo`). CI = vérité.
* **DÉCOUVERTE_3** : *NATS JetStream 2.12* — atomic batch publish, counter CRDT,
  delayed message scheduling, linéarisabilité · couche **Platform/Observatory** ·
  gain = cohérence forte event-sourcing. **BACKLOG** (infra non compilable env).
* **CVE_ACTIVES** : aucune critique applicable au runtime Python live.
* **PAPER_DU_JOUR** : *TerraLingua* — conforte la trajectoire émergence ;
  **rien de directement applicable** à 7 jours qui ne soit déjà couvert.

## Moteur de combinaison (COMBO-GENESIS)

**COMBO_RETENU** : `mineral_catalog (obsidian/quartz + lithologies)` ×
`engine.geology (StrataLayer.rock_type + ore_mix)`
→ **Cap. C2 — perception d'affleurements de pierre taillable**.

* **Gain** : 1ʳᵉ découverte d'**outil lithique** émergente (la pierre taillée,
  technologie plus fondamentale que le minerai de C1). Sélectivité archéologique
  obsidienne > silex > quartzite > basalte. Dimension *Sociétés-agents* +75→…
* **Coût** : ~3 h · complexité 2 · risque régression 1 (lecture pure, zéro hook
  `sim.step`, zéro nouvelle `ActionKind`).
* **Couche** : Substrate / Géologie + Sociétés-agents.
* **Intégration** : indice `chunk → LithicCue` dérivé de la même colonne que
  `mine_at`, invariant « le monde ne ment jamais », cache paresseux.
* **ADR requis** : NON (tags ADR-0005 réutilisés : `Genesis-L1 Earth-Seed` /
  `paper-L1 Predictor`, conformes à l'allow-list).

**Pourquoi maintenant** : l'audit (`AUDIT-DELTA-2026-06-11`) formalise le risque
*observer treadmill* — 14 Waves d'observateurs, capacités d'action stagnantes.
C1 (2026-06-11) a rompu la série côté **minerai métallique** ; C2 la prolonge
côté **pierre taillée**, chronologiquement antérieure. Émergence absolue : on
rend l'affleurement **détectable**, on ne dit jamais « ceci taille bien ».

**COMBO_BACKLOG** : provenance volcanique de l'obsidienne (gate `basalt` dans la
colonne) — à traiter côté `engine.geology` (source de distribution), noté dans le
sprint C2 §"Gaps honnêtes".

**COMBO_REJETÉ** : observateur open-endedness (treadmill) ; PQC/NATS (Rust non
compilable dans cet environnement Python-seul).

## Sources

- TerraLingua: Emergence and Analysis of Open-endedness in LLM Ecologies — arXiv 2603.16910
- Modelling the emergence of open-ended cultural evolution — arXiv 2508.04828
- From X25519 to X25519+MLKEM768: How Hybrid TLS Is Becoming Real — postquantumsecurity.org
- Post-Quantum Cryptography in Kubernetes — kubernetes.io/blog/2025/07/18/pqc-in-k8s
- NATS 2.12 — What's New — docs.nats.io/release-notes/whats_new/whats_new_212
