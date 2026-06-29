# Tâche planifiée 2026-06-29 (J+19, run 5) — run PRODUCTIF (code livré + push)

> **Type :** exécution. **5ᵉ cycle du jour** (run1 C8, run2 C5, run3 C9, run4 refactor registre).
> **Référence :** [`SCHEDULED-TASK-2026-06-29-delta-run4.md`](SCHEDULED-TASK-2026-06-29-delta-run4.md) ·
> [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Sprint doc :** [`docs/sprints/2026-06-29_D12-WIRE-C6-limestone-quarry.md`](../../docs/sprints/2026-06-29_D12-WIRE-C6-limestone-quarry.md).
> **Contexte :** session utilisateur (« continue », boucle de travail jusqu'à 22h) + battement de cœur
> horaire `genesis-arc-wiring-heartbeat` (cadence étendue **9h→22h**).

## 0. VEILLE

- La **chaux = plus ancien liant** (néolithique, antérieur à la métallurgie) ; le calcaire est le
  pendant bâtisseur de l'argile. **Valide** la pierre liante comme brique d'arc. Pas de pivot ;
  aucune brique externe (cargo-less). **CVE : aucune.**
- **COMBO_RETENU :** `C6 limestone_outcrop` → 10ᵉ tranche, précurseur non-feu, intrant du futur C10.

## 1. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #10 — `ActionKind.QUARRY` consomme C6 ; 1ʳᵉ bouchée via le registre `_ARC_SEEKS`.**

- Le refactor run 4 tient sa promesse : câbler C6 = **un append d'une ligne** au registre
  (`("limestone", _seek_limestone)` après la chaîne céramique), **sans toucher au corps de decide()**.
- Un agent curieux extrait (`QUARRY`) une berge carbonatée mortar-grade → `inv_limestone` ∝ `lime_grade`.
- **Nouveau champ `inv_limestone`** (comme inv_clay/inv_ceramic : dataclass + init + 2 listes de
  persistance, chargement défensif).
- Mensonge #15 : carbonate pur rend plus que commun ; berge karstique/dolomitique blanche → grade
  moindre (révélé pleinement à la cuisson).
- Garde-fous : D8 (`PY_TO_RUST` reste 15 ; limestone_pure catalogue-only), D10 (pas de `mine_at`),
  D9 (non-feu), zéro-régression par construction.
- Vérif : `test_limestone_quarry_loop.py` **11/11** + `test_arc_seek_registry.py` **6/6** (registre à
  9 entrées) ; smoke **p165 8/8** ; ruff clean ; CI p164 → **p165** ; non-régression p164 **8/8**.

## 2. RECOMMANDATIONS — R-J19(run5)-x

- **R (P1) — C10 `lime_burning`** : 2ᵉ transformation à deux ingrédients (calcaire `inv_limestone` +
  feu `has_made_fire` → chaux vive `inv_lime`/`inv_quicklime`), qui *consomme* le calcaire qu'on vient
  de rendre récoltable — boucle calcaire→feu→chaux (miroir de C9 argile→feu→pot). Append au registre.
- **R (P1) — ou C13 `copper_smelting`** (minerai + combustible + feu → `inv_metal`/`inv_copper`).
- **R (P2) — Paliers de priorité du budget** + dispatch ordonné des wrappers (dette ADR-0009
  résiduelle) — différés tant que le profil hot-loop ne mord pas.

## 3. Verdict

| Question | Réponse J+19 run5 |
|---|---|
| Améliorations ? | **Oui — 10ᵉ capacité (D12 10/20) ; 1ʳᵉ via le registre (1 ligne) ; intrant chaux posé.** |
| Rust ? | **Non** (ADR-0008). |
| Push ? | **Oui — `main`.** |
| Prochaine bouchée ? | **C10 lime_burning** (calcaire+feu→chaux) ou **C13 copper_smelting** ; append trivial au registre. |
