# Tâche planifiée 2026-06-29 (J+19, run 2) — run PRODUCTIF (code livré + push)

> **Type :** exécution (code + tests + smoke + docs + push). **2ᵉ cycle du jour** (run 1 = C8 TEMPER).
> **Référence :** [`SCHEDULED-TASK-2026-06-29-delta.md`](SCHEDULED-TASK-2026-06-29-delta.md) (run 1) ·
> [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Sprint doc :** [`docs/sprints/2026-06-29_D12-WIRE-C5-clay-digging.md`](../../docs/sprints/2026-06-29_D12-WIRE-C5-clay-digging.md).
> **Contexte :** session utilisateur « continue » + battement de cœur horaire `genesis-arc-wiring-heartbeat`.

## 0. VEILLE (avant code)

- *Foraging multi-agents à retour énergétique* + *Semantic Information in Resource Gathering Agents*
  + stratégies préhistoriques de collecte de matières → **valident** la collecte émergente comme
  brique de boucle agent. Pas de pivot ; aucune brique externe (cargo-less). **CVE : aucune.**
- **COMBO_RETENU :** `utility-based action selection` × `C5 clay_outcrop` → 8ᵉ tranche, **précurseur
  NON-FEU** (rétablit l'alternance D9 après IGNITE+TEMPER ; amorce la chaîne céramique C9).

## 1. AUDIT / PHASE

- **PHASE :** post-Phase-4, ère cargo-less (ADR-0008). Boucle agent : **8** capacités branchées.
- **P0 :** D12/R0 — **en cours de fermeture (8/20)**.
- **TÂCHE :** câbler C5 (DIG argile). IMPACTÉ_PAR_VEILLE : OUI.

## 2. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #8 — `ActionKind.DIG` consomme C5 clay_outcrop.**

- 8ᵉ capacité (C3→C2→C14→C18→C20→C7→C8→**C5**), **précurseur non-feu** : la matière de la future
  poterie. `inv_clay` se remplit ∝ `pottery_grade` × travaillabilité.
- **Nouveau champ d'inventaire `inv_clay`** ajouté exactement comme `inv_pigment` (dataclass + init +
  **2 listes de persistance**, chargement défensif → anciennes sauvegardes compatibles).
- Mensonge #13 : plastique (céramique) > schiste silteux ; hors fenêtre plastique → fraction humide
  seulement (appris en agissant).
- Garde-fous : D8 (`PY_TO_RUST` reste 15), D10 (pas de `mine_at`), D9 (non-feu → alternance rétablie),
  zéro-régression par construction (`bootstrap` n'installe pas C5).
- Vérif : `test_clay_digging_loop.py` **12/12** ; smoke **p163 8/8** ; ruff clean ; CI p162 → **p163** ;
  non-régression p162 (TEMPER) **9/9**.

## 3. RECOMMANDATIONS — R-J19(run2)-x

- **R (P1) — Première transformation à deux ingrédients : C9 `ceramic_firing`** (argile `inv_clay` +
  feu `has_made_fire` → poterie). Ce serait la 1ʳᵉ capacité à *consommer* une matière qu'un autre wire
  rend récoltable (DIG), bouclant argile→feu→pot — un saut qualitatif (jusqu'ici chaque wire était
  autonome).
- **R (P1) — Ou C6 `limestone_outcrop`** (l'autre intrant du four, calcaire→chaux C10) pour continuer
  d'alterner non-feu et garnir les intrants avant les transformations.
- **R (P2) — Registre de capacités + budget de perception** : `decide()` porte maintenant **8**
  lectures gated ; préparer un dispatch ordonné avant la 10ᵉ bouchée (dette ADR-0009 §Conséquences).

## 4. Verdict

| Question | Réponse J+19 run2 |
|---|---|
| Améliorations ? | **Oui — 8ᵉ capacité (D12 8/20), précurseur non-feu, chaîne céramique amorcée.** |
| Rust ? | **Non** (ADR-0008). |
| Push ? | **Oui — `main`.** |
| Prochaine bouchée ? | **C9 ceramic_firing** (1ʳᵉ transformation à deux ingrédients, consomme `inv_clay`) ou C6 limestone. |
