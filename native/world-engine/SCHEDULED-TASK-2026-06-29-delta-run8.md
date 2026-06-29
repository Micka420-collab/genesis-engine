# Tâche planifiée 2026-06-29 (J+19, run 8) — run PRODUCTIF (code livré + push)

> **Type :** exécution. **8ᵉ cycle du jour** (C8, C5, C9, refactor, C6, C10, C15, [C4]).
> **Référence :** [`SCHEDULED-TASK-2026-06-29-delta-run7.md`](SCHEDULED-TASK-2026-06-29-delta-run7.md) ·
> [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Sprint doc :** [`docs/sprints/2026-06-29_D12-WIRE-C4-combustible-glean.md`](../../docs/sprints/2026-06-29_D12-WIRE-C4-combustible-glean.md).
> **Contexte :** session utilisateur (« continue », boucle jusqu'à 22h) + battement de cœur 9h→22h.

## 0. VEILLE + DÉCISION (report de C16)

- Candidat « salaison » **C16 food_curing** examiné puis **REPORTÉ** : oracle `shelf_life_days` dont
  la dose de sel vient de la **proximité** d'un marais (pas du sel porté), **sans** modèle de
  pourriture ni champ `inv_cured` → décision de design, pas un append.
- À la place : **C4 `combustible_outcrop`** — gather non-feu propre (miroir de QUARRY), qui pose le
  **combustible** (charbon = seul grade fusion, futur catalyseur métallurgie). **CVE : aucune.**

## 1. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #13 — `ActionKind.GLEAN` consomme C4 ; précurseur non-feu (le fuel qui alimentera feux/fours).**

- Append d'une ligne au registre (`("fuel", _seek_fuel)`). Un agent curieux GLANE une exposition de
  combustible brûlable → `inv_fuel` ∝ pouvoir calorifique.
- **Nouveau champ `inv_fuel`** (≠ `inv_wood` = bois de construction ; dataclass + init + 2 listes, défensif).
- Mensonge #18 : charbon/schiste secs → combustible riche ; tourbière humide → fraction seulement.
- Garde-fous : D8 (`PY_TO_RUST` reste 15), D10 (pas de `mine_at`), D9 (non-feu), zéro-régression.
- Vérif : `test_combustible_glean_loop.py` **11/11** + `test_arc_seek_registry.py` **6/6** (registre@12) ;
  smoke **p168 8/8** ; ruff clean ; CI p167 → **p168** ; non-régression p166 **8/8**.

## 2. RECOMMANDATIONS — R-J19(run8)-x

- **R (P1) — Le FOUR (C11 `kiln_draft` / C12 `forced_draught`) en cycle ADR** : 1ʳᵉ **structure
  bâtie** de l'arc ; lèverait l'inversion réfractaire de C9 (vitrification) ET C10 (mortier hard-burnt),
  et débloquerait la fusion. Combustible (C4) désormais posé comme intrant.
- **R (P1) — C13 cuivre / C17 fer (métallurgie) en cycle ADR** : franchissent **D10** (`geo.mine_at`
  dans la boucle agent) + dépendent du four (C12). ADR « l'agent peut-il muter la géologie ? ».
- **R (P2) — C16 salaison / C1 prospection** : appends restants nécessitant une petite décision
  (modèle de conservation / champ `inv_cured` pour C16 ; verbe « prospect » pour C1).

## 3. Verdict

| Question | Réponse J+19 run8 |
|---|---|
| Améliorations ? | **Oui — 13ᵉ capacité (D12 13/20) ; combustible posé (intrant du four / de la métallurgie).** |
| Rust ? | **Non** (ADR-0008). |
| Push ? | **Oui — `main`.** |
| Prochaine bouchée ? | Cycle **ADR** pour le four (C11/C12) + la métallurgie (C13/C17, mutation D10) ; ou appends C16/C1. |
