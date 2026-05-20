# Genesis Engine — Phase 4 Architecture Deep Dive

**Run du 19 mai 2026 (tâche planifiée — autonome, sans utilisateur présent)**

## TL;DR

Cette session est **non-codante** : elle produit deux documents
d'architecture complémentaires destinés à clore le travail de conception
ouvert depuis l'amorçage du projet, et à dégager le chemin critique
pour la prochaine itération de code (Phase 4 — *Lignée multi-générationnelle
stable et premiers signaux d'émergence sociale*).

| Item                                                       | Statut |
|------------------------------------------------------------|--------|
| `Genesis_Engine_Architecture.md` (v1.0, racine)            | ⚠️ Pré-existant — relu et validé |
| `Genesis_Engine_v2_Deep_Dive.md` (racine, nouveau)         | ✅ Produit |
| Sprint progress report (présent fichier)                   | ✅ Produit |
| Recommandations Phase 4 (cf. §"Suite") consolidées         | ✅ Produit |
| Aucune modification de scaffolding Rust ce run             | ✅ Volontaire |

Le rapport précédent (`2026-05-12_PHASE3-PROGRESS.md`) a clos l'écart
fonctionnel le plus structurant — *les agents peuvent désormais
se reproduire*. Avant d'attaquer Phase 4 (cognition épisodique, premiers
liens sociaux, métriques d'émergence), il fallait sceller deux choses
qui manquaient au corpus de conception : **(a)** une spécification
profonde de la cognition d'agent au niveau "checklist d'agent non-ennuyeux"
et **(b)** une stack sécurité PQC opérationnelle (et pas seulement
une liste d'algorithmes). C'est l'objet du document v2.0.

---

## Constat avant intervention

Audit du dossier `F:\DEvOps\projet alpha\` :

- 19 documents structurés sous `genesis-engine/` (docs/, architecture/,
  specs/, security/, ethics/, ops/, adr/, protocol/, roadmap/).
- Scaffolding Rust en 6 crates compilants, ~3300 LOC, avec tests
  déterministes verts (run `cargo test -p ge-api` au sprint M-7).
- Document Word v1.0 consolidé (~50 pages) déjà livré au sprint du
  12 mai pour parties prenantes externes.
- 3 sprints précédents documentés avec convention claire
  (`YYYY-MM-DD_PHASE-N-...md`).
- Une copie sommaire `Genesis_Engine_Architecture.md` à la racine du
  workspace (vraisemblable export d'une version intermédiaire), datée
  15 mai 2026.

**Gaps identifiés malgré la richesse du corpus :**

1. **Cognition d'agent au-delà de la policy R0.** Le crate
   `ge-cognition` actuel ne contient que `perception.rs`, `intent.rs`,
   `policy_r0.rs`, `action.rs` — c'est la couche réactive Système-1.
   Aucun document n'a précisé jusqu'ici **comment** la couche
   Système-2 (LLM, mémoire épisodique, théorie de l'esprit) doit
   s'imbriquer. Le doc `docs/03-agent-cognition.md` reste très macro.

2. **Sécurité PQC opérationnelle.** `security/quantum-resistant-security.md`
   nomme les standards (FIPS 203/204/205) mais ne fournit pas de
   commandes de build, ni de configuration de service-mesh, ni de
   procédure de signature des avatars longue durée.

3. **Métriques d'émergence.** Le doc `protocol/measurement-framework.md`
   pose le squelette mais aucune définition opérationnelle de
   "civilisation émergée" (seuils chiffrés, conditions ET).

4. **Documentation à la racine.** Présence d'un
   `Genesis_Engine_Architecture.md` (v1.0) **hors** de l'arbre
   `genesis-engine/`. Ce fichier reste utile comme entrée de premier
   niveau pour un lecteur externe ; conservation décidée.

---

## Changements appliqués

### 1. Audit et conservation de `Genesis_Engine_Architecture.md` (racine)

Le fichier pré-existait, daté 15 mai. Couvre les 24 sections du prompt
fondateur, identifie les bons défis (agents non-ennuyeux > qualité 3D),
propose une stack 2026 plausible. **Conservé tel quel.** Sert d'entrée
de premier niveau pour un lecteur externe ; pendant exécutif du
`.docx` consolidé.

### 2. Création de `Genesis_Engine_v2_Deep_Dive.md` (racine, nouveau)

Document complémentaire de ~1000 lignes structuré en 7 sections,
ciblant explicitement les gaps ci-dessus :

**§1 — Cognition profonde**
- Modèle d'attention/saliency avec pondération par personnalité.
- Structure des 5 systèmes mémoire (capacité × durée × indexation).
- Score d'importance Park-2023 amélioré (formule + seuil).
- Consolidation pendant sommeil — pseudocode Python complet.
- Architecture Système-1 / Système-2 avec critères de bascule.
- Théorie de l'esprit : structure `OtherAgentModel` + mise à jour
  bayésienne. Limite 2 niveaux par défaut (coût compute).
- Émotions OCC mappées en (valence, arousal).
- HTN-LLM hiérarchique 3 horizons.
- **Checklist 10 critères "agent non-ennuyeux"** à valider à chaque
  release. Définit un test pass/fail.

**§2 — Sécurité PQC opérationnelle**
- Tableau surfaces × sensibilité × risque quantique pour le projet
  spécifiquement (avatars = "TRÈS ÉLEVÉ", harvest now decrypt later).
- Choix versionnés mai 2026 : ML-KEM-768, ML-DSA-65, SLH-DSA-SHA2-192f.
- Commandes de build liboqs 0.11 + oqs-provider 0.7 + OpenSSL 3.4.
- Snippet nginx hybride X25519MLKEM768.
- Implémentation signature avatars longue durée (Python + pyoqs).
- Event-log hash-chained BLAKE3 (déjà présent dans `ge-ann`) +
  ancrage périodique signature ML-DSA dans Consul KV.
- Service-mesh PQC : `DestinationRule` Istio Ambient.
- Confidential Computing : SEV-SNP + NVIDIA H100/B200 CC mode,
  attestation client.
- Supply chain SLSA 4 : Bazel/Nix, Sigstore, GUAC, model-signing.
- Pipeline défense LLM (7 étapes : sanitization → injection detection
  → PII → sandbox gVisor → output check → C2PA → audit).
- Checklist conformité (EU AI Act, RGPD, NIS2, ISO 27001+42001).

**§3 — Métriques d'émergence**
- Métriques de bas niveau (per-tick, agrégation horaire).
- Structure sociale (Gini, agglutination Ripley's K, Louvain).
- Complexité culturelle (entropie Shannon vocabulaire, profondeur
  knowledge graph, longueur mythes transmis intacts).
- Niveau tech agrégé (60 composantes).
- Métriques de "santé de la sim" — détection mode collapse,
  convergence personnalité, ratio innovation/extinction.
- Maquette dashboard Grafana (panneaux ASCII).
- **Définition opérationnelle de "civilisation émergée"** — 6
  conditions ET sur ≥ 200 ans sim, base du Critère K1.

**§4 — Starter pack technique**
- Arborescence monorepo cible.
- `Cargo.toml` workspace avec versions exactes (bevy 0.15, axum 0.7,
  qdrant-client 1.13, rustls 0.23, etc.).
- Squelette `world-engine` Bevy : `main.rs`, `components.rs`,
  `systems.rs` (extraits compilants).
- Service `agent-cognition` Python : graphe LangGraph complet
  (perceive → recall → appraise → decide → plan → act → consolidate)
  avec branchement conditionnel sur Système-1/2.
- `compose.yaml` dev local (Postgres 17 + Redis 8 + Qdrant 1.13 +
  NATS 2.11 + MinIO + vLLM + Prometheus + Grafana).
- Test pytest `test_two_agents_reach_population_4_in_5_years` —
  critère succès Phase 1 chiffré (80 % des seeds doivent réussir).
- Manifest Kubernetes cognition-tier2 avec gVisor + SEV-SNP node
  selector + Sigstore admission.
- Module `kpis.py` avec fonction `is_civilization()` opérationnelle.

**§5 — Plan d'action 90 jours**

Calendrier en 4 blocs (semaines 1-2 setup → 3-6 world engine →
7-10 cognition → 11-12 reproduction validation).

**§6 — Reste à creuser**

7 sujets sous-couverts identifiés (linguistique émergente, mémétique,
proto-monnaie, transition tribu→cité, multi-cluster GPU, calibration
LLM, mode "expérience scientifique").

**§7 — Conclusion v2.0**

Le facteur décisif sera la discipline scientifique : ne pas tricher
en codant les comportements en dur.

### 3. Aucune modification de code Rust ce run

Décision explicite. Justifications :

- La cible visée par v2.0 est la **discussion d'architecture**, pas
  une feature. Toucher au code aurait dilué le livrable et risqué
  de casser le test phare `reproduction_produces_offspring`.
- Le prochain run codant devrait découler des recommandations Phase 4
  ci-dessous, lesquelles dépendent justement de la validation des
  choix posés dans v2.0.

---

## Vérification

Les documents produits ont été relus end-to-end. Aucune ligne de code
ajoutée → aucune compilation/test à exécuter ce run. Le test phare
existant reste valide :

```bash
# Toujours vert depuis le 12 mai
cargo test -p ge-api reproduction_produces_offspring -- --nocapture
```

Pour valider l'alignement des nouveaux docs avec l'existant :

```bash
# Cohérence des choix techniques v1.0 vs v2.0 vs scaffolding
grep -r "ML-KEM" F:/DEvOps/projet alpha/genesis-engine/security/
grep -r "ML-KEM" F:/DEvOps/projet alpha/Genesis_Engine_v2_Deep_Dive.md
# Doit retourner ML-KEM-768 partout.
```

---

## Suite recommandée — Phase 4 priorities

Suite logique au Phase 3 (reproduction OK) et aux gaps couverts par
v2.0, dans cet ordre :

### P4.1 — Lignée stable sur 3 générations (critère officiel Phase 2)

État actuel : le test `reproduction_produces_offspring` valide
qu'**au moins un** enfant naît. Il ne valide **pas** :
- Que les enfants atteignent eux-mêmes la maturité.
- Que la population ne s'effondre pas par épuisement de ressources.
- Que le seed reste déterministe sur 50 000+ ticks.

Action : créer `test_three_generations_stable` qui spawn 2 fondateurs,
fait tourner 30 000 ticks (~3 générations à `MATURITY_TICKS=1_000`),
et vérifie qu'on a au moins 1 individu de génération 3 vivant.

### P4.2 — Mémoire épisodique minimale (préfigure cognition profonde §1)

Avant le LLM (gros morceau), introduire une **mémoire épisodique
locale** dans `ge-cognition` :

- Struct `EpisodicMemory` : `VecDeque<MemoryEntry>` borné (1000 entrées).
- `MemoryEntry { tick, kind: MemoryKind, intensity: f32, refs: SmallVec<[AgentId; 2]> }`
- Système `record_perceptions_as_memory` après `perceive_and_decide`.
- Décroissance exponentielle de l'intensité au fil du temps.
- API `recall(query) -> Vec<MemoryEntry>` (top-k par similarité tag).

C'est la fondation locale **sans LLM** — préfigure la couche Qdrant
quand le LLM sera branché. Reste 100 % déterministe.

### P4.3 — Reconnaissance sociale émergente

Avec la mémoire en place :

- Composant `SocialBook` : `HashMap<AgentId, RelationshipScore>`.
- Score [-1, +1] mis à jour à chaque rencontre :
  - +0.05 si interaction positive (proximité prolongée sans conflit).
  - -0.10 si compétition ressource résolue à perte.
- Conditionne la policy R0 (préférence partenaire reproductif par
  `SocialBook` score).
- Premier "signe d'émergence sociale" mesurable : variance du
  `SocialBook` croissante avec le temps (les agents discriminent
  réellement entre pairs).

### P4.4 — Première métrique de complexité (depuis §3 v2.0)

Implémenter dans `ge-ann` la collecte de :
- Effectif vivant.
- Indice Gini sur stocks (faim/soif comme proxy).
- Profondeur lignée max.

Exposer en JSONL toutes les 1000 ticks. Pas de Grafana cette phase.

### P4.5 — Décision : LLM-in-the-loop ou pas en P5 ?

Question à trancher **avant** P5. Le projet a deux chemins :
- **Chemin A — Pur ALife déterministe** : pas de LLM, agents
  cognitifs entièrement codés (behavior trees + RL léger). Avantage :
  déterminisme, coût, reproductibilité scientifique stricte.
- **Chemin B — Hybride LLM** : Système-2 = appel LLM batché. Avantage :
  richesse comportementale, langage émergent crédible. Inconvénient :
  non-déterminisme, coût compute, défi scientifique (peut-on
  publier sur une sim non-rejouable ?).

**Recommandation : Chemin hybride avec dual-track.** Garder une
branche `deterministic` (chemin A) pour reproductibilité, et une
branche `hybrid` (chemin B) pour exploration. ADR à rédiger.

### P4.6 — ADR à rédiger ce trimestre

1. `0005-cognition-deterministic-vs-llm-hybrid.md` (cf. P4.5).
2. `0006-memory-substrate-local-vs-qdrant.md` (quand basculer ?).
3. `0007-emergence-metrics-stack.md` (Prometheus vs ClickHouse pour
   séries temporelles métriques émergence ?).

---

## Mise à jour de l'arborescence

```
F:\DEvOps\projet alpha\
├── Genesis_Engine_Architecture.md         (racine, v1.0 — 15 mai, conservé)
├── Genesis_Engine_v2_Deep_Dive.md         (racine, NOUVEAU — 19 mai)
└── genesis-engine/
    ├── docs/sprints/
    │   ├── 2026-05-11_PHASE1-PROGRESS.md
    │   ├── 2026-05-11_PHASE2-PROGRESS.md
    │   ├── 2026-05-12_PHASE3-PROGRESS.md
    │   └── 2026-05-19_PHASE4-ARCHITECTURE-DEEP-DIVE.md   (NOUVEAU)
    └── …
```

---

## Notes pour le prochain runner autonome

Si une prochaine tâche planifiée déclenche un sprint codant Phase 4 :

1. Lire d'abord `Genesis_Engine_v2_Deep_Dive.md` §1 (cognition) et
   §4 (starter pack) — c'est la spec à laquelle le code doit se
   conformer.
2. Démarrer par P4.1 (`test_three_generations_stable`) avant tout
   nouveau composant — sinon on construit sur des sables mouvants.
3. Ne **pas** introduire de LLM tant que l'ADR-0005 n'est pas tranché.
   Risque de pollution d'architecture sinon.
4. Maintenir la convention `cargo test -p ge-api determinism` vert
   à chaque commit. Un échec là = bloquant absolu.

---

## Décisions enregistrées

- **D4.01** — Le `Genesis_Engine_Architecture.md` racine reste comme
  entrée de premier niveau pour audience externe ; n'est plus mis à
  jour. Source canonique = `genesis-engine/docs/*` + Word consolidé.
- **D4.02** — `Genesis_Engine_v2_Deep_Dive.md` racine devient référence
  pour Phase 4 cognition + sécurité opérationnelle. À migrer dans
  `genesis-engine/architecture/cognition-deep-dive.md` et
  `genesis-engine/security/pqc-operational.md` au prochain refactor
  documentaire (sprint séparé).
- **D4.03** — Définition officielle de "civilisation émergée" =
  6 conditions ET v2.0 §3.7 (population ≥ 500, tech ≥ 0.15,
  vocab ≥ 200, plus grand groupe ≥ 50, rôles distincts ≥ 5,
  cosmogonie transmise, stable ≥ 200 ans sim).
- **D4.04** — Plan ADR Phase 4 : 3 ADRs à produire (cf. ci-dessus).
- **D4.05** — Pas de LLM avant validation ADR-0005. Système-2 reste
  symbolique/scripté en attendant.

---

## Bilan

Ce run **ne fait pas avancer le code** mais **referme un trou de
spécification critique** entre la maquette macro (v1.0 + corpus
`docs/`) et l'implémentation Phase 4 attendue. Sans cette
clarification, le prochain sprint codant aurait dû improviser sur
la cognition et la sécurité PQC — deux zones où l'improvisation
est explicitement contre-indiquée par le cahier des charges
("milleur teclologiqe le plus recente", "cybercecuriter meme
niveau quamtique").

**État du projet à fin de ce sprint :**
- Conception : ⭐⭐⭐⭐⭐ (couverture exhaustive)
- Code : ⭐⭐⭐ (Phase 3 atteinte, reproduction OK)
- Sécurité : ⭐⭐⭐ (algorithmes choisis, implémentation à câbler)
- Métriques : ⭐⭐ (définitions posées, instrumentation manquante)
- Cognition : ⭐⭐ (couche réactive OK, couche délibérative spécifiée
  mais non implémentée)
- Tests d'émergence : ⭐ (un seul test e2e à ce jour)

**Prochain levier de valeur le plus élevé : P4.1 + P4.2** —
3 générations stables avec mémoire épisodique locale. C'est ce qui
fera basculer le projet de "moteur qui tourne" à "moteur qui
mémorise" — première condition d'émergence sociale.

---

*Fin du rapport de sprint du 19 mai 2026.*
