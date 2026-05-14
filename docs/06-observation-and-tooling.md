# 06 — Observation & Tooling (mode « GOD »)

## Principe : observation passive

Le mode GOD permet d'**observer sans interagir**. Aucune action humaine ne modifie l'état de la simulation. C'est la condition de validité scientifique.

> Une seule exception : le **mode debug** réservé aux développeurs (étiqueté distinctement, désactivé en run scientifique).

## Modes de vue

### 1. Vue omnisciente (carte globale)
- Mappemonde 2D avec heatmaps overlay :
  - densité de population
  - tension économique (variance du Gini)
  - intensité des conflits
  - innovation rate (#nouvelles règles apprises / 1000 agents / siècle)
  - climat
- Zoom continu jusqu'à l'agent individuel (Mapbox-like)

### 2. Vue zoom — agent
- Pile complète : drives, émotions, mémoire récente, plan en cours, relations
- Journal de l'agent (auto-narration L7)
- Lignée généalogique
- Heatmap des lieux fréquentés

### 3. Vue cinématique
- Caméra automatique sur événements remarquables
- Détection : naissances, morts, batailles, premières inventions, mariages, fondations
- Replay automatique 30 s avant + 60 s après

### 4. First-person / third-person
- Incarner la perception d'un agent (sans contrôle)
- Utile pour comprendre **comment** l'agent voit le monde

### 5. Replay temporel
- Scrubbing par tick (forward/backward)
- Vitesse variable
- Branchement (« et si on rejouait depuis tick T avec graine différente ? »)

## Dashboards analytics

### Dashboard 1 — Démographie
- Pyramide des âges (live)
- Courbe de population sur 10⁶ ticks
- Taux de natalité / mortalité / espérance de vie
- Distribution génétique (PCA des génomes)
- Détection d'extinction de masse

### Dashboard 2 — Économie
- Inventaire global par ressource
- Index de Gini
- Volume des échanges (graphe par jour simulé)
- Carte des spécialisations
- Inflation (si monnaie a émergé)

### Dashboard 3 — Conflits
- Frise chronologique des conflits détectés
- Carte de chaleur des morts violentes
- Coalitions vivantes / défuntes
- Treaty stability index

### Dashboard 4 — Innovation
- Arbre technologique reconstitué (timeline + graph)
- Time-to-discovery
- Diffusion d'une invention (animée)

### Dashboard 5 — Culture & langage
- Phylogénie du proto-langage (matrice signal-référent par tribu)
- Glossaire émergent
- Index de mutual intelligibility entre tribus
- Frise des mythes/cultes

### Dashboard 6 — Climat
- Cartes T°, précipitations, vent
- Anomalies climatiques
- Corrélation climat ↔ démographie

### Dashboard 7 — Santé du moteur
- Tick rate effectif vs cible
- Latence inférence GPU (p50, p99)
- Coût $/heure
- Backlog event bus
- Drift entre nodes (HLC)

## Détecteurs d'événements

Un sous-système distinct (« Annaliste ») écoute le bus d'événements et reconstruit la **chronique** :

```
- Naissance / Mort
- Première fois qu'un agent fait X (innovation candidate)
- Convergence de signal (langage)
- Formation/dissolution d'un groupe >5 individus
- Construction d'une structure stable
- Bataille (>3 morts en <1 heure simulée dans une zone)
- Catastrophe naturelle
- Pandémie (R₀ > 2 sur 10 jours)
```

Chaque événement est :
- horodaté (tick)
- géolocalisé
- explicable (causes immédiates) — un trace OpenTelemetry-like

## Streaming live des observers

Plusieurs observers peuvent regarder simultanément la même simulation. Le serveur diffuse :
- l'état mondial (delta-encoded)
- les événements détectés
- une **vue stable** : tous les observers voient la même réalité

WebRTC + Protobuf delta-encoding pour l'efficacité.

## Export & reproductibilité scientifique

- **Snapshot** versionné = `{world_seed, tick, full_state_hash, agent_states, world_diff}`
- Format ouvert : Apache Arrow + Zstd
- Possibilité de **fork** une simulation à un tick donné avec une nouvelle seed pour les branches « contrefactuelles »
- **Article scientifique reproductible** : une simulation entière peut être rejouée bit-à-bit à partir de son snapshot initial + journal d'événements (zéro non-déterminisme dans le moteur — tous les RNG sont indexés par seed et chemin causal)
