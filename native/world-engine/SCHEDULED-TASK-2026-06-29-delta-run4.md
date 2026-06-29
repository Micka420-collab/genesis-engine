# Tâche planifiée 2026-06-29 (J+19, run 4) — run PRODUCTIF (refactor livré + push)

> **Type :** exécution — **refactor d'architecture** (pas un nouveau wire). **4ᵉ cycle du jour.**
> **Référence :** [`SCHEDULED-TASK-2026-06-29-delta-run3.md`](SCHEDULED-TASK-2026-06-29-delta-run3.md) ·
> [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Sprint doc :** [`docs/sprints/2026-06-29_D12-REFACTOR-arc-seek-registry.md`](../../docs/sprints/2026-06-29_D12-REFACTOR-arc-seek-registry.md).
> **Contexte :** session utilisateur « continue ». Exécute R-J19(run3) P0-montant.

## 0. DÉCISION (discipline avant énième wire)

Après 9 branchements, `decide()` portait 9 lectures `_seek_*` câblées en dur — la dette nommée par
ADR-0009 (« un futur registre de capacités + un budget de perception seront nécessaires »). Plutôt
que d'empiler une 10ᵉ bouchée, ce run **ferme la dette** : registre ordonné + budget. **Pas de veille
techno** (refactor interne, pas de nouvelle brique ; CVE N/A).

## 1. CE QUI A ÉTÉ LIVRÉ (push `main`)

**`refactor(agentic/cognition)` — registre `_ARC_SEEKS` + `_run_arc_seeks` + `ARC_SEEK_BUDGET`.**

- `decide()` délègue à `_run_arc_seeks`, qui itère un **registre ordonné** des 8 seeks (ordre
  canonique survie/outils → feu → transformations → symbole) et renvoie la 1ʳᵉ décision actionnable.
- **Ajouter un wire = append d'une ligne** ; le corps de `decide()` ne grandit plus.
- **Budget de perception** (24, ≥ tout l'arc) : mécanisme de borne hot-loop, **no-op aujourd'hui**
  (comportement identique), bouton à baisser si profilage défavorable.
- **Behavior-preserving** : ordre identique + budget ≥ longueur ⇒ sorties `decide()` bit-identiques.
- Vérif : `test_arc_seek_registry.py` **6/6** (ordre, mapping, budget, first-non-None, court-circuit,
  borne) ; ruff clean ; **non-régression live** p153 (début) / p164 (profond) / p160 (fin) **8/8**.

## 2. RECOMMANDATIONS — R-J19(run4)-x

- **R (P1) — Reprendre le câblage, désormais trivial :** C6 `limestone_outcrop` (récolte non-feu,
  miroir de DIG → `inv_clay`/`inv_ceramic`), puis C10 `lime_burning` (calcaire + feu → chaux) et
  C13 `copper_smelting` (minerai + combustible + feu → `inv_metal`). Chaque ajout = 1 ligne au registre.
- **R (P2) — Paliers de priorité** : faire *mordre* `ARC_SEEK_BUDGET` (survie-d'abord) seulement si
  un profilage montre que le coût par tick devient sensible (différé, pas urgent).
- **R (P2) — Dispatch ordonné des wrappers** `decide`/`apply_decision` (dette D8-adjacente distincte,
  notée ADR-0009 §Conséquences) — non traitée ici.

## 3. Verdict

| Question | Réponse J+19 run4 |
|---|---|
| Améliorations ? | **Oui — dette ADR-0009 (registre + budget) FERMÉE ; câblage futur trivialisé.** |
| Nouveau wire ? | **Non — refactor délibéré** (discipline avant la 10ᵉ bouchée). |
| Comportement changé ? | **Non — bit-identique** (3 smokes span + 6 tests). |
| Push ? | **Oui — `main`.** |
| Prochaine bouchée ? | **C6 limestone** (append trivial au registre) puis C10/C13. |
