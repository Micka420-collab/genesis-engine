# Stack IA & World Models

## Pourquoi pas un seul gros LLM par agent

| Approche | Problème |
|---|---|
| GPT-5 / Claude / Gemini par agent | $$$, latence trop forte, comportement *trop* humain → casse l'émergence |
| Petit MLP par agent | trop limité pour théorie de l'esprit / planning |
| Un méga-modèle qui simule N agents | non scalable, conflits avec sharding |

**Choix retenu** : pile **modulaire et hétérogène**, chaque agent assemble ses sous-modèles depuis un pool partagé GPU.

## Architecture cognitive concrète

```
       ┌─────────────────────────────────────────────────┐
       │              AGENT (entité légère ECS)          │
       │                                                  │
       │  state: drives, mood, memory_ptrs, genome       │
       │                                                  │
       │  policy_id ──────────► [Pool GPU partagé]       │
       │  world_model_id ─────► [Pool GPU partagé]       │
       │  perception_enc_id ──► [Pool GPU partagé]       │
       │  language_model_id ──► [Pool GPU partagé]       │
       │                                                  │
       └─────────────────────────────────────────────────┘
```

Les modèles sont **partagés** entre agents (un seul DINOv3 sert 100 000 agents). Les **paramètres individuels** sont des petits adaptateurs LoRA stockés par agent (1–10 MB), permettant la **personnalité unique** sans coût mémoire prohibitif.

## Les briques modèles

### 1. Encodeur perception (vision + audio)

- **DINOv3-Small** (~21 M params) : self-supervised vision. Robuste, généraliste.
- Alternative : **SigLIP-2** si l'on veut un encodage texte+image (utile pour ToM symbolique).
- Audio : **EnCodec / Mimi** pour tokeniser les sons.
- Output : embedding 384-d.

### 2. World Model (modèle prédictif du monde local)

- Architecture : **DreamerV3** modifié (recurrent state-space model).
- Entrée : embeddings perception + action passée.
- Sortie : prédiction `o_{t+1}, r_{t+1}` pour rollouts imaginaires.
- Couche optionnelle : **Genie-3-style interactive video model** pour des rollouts visuels riches (utile en R&D, désactivé en simulation massive).

### 3. Policy network

- Transformer compact (50–200 M params) avec context window 256 steps.
- Entraîné **en continu** (online RL) via **PPO + KL anchoring** sur la sortie d'une politique « parent » (évite le catastrophic forgetting).
- Sortie : distribution sur ~30 actions abstraites (`move(dx,dy)`, `eat`, `attack(target)`, `give(target,item)`, `vocalize(token)`, `mate(target)`, …).

### 4. Modèle de théorie de l'esprit (ToM)

- **Bayesian Inverse Planning** : `P(intention | observation) ∝ P(observation | intention) · P(intention)`.
- Léger, interprétable, ne demande pas de réseau de neurones lourd.
- Cumulé sur l'historique d'interactions avec un agent cible.

### 5. Modèle de langage (post-émergence uniquement)

- N'apparaît **pas** au démarrage de la simu.
- Lorsqu'un proto-langage devient stable (mesuré par mutual information signal/référent), un **Small LM 1–3 B** (Mistral-3B, Llama-3B small) est attaché à la culture.
- Fine-tuné en continu sur les corpus émergents (paroles transcrites, écritures gravées).
- Un LM par culture / tribu.

## Pool d'inférence

```
┌─────────────────────────────────────────┐
│  Triton Inference Server                │
│   ├── perception-enc.plan (FP8)         │
│   ├── world-model.plan (FP8)            │
│   ├── policy-tx-200m.plan (FP8)         │
│   └── small-lm-3b.plan (INT4 GPTQ)      │
│                                          │
│  Dynamic Batching: window = 5 ms         │
│  MIG slicing : 7 instances/H200         │
└─────────────────────────────────────────┘
```

Cible perf :
- Perception+World+Policy en **<20 ms** par tick (batché par 256)
- Small LM **<200 ms** par génération (1 par culture, pas par agent)

## Apprentissage continu

Trois régimes coexistent :

### a) Online RL léger (par agent)
- LoRA adapter mis à jour à chaque épisode (~10⁴ steps)
- Limite stricte sur le drift (KL < 0.05)

### b) Curriculum évolutionnaire (population)
- Les agents qui survivent + se reproduisent passent leurs **poids LoRA** (héritage culturel/cognitif partiel) à leurs descendants
- Sélection naturelle sur les **adaptateurs**

### c) Distillation périodique (offline)
- Tous les N ticks, on entraîne un nouveau **base model** sur les démonstrations des meilleurs agents
- Permet aux générations suivantes de partir d'un meilleur prior

## Mécanique du langage émergent

### Étape 1 — Babillage
Chaque agent émet des tokens audio aléatoires (vocab de 32 phonèmes).

### Étape 2 — Conditionnement
Si un signal corrèle avec un événement (proie, danger), les agents apprennent l'association via la mémoire épisodique.

### Étape 3 — Convention
Quand 5+ agents partagent une association signal-référent stable sur 3 jours simulés, l'**Annaliste** détecte un « mot ».

### Étape 4 — Vocabulaire
Construction d'un dictionnaire émergent par tribu (stocké côté observer, **invisible aux agents**).

### Étape 5 — Syntaxe
Émerge spontanément quand les agents combinent 2+ signaux pour des messages composés. Mesurée par compositional generalization tests.

### Étape 6 — Écriture
Émerge si une tribu invente une mémoire externe (gravure, peinture). Le moteur ne code que la possibilité de **graver un symbole sur un objet**.

## Garanties scientifiques

- **Pas de pré-entraînement linguistique** : les modèles ne connaissent pas le français/anglais avant la simu
- **Pas de fine-tuning sur des données humaines** dans la phase de civilisation pré-Niveau 6
- **Logs détaillés** : chaque association signal-référent est traçable
- **Reproductibilité** : seed → langage identique
