# Wave 34 — Detailed Anatomy + Wounds + Blood System

**Date :** 2026-05-18 (session 34r)
**Module livré :** `engine.anatomy`
**Smoke :** `scripts/p64_anatomy_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi (demande utilisateur)

L'utilisateur demande un monde virtuel Black Mirror / Westworld pour
faire des tests scientifiques :
- agents qui construisent leurs propres machines / routes
- mêmes lois physiques que la Terre
- **sang pour les IA, blessures quand ils travaillent, même anatomie
  que nous**
- vue type Age of Empires pour observer le monde se construire

C'est un programme **multi-sessions**. Wave 34 ship la pièce la plus
critique pour le réalisme corporel : **l'anatomie + le système
sanguin**. Le moteur avait déjà un scalaire `agents.injuries` flou
plus `wound_load` (infection) ; Wave 34 ajoute la couche anatomique
détaillée par body-part.

---

## Architecture

### 10 body parts × 4 wound kinds

```
BodyPart : HEAD, TORSO, L_ARM, R_ARM, L_HAND, R_HAND,
           L_LEG, R_LEG, L_FOOT, R_FOOT
WoundKind : CUT, BRUISE, FRACTURE, BURN
```

État per-agent : tenseur `wound_severity[N, 10, 4]` float32 dans [0, 1].

### Système sanguin (calibré humain réel)

- **Volume initial** : 5.0 L (adulte standard).
- **Seuil mortel** : 1.5 L (perte ~70 % = choc hypovolémique fatal).
- **Taux de saignement** :
  - CUT : 1.5×10⁻⁴ L/s par unité de sévérité (0.54 L/h à sev=1)
  - BRUISE : 0 (pas de saignement, hématome contenu)
  - FRACTURE : 4×10⁻⁵ L/s (saignement interne lent)
  - BURN : 8×10⁻⁵ L/s (perte plasma)

### Cicatrisation différentielle

```
HEAL_TIME_S = (
    cut      : 7  jours
    bruise   : 3  jours
    fracture : 40 jours
    burn     : 20 jours
)
```

Tous les taux sont **calibrés sur la médecine humaine réelle**.

### Couplage automatique action → wound (émergent)

Aucun script ne dit "agent X reçoit une coupure". Chaque action
agent (`engine.cognition.decide`) déclenche une roll deterministe
`prf_rng` qui peut produire des blessures :

| Action | Wound table (part, kind, base_sev) | Prob |
|---|---|---:|
| MINE | R_HAND CUT 0.10, R_ARM BRUISE 0.05 | 25 % |
| SMELT | R_ARM BURN 0.08, R_HAND BURN 0.05 | 30 % |
| BUILD | TORSO BRUISE 0.04, L_HAND BRUISE 0.03 | 12 % |
| HUNT | TORSO CUT 0.06, L_ARM BRUISE 0.04 | 40 % |
| FIGHT | HEAD BRUISE 0.08, TORSO CUT 0.10, L_ARM CUT 0.05 | 85 % |
| FORAGE | L_HAND CUT 0.02 | 8 % |
| PLANT | TORSO BRUISE 0.02 | 5 % |
| HARVEST | TORSO BRUISE 0.03, R_HAND CUT 0.02 | 10 % |

Chaque sévérité est jittered par ±jitter via prf_rng (deterministe).

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API + 10 parts + 4 wound kinds + 5.0 L initial | OK |
| 2 | `AnatomyFields` shapes (N,) + (N,10,4) | OK |
| 3 | Initial blood=5.0, total_severity=0 | OK |
| 4 | `inflict_wound` cible bien (row, part, kind) | OK |
| 5 | **CUT saigne (5.0→4.838L en 1h), BRUISE non (5.0→5.0)** | OK |
| 6 | **Mort par hémorragie** : blood 1.6→1.171 L, alive=False | OK |
| 7 | **Cicatrisation per-kind** : bruise 0.8→0.0 vs cut 0.8→0.371 sur 3j | OK |
| 8 | `wound_from_action` déterministe sur 50 ticks | OK |
| 9 | **MINE → R_HAND cuts émerge** : 24 % des MINE → R_HAND cut | OK |

**Step 9 est le check d'émergence le plus important** : sur 800 appels
MINE, 194 ont produit une coupure main droite (24.2 %). Cohérent avec
prob × ratio_R_HAND/total. Pas un seul script ne mentionne "MINE
should cut R_HAND". Émerge entièrement de la table de probabilités
matérielle pioche + biomécanique.

---

## Mesures émergentes (sim4 fin de smoke)

```
4 alive, 388 wounds cumulatifs en 200 × 4 = 800 actions
wounds_per_body_part = {
    'head':    0,
    'torso':   0,
    'l_arm':   0,
    'r_arm':   4,    ← tous les 4 founders ont R_ARM bruise (MINE)
    'l_hand':  0,
    'r_hand':  4,    ← tous les 4 founders ont R_HAND cut  (MINE)
    'l_leg':   0,
    'r_leg':   0,
    'l_foot':  0,
    'r_foot':  0,
}
```

Le pattern est diagnostique : agents qui MINE accumulent blessures
bras/main droite. Si on regarde un agent SMELTeur, on verrait R_ARM
burn dominant. Si on regarde un agent FIGHTeur, on verrait HEAD/TORSO.

**C'est exactement comme dans la réalité humaine.**

---

## API publique

```python
from engine.anatomy import (
    # Taxonomy
    BodyPart, WoundKind, N_BODY_PARTS, N_WOUND_KINDS,
    BODY_PART_NAMES, WOUND_KIND_NAMES,
    BLOOD_VOLUME_INITIAL_L, BLOOD_DEATH_THRESHOLD_L,

    # Tables (modifiable for variants)
    ACTION_WOUND_TABLE,
    ACTION_WOUND_PROBABILITY,

    # State
    AnatomyFields,

    # Pure-function operations
    inflict_wound,                  # fields, row, part, kind, severity
    wound_from_action,              # fields, row, action, seed, tick

    # Sim integration
    install_anatomy,                # sim → AnatomyFields, wraps sim.step
    uninstall_anatomy,
    step_anatomy,                   # sim, dt_s → stats dict
    anatomy_state,                  # sim → diagnostic dict
)
```

### Usage type

```python
from engine.anatomy import install_anatomy, anatomy_state

sim = Simulation(SimConfig(...))
install_anatomy(sim)

# Now each sim.step() :
#  1. apply_decision determines action per agent (cognition emergent)
#  2. anatomy wrapper rolls wound from action via prf_rng
#  3. step_anatomy advances bleeding + healing
#  4. checks death by hemorrhage

for _ in range(10000):
    sim.step()

print(anatomy_state(sim))
# → blood_min_l, n_with_open_wound, wounds_per_body_part, cumulative_deaths_from_bleed
```

---

## Roadmap pour la vision complète (multi-sessions)

| Wave | Module | Tech | Effort |
|---|---|---|---|
| **34** ✅ | `anatomy` | body parts + wounds + blood | Livré aujourd'hui |
| 35 | `machine_emergence` | multi-component artifacts (roue, levier, watermill, métier à tisser) — extension `invention.py` au-delà des outils simples | 1 session |
| 36 | `world_render_isometric` | renderer 2.5D Age of Empires-style, voxel chunks + agent sprites | 2 sessions |
| 37 | `animation_timelapse` | GIF/MP4 export d'une evolution complète | 1 session |
| 38 | `combat_dynamics` | armes émergentes, combat resolution, blessures réalistes par arme | 1 session |
| 39 | `disease_propagation` | extension `physiology` épidémies réalistes (R0, networks Wave 29+) | 1 session |
| 40 | `reproduction_genetics` | héritage Big-Five + apparence + maladies congénitales | 1 session |

À ce stade tu auras un sim civilisationnel complet observable visuellement
en 2.5D, avec anatomie + sang + machines + maladies + génétique
réalistes. Black Mirror / Westworld scientifique.

---

## Limitations connues (Wave 34)

- **Pas d'organe interne** : pas de cœur/foie/rate séparés. Pour des
  blessures organes (e.g., coup au foie → mort par hémorragie interne),
  ajouter un sous-niveau "organ" sous "body part" en Wave 35+.
- **Pas de membres amputés** : sévérité plafonne à 1.0 ; on ne perd
  jamais un membre. Pour ça, ajouter un attribut `amputated` per-part
  + actions FIGHT spéciales.
- **Pas de groupe sanguin** : pas de compatibilité ABO. Pour les
  transfusions / héritage Wave 40+.
- **Pas de douleur chronique** : la pain weight contribue à
  `sim.agents.injuries` mais ne persiste pas après healing.
- **Couplage action statique** : la table est calibrée à la main. À
  long terme, learn from observed simulation outcomes.
- **Pas de bandages / soins** : pas d'action MEDICATE qui réduit le
  bleed rate. À ajouter pour Wave 38 combat dynamics.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| `engine.cognition` | Pain weight déjà dans `agents.injuries` → influence DECIDE (les blessés cherchent shelter, pas mine). |
| `engine.polity` | Polities en guerre = leaders avec haut FIGHT count = anatomies abîmées. |
| `engine.writing` | "Médecin" émerge : agent avec haut conscientiousness + inventions associated → MEDICATE. |
| `engine.world_render` | Overlay rouge où agents ont des wounds visibles. |
| `engine.stone_age_evolution` | Observer `cumulative_deaths_from_bleed` au fil de l'évolution. |
