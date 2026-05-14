# Cadre de mesure scientifique

> Mesurer une **émergence** sans biais anthropocentrique est l'un des défis les plus difficiles du projet. Ce document définit les métriques opérationnelles et leurs limites.

## Principes

1. **Pré-enregistrement** : toute métrique utilisée pour valider une hypothèse est déclarée AVANT le run.
2. **Métriques structurelles d'abord** (pas sémantiques) : on mesure des patterns observables, pas leur « sens ».
3. **Plusieurs métriques redondantes** : pas de single point of failure conceptuel.
4. **Comparaison à un null model** : tout pattern observé est comparé à une simulation contrôle (graine différente, mêmes paramètres).

## Métriques par niveau d'émergence

### Niveau 0–2 : survie, reproduction, coopération

| Métrique | Définition | Unité |
|---|---|---|
| Population | nombre d'agents vivants | count |
| Espérance de vie | mean(death_tick - birth_tick) sur cohorte | ticks |
| Taux reproductif net (R) | enfants viables / agent / vie | float |
| Cohésion locale | moyenne des coefficients de clustering du graphe d'interactions | [0,1] |

### Niveau 3–4 : groupes, tribus

| Métrique | Définition |
|---|---|
| Modularité du graphe social | Newman-Girvan modularity Q |
| Stabilité des groupes | persistance > 30 jours simulés |
| Asymétrie de pouvoir | distribution Gini des degrés sortants d'influence |
| Loyauté intra-groupe | ratio interactions intra/inter |

### Niveau 5 : proto-langage

| Métrique | Définition |
|---|---|
| **Mutual information signal–référent** | I(token, context) bits |
| Stabilité d'usage | autocorrélation du token sur fenêtre glissante |
| Compositional generalization | capacité de combiner 2 tokens pour un nouveau référent |
| Convergence inter-agents | proportion de paires qui partagent ≥80% du vocab |

**Seuil émergence** : I ≥ 0.5 bit pour ≥5 référents stables sur ≥3 générations dans une tribu.

### Niveau 6+ : technologie, sédentarité

| Métrique | Définition |
|---|---|
| Time-to-first-tool | tick auquel un objet manipulé est utilisé répétitivement par >1 agent |
| Time-to-first-fire | tick auquel un agent contrôle volontairement le feu |
| Sédentarité | rayon moyen de déplacement de l'agent < 100 m sur 30 jours |
| Diversité des structures | entropie de Shannon sur les types de constructions |

### Niveau 7+ : hiérarchie, écriture

| Métrique | Définition |
|---|---|
| Hiérarchie détectable | profondeur de l'arbre d'autorité ≥ 2 |
| Persistance de loi | un comportement « illégal » est sanctionné de manière récurrente |
| Écriture | symboles externes durables référant à des concepts mémorisés |

## Comparaison à null model

Pour chaque métrique :
- Lancer N=20 simulations de contrôle (mêmes paramètres, seeds différentes)
- Comparer la simulation observée au 95-percentile du null model
- Une émergence est validée si la métrique dépasse le 95p du null pendant ≥X ticks consécutifs

## Détection de fausses positives

- **Régression vers la moyenne** : un signal stable peut redevenir bruit. Métrique seulement valide sur fenêtre glissante.
- **Imitation triviale** : si un agent copie 100 % d'un autre sans variation, ce n'est pas du langage. Vérifier la variation.
- **Ressemblance fortuite** : deux signaux similaires peuvent ne pas avoir la même fonction. Vérifier la mutual information avec contexte.

## Validation externe

Avant publication :
- Pré-enregistrement OSF ouvert
- Replay independant par 2 équipes externes (mêmes seed, même build)
- Code audit indépendant
- Métriques calculées par un script séparé + cross-check

## Tableau de bord scientifique (live)

Le mode GOD expose un onglet « Science » qui calcule en temps réel les principales métriques et les compare au null model. Vert = émergence statistiquement significative, jaune = en cours, rouge = retour au null.
