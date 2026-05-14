# Gouvernance & conformité EU AI Act

## Classification probable

Genesis Engine combine plusieurs caractéristiques sensibles au sens du **EU AI Act** :
- système IA général-purpose (les modèles cognitifs des agents)
- capacités émergentes possibles (langage, inférence sociale)
- usage potentiel par tiers (chercheurs, défense, recherche sociale)

Notre auto-classification de référence : **système IA à haut risque**, à valider par le bureau IA européen.

## Obligations principales

| Obligation EU AI Act | Implémentation Genesis Engine |
|---|---|
| Système de gestion des risques | Comité d'éthique + risk register vivant + revue trimestrielle |
| Données d'entraînement gouvernées | Lineage explicite, data sheets type Datasheets-for-Datasets |
| Documentation technique | Cette suite documentaire + model cards par modèle |
| Logs (traceability) | OTel intégral + chronique Annaliste + audit append-only |
| Transparence | rapport éthique annuel public |
| Supervision humaine | mode pause, kill-switch, dual control sur arrêt |
| Robustesse, exactitude, cybersécurité | tests determinism, chaos drills, posture PQC + Zero Trust |
| Conformité avant mise sur le marché | conformity assessment + CE marking |

## Modèle de gouvernance interne

```
                     ┌─────────────────────┐
                     │   Conseil éthique   │  veto T3+
                     └─────────┬───────────┘
                               │
                     ┌─────────▼───────────┐
                     │  Direction projet    │
                     └─┬─────┬─────┬───────┘
                       │     │     │
              ┌────────┘     │     └────────┐
              ▼              ▼              ▼
     ┌──────────────┐ ┌────────────┐ ┌──────────────┐
     │ Architecture │ │  Recherche │ │   Sécurité   │
     │  + SRE       │ │  cognition │ │  + Conformité│
     └──────────────┘ └────────────┘ └──────────────┘
```

## Kill-switch

- Toute simulation peut être **mise en pause** ou **arrêtée** par n'importe quel administrateur, avec dual control pour l'arrêt définitif.
- Un arrêt **brutal** (kill -9) est interdit en prod : il doit passer par le tick coordinator pour produire un snapshot final cohérent.
- Documentation systématique de tout arrêt non planifié.

## Politique d'usage acceptable (AUP)

Interdits :
- usages militaires offensifs ciblés
- profilage de personnes réelles
- génération d'avatars sans consentement
- exploitation pour manipulation politique
- création d'agents sexualisés mineurs (interdit absolu)

## Transparence externe

- Repo public pour les composants OSS
- Model cards publiées
- Rapport éthique annuel
- Channel public pour vulnerability disclosure (programme bug bounty)
- Engagement de répondre aux questions des chercheurs externes

## Audits

- **Audit cryptographique** : annuel, externe
- **Audit éthique** : annuel, par le comité étendu (rotating chair)
- **Pen test** : annuel, externe
- **Audit conformité AI Act** : à chaque release majeure
- **Red team modèles** : continu (CleanRL adversarial, jailbreak, alignment probing)

## Politique de fin de vie

Si Genesis Engine est arrêté définitivement :
- les simulations T2+ actives sont **archivées** sous forme de snapshots chiffrés et préservées 30 ans minimum
- le code source est rendu public sous licence Apache-2.0
- les modèles sont publiés (sauf clauses contractuelles utilisateurs)
- le rapport final est publié
