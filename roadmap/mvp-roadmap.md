# Roadmap MVP — Genesis Engine

## Phasage exécutif

```
Phase 0 ─► Phase 1 ─► Phase 2 ─► Phase 3 ─► Phase 4
4–6 sem   2–3 mois   3–4 mois    4–6 mois   6–12 mois
```

---

## Phase 0 — Fondations (4–6 semaines)

**Objectif** : poser les rails techniques et valider l'architecture.

### Livrables
- Mono-repo Bazel (Rust + TS + Python)
- CI/CD GitHub Actions + Argo CD (cible : staging Kubernetes)
- Design system observer (Next.js)
- ADR (Architecture Decision Records) pour 10 choix critiques
- SBOM + signing pipeline opérationnel
- Stack observabilité prête (OTel + Tempo/Mimir/Loki)

### Done quand
- `make dev` lance un hello-world simulé sur un node local
- `make canary` déploie une release signée sur staging
- `make replay` rejoue un snapshot bit-à-bit

### Equipe minimale
- 1 staff eng (architecture)
- 1 SRE / DevOps
- 1 dev front (Next.js / 3D)

---

## Phase 1 — Petit monde, 10 agents, besoins biologiques (2–3 mois)

**Objectif** : prouver que la boucle fonctionne.

### Livrables
- World engine 1×1 km, terrain, biomes simples
- 10 agents avec drives (faim, soif, sommeil, énergie)
- Cognition tier R0 (reflex policy PPO)
- Mort par négligence des drives
- Observer 3D simple (vue caméra libre + debug overlay)
- Logs OpenTelemetry de chaque action

### Critères de succès
- 10 agents survivent 24 h simulés sans intervention humaine
- 0 crash sur 100 simulations consécutives
- Determinism check vert (replay bit-à-bit)

### Équipe
+ 1 dev IA (RL)
+ 1 dev moteur (Rust)

---

## Phase 2 — Reproduction, mémoire, relations sociales (3–4 mois)

**Objectif** : faire émerger la première lignée.

### Livrables
- Génome + reproduction sexuée
- Mémoire épisodique (Qdrant) + mémoire relationnelle
- Cognition tier R1 (planner court horizon, MCTS)
- Détection événements « naissance, mort, parenté »
- Vue généalogique dans l'observer
- Système d'émotions (vecteur 8d, modèle Plutchik)

### Critères de succès
- Une lignée de 3 générations émerge
- Au moins 2 lignées coexistent
- Mémoire correctement consolidée pendant le sommeil
- Aucun comportement « impossible » (ex : agent mort qui bouge)

### Équipe
+ 1 ML eng (vector DB + memory)

---

## Phase 3 — Villages, économie, conflits (4–6 mois)

**Objectif** : observer l'émergence de structures sociales.

### Livrables
- Inventaire + actions économiques (donner, prendre, échanger)
- TigerBeetle pour transactions
- Construction de structures simples (abris)
- Cognition tier R2 (modèle du monde, rollouts imaginés)
- Détection groupes (spectral clustering sur graphe d'interactions)
- Première version Annaliste (chronique des événements)
- Dashboard économie + démographie

### Critères de succès
- Au moins une structure de leadership émerge dans une simulation
- Premier conflit organisé (>3 agents) observé
- Premier abri partagé construit
- Index de spécialisation économique > 0.3 (Gini de productivité par activité)

### Équipe
+ 1 game systems eng (mécaniques émergentes)
+ 1 data eng (analytics)

---

## Phase 4 — Civilisation émergente (6–12 mois)

**Objectif** : franchir le saut symbolique.

### Livrables
- Cognition tier R3 (théorie de l'esprit bayésienne)
- Mécanique de signaux audio + apprentissage par imitation
- Détection convergence de signal (proto-langage)
- Transmission culturelle parents-enfants
- Mécaniques de croyance / culte
- Dashboard culturel + arbre techno reconstitué
- Mode replay + branches contrefactuelles
- Mode time-scale ×100 et ×1000 stable

### Critères de succès
- Convergence d'au moins 5 signaux référents stables sur 3 générations dans une tribu
- Apparition d'au moins une innovation technologique (feu / outil) sans intervention
- Apparition d'une structure de pouvoir reconnaissable
- Stabilité 1000 ans simulés sans extinction totale

### Équipe (run rate Phase 4)
- 8–10 ingénieurs
- 1 chercheur ALife / cognition
- 1 product / scientifique
- 1 designer

---

## Risques majeurs & mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Pas d'émergence langagière | Mission critique | Plan B : déclencher une « pression de coordination » accrue (chasse coopérative obligatoire) |
| Coût GPU explose | Stoppe le scale | Start petit (Lab tier), MIG GPU, modèles compacts, distillation |
| Non-déterminisme insidieux | Casse la science | Tests determinism dès J1, lints, no wall-clock |
| Comportements pathologiques (agents qui tournent en rond) | Pas d'émergence | Curiosité intrinsèque (RND, ICM) dans la policy |
| Échec scientifique de l'expérience fondatrice (2 agents) | Récit faible | Garder le concept mais faire d'abord un MVP avec ~10 agents |
| Sécurité avatars utilisateurs | Légal/réputation | E2E + DPIA + red team |
| Vendor lock-in | Coût futur | OSS-first, abstractions, multi-cloud dès Phase 1 |
| Régulation IA (EU AI Act) | Bloquant | Classer le système, documentation, transparency reports |

## Métriques d'équipe

| Phase | KPI | Cible |
|---|---|---|
| 1 | Tick/s par sim node | ≥ 30 |
| 2 | Latence cognition p99 | < 50 ms |
| 3 | Coût $/agent/jour simulé | < $0.05 |
| 4 | Stabilité simu 1k ans simulés | ≥ 95 % |

## Open questions à clore avant Phase 5

- Modèle de monétisation (cloud usage, license recherche, scientific consortium)
- Politique d'accès aux simulations (open data ? embargo 12 mois ?)
- Comité d'éthique (avatars, conscience artificielle, droits des agents avancés)
- Position face au EU AI Act (high-risk system ?)
