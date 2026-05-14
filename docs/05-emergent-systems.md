# 05 — Systèmes émergents

> **Règle d'or** : **rien** dans cette section n'est *codé*. Tout y est *rendu possible* par les couches inférieures.

## 1. Économie

### Ce qui est codé (briques)

- Inventaire individuel (slots limités par force)
- Notion de propriété (un objet appartient à l'agent qui l'a fabriqué/transporté en dernier)
- Action `donner(autre_agent, objet)` et `prendre(objet_au_sol)`
- Mémoire des transactions

### Ce qui émerge

- **Troc** dès que deux agents ont des inventaires complémentaires + relation positive
- **Spécialisation** dès que la productivité d'un agent dans une activité × temps > productivité moyenne dans une autre
- **Monnaie** : objet rare, divisible, durable, désiré → coquillages, métaux précieux. Apparaît seulement après plusieurs siècles.
- **Crédit / dette** dès que la mémoire relationnelle est assez fine pour tracker
- **Marché** dès que >5 agents convergent géographiquement avec biens divers

## 2. Politique & gouvernance

### Ce qui est codé

- Notion de **groupe** (ensemble d'agents avec interactions répétées et identité commune)
- Charisme (trait de personnalité influençant la persuasion)
- Mémoire collective via transmission d'événements (signal-récit)
- Coercition (un agent fort peut contraindre un agent faible)

### Ce qui émerge

- **Leadership** par charisme/force/expertise
- **Tribu** dès que la taille du groupe dépasse ~15 (limite de Dunbar mini)
- **Hiérarchie** dès que la spécialisation crée des dépendances
- **Loi tacite** par convention (Schelling points)
- **Loi explicite** dès l'apparition d'une mémoire externe (gravure, écriture)
- **Régimes** : observables a posteriori — démocratie / monarchie / oligarchie / dictature ne sont **jamais** des paramètres mais des **patterns détectés** par l'observer.

## 3. Culture

### Briques codées

- **Imitation** : un agent peut copier le comportement observé d'un autre (avec succès stochastique)
- **Communication par signal** : émission de tokens audio (initialement aléatoires)
- **Mémoire transmise** : un parent partage une fraction de sa mémoire sémantique avec son enfant pendant la phase d'éducation

### Émergences attendues

- **Proto-langage** : un signal devient stable parce qu'il améliore la coordination (chasse, alerte). Co-occurrence référent/signal sur plusieurs générations → conventionalisation.
- **Variations dialectales** par dérive entre groupes isolés
- **Art** : production d'objets sans utilité immédiate quand les besoins primaires sont satisfaits
- **Mythes** : récits qui survivent malgré leur fausseté empirique parce qu'ils renforcent la cohésion
- **Tradition** : comportement transmis sur 3+ générations

## 4. Religion / philosophie

### Émergence

- L'agent observe des **régularités inexplicables** (saisons, mort, foudre)
- Son moteur causal R2 cherche des causes
- Quand la cause empirique est inaccessible, il **invente** un agent invisible (animisme)
- Le récit se propage par imitation
- Si plusieurs agents partagent ce récit → **culte**
- Si un agent tire un statut social du culte → **prêtre**
- Si plusieurs cultes coexistent → tensions, syncrétisme, ou guerre de religion

> **Note R&D** : c'est l'un des phénomènes les plus instables. Calibrer la probabilité d'invention d'agents invisibles est une question ouverte.

## 5. Conflits

### Niveaux

| Niveau | Description | Acteurs | Émergence |
|---|---|---|---|
| Duel | 2 individus | famille, rivaux | dès J1 |
| Vendetta | clans | familles | après plusieurs générations |
| Razzia | groupes voisins | tribus | sédentarité + ressources |
| Guerre tribale | tribus | tribus organisées | leadership stable |
| Guerre étatique | États | États | apparition cités |
| Guerre totale | civilisations | civilisations | technologie + idéologie |

### Briques codées

- Action `attaquer(cible)`
- Coalition (alliance temporaire à coût bas)
- Mémoire des torts subis (rancune)
- Logique du **dilemme du prisonnier itéré** (la coopération est avantageuse mais la trahison ponctuelle paie)

## 6. Science & technologie

### Mécanique

- **Découverte** = un agent observe une corrélation **non encore mémorisée** entre une action et un effet désiré.
- Son cerveau R2 enregistre cette corrélation comme **règle apprise**.
- L'invention se transmet par imitation/enseignement.
- L'**arbre technologique** est implicite : on ne le code pas, mais on peut le **reconstruire a posteriori** depuis les inventions enregistrées.

### Pré-requis émergents

| Technologie | Requiert |
|---|---|
| Feu | foudre + bois sec + curiosité élevée |
| Outil de pierre | observation impact + intentionnalité |
| Lance | outil + chasse coopérative |
| Agriculture | observation cycle saisonnier + sédentarité |
| Métallurgie | feu intense + minerai trouvé + curiosité élevée |
| Écriture | mémoire externalisée + symboles stables |
| Mathématiques | comptage de biens (commerce) + abstraction |
| Informatique | écriture + mathématiques + métallurgie + énergie |

## 7. Évolution darwinienne

### Génotype d'un agent

```
genome:
  morpho:
    taille (gene 0–255)
    force (gene 0–255)
    endurance, vitesse, métabolisme, longévité
  cognition:
    QI (capacité MLP)
    mémoire (taille vector store)
    curiosité, créativité, prudence (poids OCC)
    plasticité (taux d'apprentissage)
  social:
    grégarité, empathie, agressivité
  reproductif:
    age_puberté, fertilité
```

### Mécanique

- **Reproduction sexuée** : crossover gène-à-gène + mutation Gaussienne (σ paramétrable)
- **Sélection naturelle** = différentiel de fitness (= nombre de descendants viables)
- **Sélection sexuelle** = préférences apprises culturellement (peut diverger de la fitness pure)
- **Drift génétique** : non négligeable sur petites populations

## 8. Renaissance après extinction

Une civilisation peut s'effondrer (catastrophe, guerre, épuisement ressources). Les survivants éparpillés conservent une **mémoire fragmentée**. Une nouvelle civilisation peut émerger en réutilisant des artefacts de la précédente (ruines, restes d'écriture).

Cela permet d'observer des **dark ages** et des renaissances culturelles **réelles, non scriptées**.
