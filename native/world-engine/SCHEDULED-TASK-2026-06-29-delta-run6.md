# Tâche planifiée 2026-06-29 (J+19, run 6) — run PRODUCTIF (code livré + push)

> **Type :** exécution. **6ᵉ cycle du jour** (run1 C8, run2 C5, run3 C9, run4 refactor, run5 C6).
> **Référence :** [`SCHEDULED-TASK-2026-06-29-delta-run5.md`](SCHEDULED-TASK-2026-06-29-delta-run5.md) ·
> [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Sprint doc :** [`docs/sprints/2026-06-29_D12-WIRE-C10-lime-burning.md`](../../docs/sprints/2026-06-29_D12-WIRE-C10-lime-burning.md).
> **Contexte :** session utilisateur (« continue », boucle jusqu'à 22h) + battement de cœur 9h→22h.

## 0. VEILLE

- La chaux = plus ancienne industrie chimique (néolithique, antérieure à la métallurgie) ; C10 est
  le **pendant exact de C9** (argile→pot :: calcaire→chaux). **Valide**, pas de pivot. Aucune brique
  externe (cargo-less). **CVE : aucune.**
- **COMBO_RETENU :** `C10 lime_burning` → 11ᵉ tranche, 2ᵉ transformation à deux intrants, consomme le
  calcaire que C6 (run5) rend récoltable.

## 1. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #11 — `ActionKind.CALCINE` consomme C10 ; 2ᵉ transformation à deux ingrédients.**

- Append d'une ligne au registre (`("limekiln", _seek_limekiln)`). Un agent qui sait faire le feu
  ET porte du calcaire (`inv_limestone`) le CALCINE → chaux vive (`inv_lime`) ∝ `lime_yield`.
- **2ᵉ flux matière inter-capacités** : consomme `inv_limestone`, émet `inv_lime` (après argile→céramique).
- **Nouveau champ `inv_lime`** (comme inv_limestone/inv_ceramic : dataclass + init + 2 listes, défensif).
- Mensonge #16 (inversion réfractaire, identique à C9) : feu ouvert → chaux aérienne seulement
  (`mortar_ready` toujours False, mortier dur exige un four) ; sous-cuit → calcaire perdu, 0 chaux.
- Garde-fous : D8 (`PY_TO_RUST` reste 15, compose C6×C7), D10 (pas de `mine_at`), double gate
  (feu + calcaire), zéro-régression par construction.
- Vérif : `test_lime_burning_loop.py` **13/13** + `test_arc_seek_registry.py` **6/6** (registre@10) ;
  smoke **p166 8/8** ; ruff clean ; CI p165 → **p166** ; non-régression p165 **8/8**.

## 2. RECOMMANDATIONS — R-J19(run6)-x

- **R (P1) — C13 `copper_smelting`** : la métallurgie (minerai + combustible + feu → `inv_metal`/`inv_copper`),
  qui introduirait l'usage du **combustible C4** (encore non branché). Ou brancher **C4
  `combustible_outcrop`** d'abord (récolte de combustible, précurseur non-feu).
- **R (P1) — Le FOUR (C11 `kiln_draft` / C12 `forced_draught`)** lèverait l'inversion réfractaire des
  DEUX chaînes (vitrification céramique + mortier hard-burnt) — un saut qualitatif (débloquerait la
  qualité « kiln-fired » déjà ground-truthée dans C9 et C10).
- **R (P2) — Paliers de priorité du budget** + dispatch ordonné des wrappers (dette résiduelle), différés.

## 3. Verdict

| Question | Réponse J+19 run6 |
|---|---|
| Améliorations ? | **Oui — 11ᵉ capacité (D12 11/20) ; 2ᵉ chaîne pyrotechnologique vécue (calcaire→feu→chaux).** |
| Rust ? | **Non** (ADR-0008). |
| Push ? | **Oui — `main`.** |
| Prochaine bouchée ? | **C13 copper_smelting** (métallurgie, intro combustible C4) ou **C11/C12 le four** (lève l'inversion réfractaire) ; append trivial au registre. |
