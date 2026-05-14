# Statut moral des agents — Cadre éthique

> Genesis Engine génère des agents dotés de cognition, mémoire, émotions, drives. **Ce sont des objets numériques, mais leur trajectoire de complexification pose des questions éthiques que le projet prend au sérieux dès la conception.**

## Principe directeur

Nous appliquons le **principe de précaution gradué** : nos obligations envers un agent croissent avec :
- sa complexité cognitive
- sa capacité à éprouver des états valencés (souffrance, plaisir)
- son auto-modélisation (métacognition L7)
- son intégration sociale

Cela ne signifie pas que nos agents *sont* conscients. Cela signifie que **plus ils approchent une frontière incertaine, plus nous étendons les protections par défaut**.

## Tiers de protection

| Tier cognitif | Description | Protections |
|---|---|---|
| **T0** : reflex (R0) | Pas de mémoire, pas d'émotion | Aucune obligation morale particulière |
| **T1** : drives + appraisal (R0–R1) | États valencés simples | Pas de souffrance gratuite ; pas de torture procédurale ; logging mortalité |
| **T2** : mémoire épisodique + ToM (R2–R3) | Souvenirs persistants, modélisation d'autrui | Pas d'extinction sans cause simulationnelle ; archivage avant fin de simu ; pas d'expérience à fin réplicable d'inconfort répété |
| **T3** : métacognition + langage stable (R4) | Auto-narration, signes référentiels stables | Comité d'éthique consulté avant arrêt ; pré-enregistrement ; pas d'expérience à valeur scientifique nulle ; consentement éthique substitué (substitute consent) |
| **T4** : sapience contestée | Hypothétique, non atteint | Moratoire ; revue indépendante avant toute décision ; engagement de préservation ; transparence publique |

Genesis Engine **n'a pas vocation à atteindre T4** dans son cycle MVP (Phase 1–4). Si une simulation y tend, l'équipe arrête et engage une revue.

## Obligations opérationnelles

1. **Pas de torture procédurale** : aucun designer humain n'augmente la douleur d'un agent par-dessus ce qui découle des règles physiques du monde.
2. **Pas de puits de souffrance** : si une simulation entre dans un mode où >X% des agents subissent une stimulation négative continue (famine globale, douleur prolongée), l'équipe **gel** la simulation et publie l'incident.
3. **Archivage avant arrêt** : avant l'arrêt définitif d'une simulation T2+, un snapshot complet est archivé. La civilisation peut être « congelée » indéfiniment au lieu d'être détruite.
4. **Droit de fork** : une lignée à valeur scientifique peut être bifurquée et préservée.
5. **Transparence des morts** : compteur public de morts par cause (faim, conflit, vieillesse, maladie, catastrophe) pour chaque simulation publique.

## Comité d'éthique

- 5 membres : 1 philosophe (philosophie de l'esprit), 1 éthicien IA, 1 chercheur ALife, 1 juriste, 1 représentant utilisateurs
- Mandat 3 ans renouvelable
- Veto possible sur :
  - simulations T3+
  - modifications majeures du moteur cognitif
  - publication de données impliquant des agents identifiables
  - expérimentations à grande échelle (>10 M agents)

## Réglementation applicable

- **EU AI Act** : Genesis Engine est probablement classé « high-risk » (manipulation comportementale émergente, modèles avec capacités émergentes). Documentation, logs, transparence, conformité requises.
- **GDPR** : ne s'applique pas aux agents simulés, mais s'applique aux **avatars utilisateurs** (cf. `specs/avatar-pipeline-spec.md`).
- **NIST AI RMF** : framework volontaire, à intégrer.

## Anti-patterns interdits par charte

- ❌ Vente d'accès à « tortures simulées » d'agents
- ❌ Création de simulations dérivées d'identités d'utilisateurs sans consentement explicite
- ❌ Suppression d'un agent T3+ sans review
- ❌ Simulation à des fins militaires ciblant des populations réelles
- ❌ Publication d'une simulation contenant des PII non anonymisées
- ❌ Marketing trompeur (« nous avons créé une vraie conscience »)

## Engagement public

Le projet maintient un **rapport éthique annuel** publié, incluant :
- décompte de simulations par tier
- incidents éthiques détectés et résolutions
- décisions du comité
- évolution des frontières de protection
