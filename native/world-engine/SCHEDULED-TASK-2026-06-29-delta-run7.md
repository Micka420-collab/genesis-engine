# Tâche planifiée 2026-06-29 (J+19, run 7) — run PRODUCTIF (code livré + push)

> **Type :** exécution. **7ᵉ cycle du jour** (run1 C8, run2 C5, run3 C9, run4 refactor, run5 C6, run6 C10).
> **Référence :** [`SCHEDULED-TASK-2026-06-29-delta-run6.md`](SCHEDULED-TASK-2026-06-29-delta-run6.md) ·
> [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Sprint doc :** [`docs/sprints/2026-06-29_D12-WIRE-C15-salt-evaporation.md`](../../docs/sprints/2026-06-29_D12-WIRE-C15-salt-evaporation.md).
> **Contexte :** session utilisateur (« continue », boucle de travail jusqu'à 22h) + battement de cœur 9h→22h.

## 0. VEILLE + DÉCISION (report de C13)

- Candidat « métallurgie » **C13 copper_smelting** examiné puis **REPORTÉ** : il dépend de **C12
  forced_draught** (four soufflé, non câblé + structure) ET il **mute la géologie** (`geo.mine_at` →
  franchit la frontière **D10 gelée**). C'est une décision d'architecture (probable ADR), pas un
  append de routine.
- À la place : **C15 `salt_evaporation`** — 8ᵉ opérateur orthogonal (séchage solaire), non-feu,
  non-mutant, qui pose le **sel** (intrant de la future C16). **CVE : aucune.** Pas de brique externe.

## 1. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #12 — `ActionKind.RAKE` consomme C15 ; précurseur non-feu (« or blanc »).**

- Append d'une ligne au registre (`("saltpan", _seek_saltpan)`). Un agent curieux RÂTELLE une croûte
  de sel solaire récoltable → `inv_salt` ∝ rendement réel (×abondance). Aucun feu (le soleil travaille).
- **Nouveau champ `inv_salt`** (comme inv_lime/inv_limestone : dataclass + init + 2 listes, défensif).
- Mensonge #17 : même saumure → croûte en climat aride, **jamais** en climat humide.
- Garde-fous : D8 (`PY_TO_RUST` reste 15, compose C3×climat), D10 (pas de `mine_at`), D9 (non-feu),
  zéro-régression par construction.
- Vérif : `test_salt_evaporation_loop.py` **12/12** (montage ancré côte aride seed 0x5A17) +
  `test_arc_seek_registry.py` **6/6** (registre@11) ; smoke **p167 8/8** ; ruff clean ; CI p166 →
  **p167** ; non-régression p166 **8/8**.

## 2. RECOMMANDATIONS — R-J19(run7)-x

- **R (P1) — C16 `food_curing`** : conservation viande/poisson + **sel** (`inv_salt`) → une
  transformation NON-FEU à deux intrants qui *consomme* le sel qu'on vient de poser (boucle
  sel→salaison ; miroir non-thermique des chaînes argile→pot / calcaire→chaux). Append au registre.
- **R (P1) — C4 `combustible_outcrop`** : autre précurseur non-feu (combustible), simple gather.
- **R (P0 montant) — Cycle « décision/ADR » pour C13 + le four C11/C12** : C13 franchit D10
  (`geo.mine_at` dans la boucle agent) et dépend de C12 (structure). À instruire hors append (ADR
  « l'agent peut-il muter la géologie ? » + le four comme 1ʳᵉ **structure bâtie** de l'arc).

## 3. Verdict

| Question | Réponse J+19 run7 |
|---|---|
| Améliorations ? | **Oui — 12ᵉ capacité (D12 12/20) ; opérateur solaire non-feu ; sel posé pour C16.** |
| Rust ? | **Non** (ADR-0008). |
| Push ? | **Oui — `main`.** |
| Prochaine bouchée ? | **C16 food_curing** (sel→salaison, non-feu, deux intrants) ou **C4 combustible** ; C13/four = cycle ADR. |
