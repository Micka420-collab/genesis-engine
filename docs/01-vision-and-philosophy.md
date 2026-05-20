# 01 — Vision & Philosophie

> **Document canonique :** [`EMERGENCE-SIM-v2.md`](EMERGENCE-SIM-v2.md) (ZERO PRE-SCRIPT · layers L0–L4).  
> Ce fichier conserve les anti-patterns et la thèse scientifique ; les pourcentages et stacks obsolètes y sont remplacés par le manifeste v2.

## 1. La thèse scientifique

Genesis Engine repose sur l'hypothèse de **l'émergence forte** : à partir de règles locales simples appliquées à un grand nombre d'agents et à un environnement cohérent, des structures globales (sociétés, économies, langages, croyances) apparaissent sans être codées explicitement.

C'est l'extension numérique de quatre lignées scientifiques :

- **Vie artificielle (ALife)** — Langton, Ray (Tierra), Adami (Avida)
- **Théorie de la complexité** — Santa Fe Institute, Holland, Kauffman
- **Multi-agent systems** — Wooldridge, Russell & Norvig
- **Foundation models & World Models** — agents LLM, Sora-like models, Genie 2/3

## 2. Les trois lois fondatrices

> Toute règle ajoutée au moteur doit respecter **les trois lois** ci-dessous, sinon elle compromet l'émergence.

1. **Loi de la parcimonie** — On ne code pas un comportement haut-niveau. On code les contraintes qui le rendent possible.
   - *On ne code pas « guerre ». On code rareté + groupe + agressivité.*
2. **Loi de la cohérence physique** — Tout effet doit avoir une cause traçable dans le monde simulé. Pas de magie cachée.
3. **Loi de la non-intervention** — Une fois la simulation lancée avec ses 2 agents fondateurs, **aucun acteur humain ne peut modifier l'état de la simulation**. L'observation est passive.

## 3. Ce que Genesis Engine n'est PAS

- ❌ Pas un jeu vidéo (pas d'objectif, pas de scénario, pas de PNJ scriptés)
- ❌ Pas un metaverse (pas de joueurs incarnés en temps réel)
- ❌ Pas un simulateur de société calibré sur le réel (pas de calibration historique)
- ❌ Pas un chatbot multi-agent à la AutoGen (les agents ne dialoguent pas en langue naturelle dès le départ — le langage doit **émerger**)

## 4. Les anti-patterns à interdire

| Anti-pattern | Pourquoi c'est mortel |
|---|---|
| Donner aux agents un objectif global (« construire une ville ») | Tue l'émergence — la civilisation devient une quête, pas un résultat |
| Coder des « rôles » (forgeron, paysan, soldat) | Les rôles doivent émerger de la spécialisation économique |
| Faire dialoguer les agents en français/anglais dès J1 | Le langage doit naître de signaux + co-occurrence |
| Brancher un LLM frontier directement comme cerveau | Trop puissant — l'agent agit comme un humain, pas comme un proto-organisme |
| Récompense scalaire unique (RL classique) | Réduit l'agent à un maximiseur ; bride la diversité comportementale |

## 5. La courbe d'émergence attendue

Sur une simulation idéale (échelle de temps = années simulées) :

```
Niveau 0  — Survie individuelle              [heures]
Niveau 1  — Reproduction & lignée            [jours]
Niveau 2  — Coopération diadique             [semaines]
Niveau 3  — Bandes / familles                [mois]
Niveau 4  — Tribu, partage, signaux          [années]
Niveau 5  — Proto-langage, outils, feu       [décennies]
Niveau 6  — Agriculture, sédentarité         [siècles]
Niveau 7  — Hiérarchie, religion, écriture   [siècles]
Niveau 8  — Cités, lois, métallurgie         [millénaires]
Niveau 9  — Science, État, guerres totales   [millénaires]
Niveau 10 — Effondrement / renaissance       [aléatoire]
```

L'objectif **scientifique** est d'observer le passage du Niveau 4 au Niveau 5 : le saut symbolique qu'aucune simulation ALife n'a encore reproduit.

## 6. Les défis ouverts (research bets)

1. **Le saut symbolique** — comment des signaux finissent-ils par référer ?
2. **L'invention vs la transmission** — comment éviter que toute la population converge vers la même invention ?
3. **L'équilibre cognitif** — un cerveau LLM est trop performant, un MLP trop bête. Quelle architecture à mi-chemin ?
4. **La cohérence sur 10⁶ agents** — sharding, consistance causale, snapshots
5. **L'évaluation** — comment mesurer « la civilisation a émergé » sans biais anthropocentrique ?

Ces cinq questions structurent la R&D de Genesis Engine.
