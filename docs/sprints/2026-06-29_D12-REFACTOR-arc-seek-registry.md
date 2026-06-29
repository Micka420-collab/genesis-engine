# Sprint 2026-06-29 (run 4) — D12 refactor : registre de capacités + budget de perception

> **Type :** `refactor(agentic/cognition)` — dette d'architecture, **pas un nouveau wire**.
> **Acte :** ferme la dette nommée dans [ADR-0009 §Conséquences](../../adr/0009-agent-consumer-loop.md)
> (« un futur **registre de capacités** + un **budget de perception** seront nécessaires au-delà de
> quelques branchements »). **Suite de :** wires #7–#9 du jour (C8, C5, C9 → arc 9/20).
> **Behavior-preserving** (ordre identique, aucune sortie de `decide()` changée).

## Pourquoi maintenant (pas un 10ᵉ wire)

Après 9 branchements, la branche curiosité de `cognition.decide()` était devenue une séquence
câblée de **9 lectures `_seek_*`** (`if d is not None: return d` × 9), qui grandissait d'un bloc à
chaque bouchée. C'est exactement la dette anticipée par ADR-0009. La discipline (et ma reco
R-J19(run3) P0-montant) imposait de **fermer cette dette avant la 10ᵉ bouchée**, sinon le chemin
chaud `decide()` continue de gonfler et chaque futur wire le ré-édite.

## Ce qui change

`decide()` n'appelle plus les seeks un par un. Elle délègue à **`_run_arc_seeks`**, qui itère un
**registre ordonné** `_ARC_SEEKS` et renvoie la première décision actionnable :

```python
_ARC_SEEKS = (
    ("frost_clast", _seek_frost_clast),   # GATHER     · C14
    ("toolstone",   _seek_toolstone),     # KNAP       · C2
    ("firesite",    _seek_firesite),      # IGNITE     · C7  (la VOÛTE)
    ("tempersite",  _seek_tempersite),    # TEMPER     · C8
    ("clay",        _seek_clay),          # DIG        · C5
    ("kiln",        _seek_kiln),          # FIRE_CLAY  · C9
    ("ochre",       _seek_ochre),         # GRIND      · C18
    ("canvas",      _seek_canvas),        # MARK       · C20
)
ARC_SEEK_BUDGET = 24   # max seeks évalués / tick (rail hot-loop ; no-op tant que < arc complet)
```

**Gains :**
- **Ajouter un wire = append d'une ligne** au registre. Le corps de `decide()` ne grandit plus.
- **Ordre load-bearing centralisé et lisible** (survie/outils → feu → transformations → symbole) au
  lieu d'être dispersé dans 9 blocs `if`.
- **Budget de perception** : `_run_arc_seeks` borne le nombre de seeks évalués par tick. Réglé à 24
  (≥ tout l'arc de 20 capacités) → **no-op aujourd'hui** (comportement identique), mais le *mécanisme*
  existe : c'est le bouton à baisser — avec des paliers de priorité survie-d'abord — si un profilage
  montre un jour que le coût par tick mord. (Cues mémoïsés + early-return sur cache absent → le coût
  actuel est une poignée de lookups.)

## Behavior-preserving — la preuve

L'ordre du registre est **exactement** celui de l'ancienne séquence ; `ARC_SEEK_BUDGET (24) ≥
len(_ARC_SEEKS) (8)` ⇒ aucun seek n'est jamais sauté pendant la campagne. Donc `decide()` renvoie
des décisions **bit-identiques**.

- `runtime/tests/test_arc_seek_registry.py` — **6 tests** (ordre canonique ; chaque entrée pointe le
  vrai `_seek_*` ; budget ≥ longueur ; `_run_arc_seeks` renvoie le **premier** non-None et
  court-circuite le reste ; renvoie None si tous cèdent ; le budget **borne** réellement le nombre
  d'évaluations — testé avec un budget réduit + seeks stubés).
- **Non-régression live (l'ordre préservé sur tout le span) :** p153 KNAP (2ᵉ entrée) **8/8**,
  p164 FIRE_CLAY (6ᵉ entrée, le plus profond — exige que le registre itère jusqu'à `kiln`) **8/8**,
  p160 MARK (dernière entrée) **8/8**. `ruff` clean.

## Garde-fous

| Garde-fou | Statut |
|---|---|
| **Comportement** | ✅ ordre identique + budget ≥ longueur ⇒ sorties `decide()` inchangées (3 smokes span + 6 tests) |
| **D8 / D10** | ✅ aucun tell, aucune mutation — pur refactor de dispatch |
| **Déterminisme** | ✅ itération ordonnée déterministe, 0 RNG |
| **Réversibilité** | ✅ le registre EST l'ancienne séquence sous forme de données ; trivialement réversible |

## Reste

Le câblage peut reprendre **trivialement** (append au registre) : C6 `limestone_outcrop` (récolte
non-feu), puis les transformations à deux intrants C10 `lime_burning` / C13 `copper_smelting`. La
dette ADR-0009 « registre + budget » est **fermée** ; la prochaine itération d'architecture
éventuelle serait des **paliers de priorité** (faire mordre le budget en cas de profilage défavorable)
et un éventuel **dispatch ordonné des wrappers** `decide`/`apply_decision` (dette D8-adjacente
restante, distincte).
