# Wave 38 — Combat Dynamics + Emergent Weapons

**Date :** 2026-05-18 (session 34w)
**Module livré :** `engine.combat_dynamics`
**Smoke :** `scripts/p69_combat_dynamics_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Wave 34 livre l'anatomie + blessures. Wave 35 livre les machines.
Wave 38 fait le pont : **les machines servent d'armes lors des combats
agent-vs-agent**, infligent des wounds via Wave 34 anatomy, et la mort
par hémorragie résulte naturellement.

Aucune liste "voici les armes du jeu". Une machine est une arme **par
classification de sa signature matérielle** :

```
WeaponKind émergent :
    UNARMED      : agent sans machine → coup de poing/coude (low dmg)
    CLUB         : dominant=stone OU dominant=wood            → BRUISE
    BLADE        : dominant=metal, 0.3-4 kg                   → CUT
    SPEAR        : metal + wood, 0.5-6 kg, 2-3 components     → CUT
    BOW          : dominant=wood, ≥3 components, 1-3 kg       → CUT distant
```

Une culture appelle son arme `malo`, une autre `kura` — si elles ont
la même signature matérielle, c'est la même classe d'arme.

---

## Architecture

### Classification

```python
_classify_machine_as_weapon(machine) → WeaponKind value

# Détection par combinaison matérielle d'abord (metal + wood = spear)
# puis dominant + masse pour les autres kinds.
```

### Résolution combat

```python
resolve_combat(sim, attacker_row, defender_row, *, skip_same_polity=True):
    weapon_a = best_weapon_for_agent(sim, attacker_row)
    weapon_d = best_weapon_for_agent(sim, defender_row)

    # Optional same-polity guard (uses engine.polity Wave 9c).
    if skip_same_polity and _same_polity(sim, a, d):
        return CombatExchange(same_polity_skipped=True)

    # Attacker hit roll.
    hit_p_a = 0.6 × accuracy_a × (1 + 0.5 × aggression_a)
    if rng_hit_a < hit_p_a:
        dmg_a = base_damage × (1 + 0.3 × strength_a) × jitter
        body_part = sample_part_by_weapon(weapon_a)
        anatomy.inflict_wound(d, body_part, weapon_a.wound_kind, dmg_a)

    # Defender counter (smaller).
    hit_p_d = 0.4 × accuracy_d × (1 + 0.5 × aggression_d)
    if rng_hit_d < hit_p_d:
        anatomy.inflict_wound(a, ...)
```

### Damage table calibrée brutalement

| Weapon | base_damage | accuracy | wound | parts visées |
|---|---:|---:|---|---|
| UNARMED | 0.06 | 0.7 | BRUISE | head, torso×2, hands |
| CLUB | 0.22 | 0.8 | BRUISE | head×2, torso×2, arms |
| BLADE | 0.30 | 0.9 | CUT | torso×3, arms, hands |
| SPEAR | 0.26 | 1.0 | CUT | head, torso×3 |
| BOW | 0.20 | 0.85 | CUT | torso×2, arms, legs (ranged spread) |

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API + 5 weapon kinds | OK |
| 2 | `unarmed_profile` sane (kind=0, dmg=0.06, acc=0.7) | OK |
| 3 | **Classification : stone+wood→CLUB(1), metal+wood→SPEAR(3)** | OK |
| 4 | No machines → UNARMED | OK |
| 5 | `resolve_combat` inflige wounds via anatomy (sev 0→0.774) | OK |
| 6 | **BLADE damage 27.897 vs UNARMED 4.684** → ratio 6× | OK |
| 7 | Déterminisme inter-runs (30 exchanges, hashes match) | OK |
| 8 | Install idempotent + stacks wrapper + uninstall clean | OK |
| 9 | **Combat bladé tue par hémorragie** : blood 0.828L < 1.5L seuil → `alive=False` | OK |

**Step 9 est la preuve d'intégration parfaite Wave 34 ↔ Wave 38** :
60 ticks de combat avec un blade + step_anatomy (bleeding) drainent
le sang du défenseur de 5.0 L initial à 0.828 L (sous le seuil
hypovolémique de 1.5 L), provoquant sa mort.

Aucune ligne de code ne dit "tue l'agent au tick X". La mort résulte
de la physique anatomique réelle.

---

## API publique

```python
from engine.combat_dynamics import (
    # Taxonomy
    WeaponKind, N_WEAPON_KINDS, WEAPON_KIND_NAMES,
    WeaponProfile, WEAPON_DAMAGE_TABLE,

    # Pure functions
    weapon_profile_from_machine,    # machine → WeaponProfile
    unarmed_profile,                # default fallback
    best_weapon_for_agent,          # sim, row → WeaponProfile

    # Combat
    resolve_combat,                 # sim, attacker, defender → CombatExchange
    CombatExchange,
    CombatState,

    # Sim integration
    install_combat_dynamics,        # idempotent + stacks apply_decision
    uninstall_combat_dynamics,
    combat_state,                   # diagnostic dict
)
```

### Usage type

```python
from engine.combat_dynamics import install_combat_dynamics, resolve_combat
from engine.anatomy import install_anatomy
from engine.machine_emergence import install_machine_emergence

install_anatomy(sim)
install_machine_emergence(sim)
install_combat_dynamics(sim)

# Quand un agent décide FIGHT (cognition) :
#   1. apply_decision wrapper intercepts ActionKind.FIGHT
#   2. resolve_combat(sim, attacker, target_row) runs
#   3. wounds inflicted via anatomy
#   4. bleeding ticks via step_anatomy → eventual death

# Ou appel manuel pour debug :
exchange = resolve_combat(sim, attacker_row=0, defender_row=1)
print(f"hit={exchange.attacker_hit} dmg={exchange.attacker_dealt_severity}")
```

---

## Limitations connues

- **Pas d'armure** : aucun système de protection corporelle. Les agents
  prennent les wounds sans mitigation. À ajouter Wave 38b (vêtements
  émergents depuis material_synthesis ?).
- **Pas de range BOW réel** : le BOW est classifié mais le combat
  exige proximité (target_row à 1m). À ajouter un attribut "ranged"
  qui permet target_row à distance > 0.
- **Same-polity guard naïf** : `_same_polity` cherche
  `polity_of_row` sur `_polity_state`. Si Wave 32 polity_emergence
  installe une autre interface, à adapter.
- **Pas de skill améliorable** : `strength` et `aggression` sont
  des Big-Five fixes (pas de progression par combat). À coupler avec
  `engine.cognitive_plasticity` Wave 12.
- **Pas de combat group** : 1v1 uniquement. Pour batailles N vs M,
  appeler resolve_combat en boucle (déterministe).
- **Pas de fuite réaliste** : FLEE existe comme ActionKind mais Wave 38
  ne propose pas de "réussite de fuite" qui éviterait le defender_counter.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| **Wave 39** | Disease propagation : wounds + low hygiene → infection (combat → maladie). |
| **Wave 40** | Genetics : strength/aggression héritables → guerriers émergent par lignées. |
| Polity diplomacy | Tracker des "casus belli" : si combat inter-polity > N → guerre formalisée. |
| Settlement defense | Buildings (Wave 10e) avec attribut `is_fort` réduit damage taken. |
| Animation timelapse | Visualiser les combats émergents au fil des frames Wave 37. |
