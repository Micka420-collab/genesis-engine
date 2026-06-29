# Tâche planifiée 2026-06-29 (J+19, run 9) — run PRODUCTIF (code livré + push)

> **Type :** exécution. **9ᵉ cycle du jour** (C8, C5, C9, refactor, C6, C10, C15, C4, [C11]).
> **Référence :** [`SCHEDULED-TASK-2026-06-29-delta-run8.md`](SCHEDULED-TASK-2026-06-29-delta-run8.md) ·
> [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Sprint doc :** [`docs/sprints/2026-06-29_D12-WIRE-C11-kiln-draft.md`](../../docs/sprints/2026-06-29_D12-WIRE-C11-kiln-draft.md).
> **Contexte :** session utilisateur (« continue », boucle jusqu'à 22h) + battement de cœur 9h→22h.

## 0. DÉCISION

- Le delta run8 classait le four en « cycle ADR ». Lecture faite : **C11 `kiln_draft` est une
  affordance in-situ NON-MUTANTE** (compose C5×C7, pas de `geo.mine_at`, pas de structure persistante)
  → **wireable proprement** comme un « build ». **Reste ADR :** seulement C13/C17 (métallurgie, qui
  franchissent D10 via `geo.mine_at`). Pas de brique externe (cargo-less). **CVE : aucune.**

## 1. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #14 — `ActionKind.RAISE_KILN` consomme C11 ; la 1ʳᵉ FABRICATION D'APPAREILLAGE de l'arc.**

- Append d'une ligne au registre (`("kilnbuild", _seek_kilnbuild)`). Un agent qui sait faire le feu
  ET porte de l'argile chemise son foyer → four à tirage `kiln_peak_c` (~1070 °C vs 800 °C feu nu).
- **Auto-limité** (`has_built_kiln` : une construction = la découverte). Consomme `inv_clay` (la
  chemise) ; **aucun nouveau champ d'inventaire**.
- Mensonge #19 (inversion-de-l'inversion) : parois communes fluent (pic modeste) ; la kaolinite
  réfractaire qui sous-cuit comme pot fait les meilleures parois. Réfr 1070 > commun 1000 > feu nu 800.
- Garde-fous : D8 (`PY_TO_RUST` reste 15), D10 (pas de `mine_at` — appareillage non-mutant), double
  gate (feu + argile), zéro-régression.
- Vérif : `test_kiln_draft_loop.py` **13/13** + `test_arc_seek_registry.py` **6/6** (registre@13) ;
  smoke **p169 8/8** ; ruff clean ; CI p168 → **p169** ; non-régression p168 **8/8**.

## 2. RECOMMANDATIONS — R-J19(run9)-x

- **R (P0 montant) — Coupler le four à C9/C10 (saut qualitatif, pas un nouveau wire) :** faire que
  `FIRE_CLAY` (C9) et `CALCINE` (C10) détectent un four de l'agent (`has_built_kiln` / four à
  proximité) et utilisent `kiln_peak_c` au lieu de la température du feu nu → **vitrifie** la poterie
  (C9 racheté) et **hard-burn** le mortier (C10 racheté). C'est la promesse différée des mensonges
  #14/#16, enfin tenue.
- **R (P1) — C12 `forced_draught`** (tirage soufflé → température cuivre) : prochain palier de four.
- **R (P0, cycle ADR) — Métallurgie C13/C17** : franchissent **D10** (`geo.mine_at` dans la boucle
  agent). ADR « l'agent peut-il muter la géologie ? » avant tout câblage.

## 3. Verdict

| Question | Réponse J+19 run9 |
|---|---|
| Améliorations ? | **Oui — 14ᵉ capacité (D12 14/20) ; 1ʳᵉ structure/appareillage bâti(e) par l'agent.** |
| Rust ? | **Non** (ADR-0008). |
| Push ? | **Oui — `main`.** |
| Prochaine bouchée ? | **Coupler le four à C9/C10** (vitrification/mortier — saut qualitatif) ; puis C12 ; métallurgie = cycle ADR D10. |
