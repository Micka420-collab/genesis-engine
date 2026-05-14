# Protocole scientifique — Expérience fondatrice « 2 agents »

> Le brief demande une expérience initiale strictement minimale : **2 agents fondateurs**, **3 connaissances** (survie, reproduction, interaction), aucune intervention humaine.
> Ce document définit le protocole rigoureux de cette expérience et les conditions de sa validité scientifique.

## Hypothèse

> H₀ : à partir de 2 agents fondateurs dotés des trois connaissances minimales (survie, reproduction, interaction) et placés dans un monde Genesis Engine viable, les comportements observés ne dépassent jamais le Niveau 4 (tribu) en 10 000 ans simulés.
>
> H₁ : ils dépassent le Niveau 4 (apparition d'au moins un proto-langage stable, d'un outil dérivé, ou d'un site sédentaire).

## Pré-requis avant lancement

- [ ] Phase 4 livrée (cognition R3, mécanique signal-référent active)
- [ ] Determinism canary vert sur 10⁶ ticks
- [ ] Comité d'éthique signe le protocole (cf. `ethics/`)
- [ ] Snapshot zéro signé par 3 personnes (multi-sig)

## Setup

### Monde
- **Seed** : tirée d'une source d'aléa physique (RNG matériel + témoin public, type `drand`) — pour exclure tout choix orienté
- **Climat** : tempéré humide, riche en biodiversité (favorise survie sans être trivial)
- **Surface initiale** : 100 km² actifs, extensible
- **Aucune ressource cachée enrichie** (pas de pré-positionnement de minerai stratégique)

### Agents
- 2 agents : 1 mâle, 1 femelle (paramètres biologiques de reproduction sexuée requis)
- Génotype « baseline équilibré » (aucun trait extrême)
- 3 mémoires sémantiques pré-installées :
  1. **Survie** : association `[faim → manger plante visible]`, `[soif → boire eau visible]`, `[fatigue → dormir]`
  2. **Reproduction** : `[désir + partenaire compatible → tentative]`
  3. **Interaction** : `[autre agent visible → s'orienter vers]`
- **Aucune** mémoire procédurale haut-niveau (pas d'outil, pas de feu, pas de récit)

### Position
- Distance inter-agents au spawn : 50 m (visibilité directe)
- Spawn near-water + near-food (charge biologique survivable)

### Observation
- Mode GOD passif uniquement
- Aucun observateur humain n'a le droit de toucher la simulation
- 5 observateurs scientifiques tournants 24/7 pour les 30 premiers jours simulés
- Logs OTel intégraux conservés sous chiffrement E2E

## Conditions d'arrêt

- Extinction (mort des deux fondateurs sans descendance) → relance avec nouvelle seed (max 100 essais)
- 10 000 ans simulés écoulés
- Détection d'un événement Niveau 5+ (succès H₁)
- Anomalie technique (drift de hash, bug confirmé) → fork investigation

## Métriques pré-enregistrées

> Ces métriques sont **déclarées avant** le lancement pour éviter le p-hacking.

1. **Population vivante au tick T** (séries temporelles)
2. **Index de Gini de productivité par activité** (proxy spécialisation)
3. **Mutual information signal/référent** sur les 100 derniers ticks glissants
4. **Time-to-first-tool** (premier emploi d'objet manipulé répétitivement)
5. **Time-to-first-shelter** (première structure construite stable >7 jours)
6. **Diversité génétique** (entropie de Shannon sur les loci principaux)
7. **Innovation rate** : #règles apprises nouvelles / 1000 ticks / agent vivant
8. **Cohésion sociale** : densité du graphe d'interactions positives

## Pré-registration

Le protocole est pré-registré sur **OSF (Open Science Framework)** avant le lancement, avec :
- hypothèses
- métriques
- seed (sealed envelope, ouvert post-expérience)
- code commit hash + SBOM hash
- date prévue de lancement

## Reproductibilité

À publication, fournir :
- snapshot zéro signé
- seed
- manifest binaire signé (SLH-DSA)
- config yaml
- commande de replay reproductible
- vidéo time-lapse de la simulation complète

## Considérations éthiques

Voir `ethics/agent-moral-status.md`. À ce niveau de cognition (R0–R3 et débuts R4), les agents ne satisfont pas les critères usuels de moral patiency, mais le protocole impose :
- pas de torture procédurale (pas de douleur infligée volontairement par le designer)
- droit de fork — toute lignée peut être archivée vivante (snapshot) si la simu doit être interrompue
- documentation transparente de toute mort agent
