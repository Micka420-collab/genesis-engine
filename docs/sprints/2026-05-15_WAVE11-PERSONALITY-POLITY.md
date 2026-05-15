# SPRINT 2026-05-15 — Wave 11 personality-drives-politics

**Règle invariante respectée** : rien n'est scripté, les agents
découvrent par eux-mêmes. La politique émerge des **traits réels**
des agents, pas d'un script de gouvernance.

**Statut**: ✅ livré
**Cible**: faire émerger la gouvernance à partir des Big-Five
traits individuels — pas de table de règles "si chef alors X".

---

## Pourquoi ce sprint

Wave 9c `engine/polity.py` livrait :
* leader = highest *offspring_count + authored_inscriptions + age*
* tax = `TAX_RATE` constant pour tous
* redistribute = part proportionnelle au besoin pour tous

Tout cela ignorait les **traits de personnalité** déjà stockés
sur chaque agent (`ambition`, `extraversion`, `agreeableness`,
`conscientiousness`, …, sortis de `prf_rng` à la naissance et
hérités par crossover+mutation). La politique était identique
quel que soit qui dirigeait — pas crédible.

Cette Wave 11 wire les 4 traits clés dans 3 mécaniques :

| Mécanisme | Trait wired | Effet |
|---|---|---|
| Leader election | ambition + extraversion | +5·a + 2·e sur prestige score |
| Tax collection | agreeableness (per-agent) | compliance = 0.3 + 0.7·A |
| Redistribution share | conscientiousness (leader) | share_fraction = 0.3 + 0.7·C |
| Redistribution curve | conscientiousness (leader) | weight = need^(1/max(0.2,C)) |

---

## Détails par mécanisme

### 1. `_prestige_score` — leader election

```python
score += offspring_count + 0.5 * authored_inscriptions + age_bonus  # déjà là
score += 5.0 * ambition + 2.0 * extraversion                        # Wave 11
```

* `ambition` (0..1) pèse 5 pts max — c'est l'envie de pouvoir.
* `extraversion` (0..1) pèse 2 pts max — c'est la visibilité sociale.

Échelle calibrée pour qu'un agent très ambitieux dépasse un agent
ordinaire avec ~5 enfants, mais pas un patriarche avec 20+ enfants.
Charisme prend du poids quand la démographie n'a pas encore tranché.

### 2. `_tax` — per-agent compliance

```python
compliance = 0.3 + 0.7 * agreeableness   # [0.3, 1.0]
levy_kg = food_kg * TAX_RATE * compliance
```

* `agreeableness` = trait Big-Five de coopération prosociale.
* Un agent agreeable=1.0 paye `TAX_RATE` plein (5 %).
* Un agent agreeable=0.0 paye `0.3 × TAX_RATE` (1.5 %) — évasion.

**Vérifié** : 2.88× ratio (smoke p39 step 3) entre payeur agreeable
(0.95) et évadeur (0.05).

### 3. `_redistribute` — share_fraction + fairness exponent

```python
consc = sim.agents.conscientiousness[leader_row]
share_fraction = 0.30 + 0.70 * consc                # combien sort du trésor
fairness = max(0.20, consc)
weight = need ** (1.0 / fairness)                   # courbe de répartition
```

* `share_fraction` : un chef peu consciencieux thésaurise (~30 % sort) ;
  un chef très consciencieux vide les greniers (~100 % sort).
* `fairness` exponent : consc=1 → linéaire (`weight = need`) — tout
  le monde reçoit proportionnellement à son besoin.
  consc→0 → puissance forte — le plus affamé capte presque tout.

**Vérifié** :
* p39 step 4 : low-consc → 33.5 % distribué (target 20-45 %).
* p39 step 5 : high-consc → 96.5 % distribué (target > 80 %).
* p39 step 6 : ratio hungriest/least-hungry =
  **25218× (low-consc)** vs **3.7× (high-consc)** — courbe brutale
  vs courbe douce.

---

## Smoke `p39_personality_polity_smoke` **8/8 PASS**

```
[OK] step 1 — install_polity idempotent
[OK] step 2 — high-ambition agent wins leadership (row=3)
[OK] step 3 — agreeable pays 2.88× tax vs évadeur
[OK] step 4 — low-consc leader hoards (33.5 % distribué)
[OK] step 5 — high-consc leader empties (96.5 % distribué)
[OK] step 6 — low-consc curve concentre sur hungriest (25218×)
[OK] step 7 — ADR-0005 polity OK
[OK] step 8 — persistence preserves personality-driven tax
```

---

## Non-régression

`p32_polity_smoke` reste **8/8 PASS** après ajustement : les traits
sont pinés à 1.0 dans le setup pour exercer le **comportement nominal**
(TAX_RATE plein, redistribution linéaire) — la Wave 11 ne casse pas
l'API Wave 9c, elle l'enrichit.

Les autres Phase 4/5 smokes (p23, p25-p31, p33-p38) restent verts.

---

## Pré-requis Phase 5 — état

| Pré-req | État |
|---|---|
| 18 modules ADR-0005 | ✅ |
| P-NEW.22 + .24 | ✅ |
| Wave 9d cognition wiring | ✅ |
| Wave 10b/c/d (mine/smelt/build) | ✅ |
| Wave 10e discovery-driven building | ✅ |
| Wave 11 elite metrics (observer) | ✅ |
| **Wave 11 personality → polity** | ✅ |
| Wave 12 10K sim-yr long-run | ⏳ |

**9/10** pré-requis Phase 5 livrés. Il ne reste que la validation
long-run 10K sim-années.

---

## Fichiers touchés

```
runtime/engine/polity.py                                   (~40 LOC modifiées)
runtime/scripts/p32_polity_smoke.py                         (+5 LOC : pin traits)
runtime/scripts/p39_personality_polity_smoke.py             (nouveau, ~220 LOC)
docs/sprints/2026-05-15_WAVE11-PERSONALITY-POLITY.md        (ce fichier)
NEXT-SPRINT.md                                              (Wave 11 polity archivé)
```

---

## Lien avec la règle d'invariance

> *"rien n'est scripté, ils doivent découvrir par eux-mêmes"*

Wave 11 respecte la règle : **aucune règle "si chef alors X"**.
La gouvernance émerge des **valeurs réelles** des Big-Five sur
chaque agent — valeurs issues du prf_rng à la naissance,
héritées par méiose + mutation, soumises à la sélection
démographique. Une société qui sélectionne pour des hauts
agreeableness produit naturellement plus de coopération
fiscale. Une lignée qui sélectionne pour high-consc produit
des chefs redistributeurs. **C'est le pattern humain réel**,
pas un script.
