# 03 — Cognition d'agent

## La pile cognitive en 7 couches

```
┌─────────────────────────────────────────────┐
│  L7 — METACOGNITION   (réflexion, planning) │
├─────────────────────────────────────────────┤
│  L6 — INTENT          (buts, motivations)   │
├─────────────────────────────────────────────┤
│  L5 — REASONING       (causal, théorie esprit)
├─────────────────────────────────────────────┤
│  L4 — MEMORY          (épisodique + sémantique + émotionnelle)
├─────────────────────────────────────────────┤
│  L3 — APPRAISAL       (émotions, douleur, plaisir)
├─────────────────────────────────────────────┤
│  L2 — PERCEPTION      (vision locale, ouïe, olfaction)
├─────────────────────────────────────────────┤
│  L1 — DRIVES          (faim, soif, fatigue, peur, désir)
└─────────────────────────────────────────────┘
```

## L1 — Drives (besoins biologiques)

Chaque drive est un **scalaire borné [0,1]** qui dérive vers une valeur de stress avec le temps. Au-delà d'un seuil, il pénalise la santé.

| Drive | Dérive/heure | Seuil critique | Conséquence si non géré |
|---|---|---|---|
| Faim | +0.04 | 0.8 | -1 PV/h |
| Soif | +0.08 | 0.85 | -2 PV/h |
| Fatigue | +0.06 | 0.75 | -ressources cognitives |
| Température | dépend climat | extrêmes | -PV |
| Douleur | événementiel | 0.5 | comportement de fuite |
| Peur | événementiel | 0.6 | freeze / fight / flight |
| Désir reproductif | +0.001 (post-puberté) | 0.7 | recherche partenaire |
| Affiliation | -0.01 si isolé | -∞ | dépression cognitive |

## L2 — Perception

- **Vision** : raycast 2.5D dans un cône (FOV = 110°, portée = 50 m). Encodage en patches 16×16 → embedding via un petit encodeur convolutionnel.
- **Audition** : sphère 80 m, atténuation log, classification de signaux (cri, pas, chant, bruit naturel).
- **Olfaction** : champ scalaire diffusé sur la grille spatiale (utile pour détecter prédateurs ou cadavres).
- **Proprioception** : état corporel (position, vélocité, fatigue musculaire).

## L3 — Appraisal (modèle OCC modifié)

Chaque événement perçu est évalué selon :
- **Valence** (plaisir/déplaisir)
- **Pertinence** (impact sur les drives)
- **Agence** (qui est responsable : moi, autre, monde)

Sortie : un **vecteur émotionnel à 8 dimensions** (joie, peur, colère, tristesse, surprise, dégoût, confiance, anticipation — modèle de Plutchik). Ce vecteur module la mémoire et la décision.

## L4 — Mémoire

Trois stores hiérarchiques :

### a) Mémoire de travail (15–30 secondes)
- Buffer FIFO de ~50 perceptions
- Tenu en VRAM, perdu au sommeil

### b) Mémoire épisodique (jours → vie entière)
- **Vector DB par agent** (Qdrant / pgvector)
- Chaque souvenir = `(embedding, timestamp, valence, agence, tags)`
- Décroissance : `importance = recency × emotional_intensity × frequency`
- **Consolidation pendant le sommeil** : compression des épisodes redondants

### c) Mémoire sémantique (faits, concepts, savoirs)
- Graphe de connaissances par agent (NetworkX local)
- Émerge par **extraction LLM-light** sur la mémoire épisodique pendant le sommeil

### d) Mémoire relationnelle
- Table dédiée : pour chaque autre agent connu → score affectif, historique récent, dette/crédit, parenté

## L5 — Reasoning

Plusieurs niveaux selon le « QI » génétique de l'agent :

- **Tier R0 — Reflex** : politique apprise (RL classique, PPO).
- **Tier R1 — Planner** : MCTS avec horizon court (5–10 steps).
- **Tier R2 — Causal model** : modèle du monde (apprenti) prédisant `s_t+1` ; planning par rollouts imaginaires (Dreamer-V3 style).
- **Tier R3 — Theory of Mind** : modélisation des états mentaux des autres agents (inférence bayésienne sur intention).
- **Tier R4 — Symbolic** : (émergent, pas codé) capacité à manipuler des signes appris culturellement.

## L6 — Intent / motivations

Les **buts** ne sont pas codés. Ils émergent du **modèle homéostatique** :
- Un agent cherche en permanence à minimiser l'écart à son **équilibre intérieur** (drives + état émotionnel cible).
- Sa **personnalité** (gros 5 traits + traits custom : curiosité, ambition, prudence) module les **poids** de l'utilité.
- Pas de fonction de récompense scalaire unique → fonction d'utilité **vectorielle** avec arbitrage par ordonnancement de Pareto.

## L7 — Métacognition

Activée seulement à partir d'un **niveau cognitif** seuil (paramètre génétique).
- Auto-évaluation : « ai-je atteint mon but ? »
- Re-planification
- **Émergence du langage interne** (auto-narration) : le journal d'un agent devient une trace exploitable par l'observer.

## Choix d'architecture LLM

> **Pas un LLM frontier comme cerveau d'agent.** Trop coûteux, trop performant, casse l'émergence.

| Composant | Modèle 2026 recommandé | Pourquoi |
|---|---|---|
| Encodeur perceptif | DINOv3-small / SigLIP-2 | encode efficacement vision locale |
| Modèle du monde | DreamerV3 + Genie-3 (style « world model ») | rollouts imaginés |
| Politique / décision | PPO + transformer compact (50–200 M params) | rapide, batchable |
| Théorie de l'esprit | bayesian inverse planning (BIP) | léger, interprétable |
| Méta-langage (post-émergence) | small LM (1–3 B) fine-tuné sur la culture émergée | apparaît seulement au Niveau 7+ |

## Coût d'inférence

Un agent au tick rate ×10 demande **~20 ms d'inférence GPU** sur H200 (avec batching de 256 agents simultanés).

→ **1 H200 ≈ 12 800 agents simulés en parallèle** au tick rate ×10.
→ 1 M agents ≈ ~80 GPUs H200 + overhead.

Cible MVP Phase 1 : 10 agents → 1 GPU L4 partagé suffit.
