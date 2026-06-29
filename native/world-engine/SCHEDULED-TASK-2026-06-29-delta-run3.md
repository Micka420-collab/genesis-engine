# Tâche planifiée 2026-06-29 (J+19, run 3) — run PRODUCTIF (code livré + push)

> **Type :** exécution. **3ᵉ cycle du jour** (run 1 = C8 TEMPER, run 2 = C5 DIG).
> **Référence :** [`SCHEDULED-TASK-2026-06-29-delta-run2.md`](SCHEDULED-TASK-2026-06-29-delta-run2.md) ·
> [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Sprint doc :** [`docs/sprints/2026-06-29_D12-WIRE-C9-ceramic-firing.md`](../../docs/sprints/2026-06-29_D12-WIRE-C9-ceramic-firing.md).
> **Contexte :** session utilisateur « continue » + battement de cœur horaire `genesis-arc-wiring-heartbeat`.

## 0. VEILLE (avant code)

- Cuisson céramique émergente + chaînes de craft à deux ingrédients (Vintage Story / TerraFirmaCraft)
  → **valident** la transformation à deux intrants comme saut de la boucle agent. Pas de pivot ;
  aucune brique externe (cargo-less). **CVE : aucune.**
- **COMBO_RETENU :** `utility-based action selection` × `C9 ceramic_firing` → 9ᵉ tranche, **la
  transformation néolithique fondatrice** et le **1ᵉʳ wire dont les intrants sont deux produits
  d'autres wires** (argile DIG/C5 + feu IGNITE/C7).

## 1. AUDIT / PHASE

- **PHASE :** post-Phase-4, ère cargo-less (ADR-0008). Boucle agent : **9** capacités branchées.
- **P0 :** D12/R0 — **en cours de fermeture (9/20)**.
- **TÂCHE :** câbler C9 (FIRE_CLAY). IMPACTÉ_PAR_VEILLE : OUI. **L'arc se referme sur lui-même.**

## 2. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #9 — `ActionKind.FIRE_CLAY` consomme C9 ceramic_firing (= C5 × C7).**

- 9ᵉ capacité, **JALON** : 1ʳᵉ bouchée dont les deux intrants viennent de deux wires antérieurs.
  L'agent qui **sait faire le feu** (`has_made_fire`) **et porte de l'argile** (`inv_clay`, dug par
  DIG) **cuit** un site de cuisson → `inv_ceramic` ∝ `ware_quality`. Chaîne **argile→feu→pot** vécue.
- **Flux matière inter-capacités** : `apply_decision` consomme `inv_clay` et émet `inv_ceramic`.
- **Nouveau champ `inv_ceramic`** (comme `inv_clay`/`inv_pigment` : dataclass + init + 2 listes de
  persistance, chargement défensif).
- Mensonge #14 (inversion réfractaire) : sur feu ouvert, le schiste humble cuit sound ; la kaolinite
  fine reste sous-cuite → argile perdue, 0 pot. Vitrification impossible sans four (`watertight` False).
- Garde-fous : D8 (`PY_TO_RUST` reste 15, compose C5×C7), D10 (pas de `mine_at`), gate double
  (feu + argile), zéro-régression par construction.
- Vérif : `test_ceramic_firing_loop.py` **13/13** ; smoke **p164 8/8** ; ruff clean ; CI p163 → **p164** ;
  non-régression p163 (DIG) **8/8**.

## 3. RECOMMANDATIONS — R-J19(run3)-x

- **R (P1) — Continuer la chaîne pyrotechnologique à deux intrants :** **C10 `lime_burning`**
  (calcaire + feu → chaux) — exige d'abord de brancher **C6 `limestone_outcrop`** (récolte non-feu,
  miroir de DIG) ; ou **C13 `copper_smelting`** (minerai + combustible + feu → métal, `inv_metal`).
- **R (P0 montant) — Registre de capacités + budget de perception.** `decide()` porte **9** lectures
  gated ; la dette ADR-0009 §Conséquences atteint le seuil « quelques branchements ». Prochaine
  itération : un dispatch ordonné de seeks + un budget, avant la 10ᵉ bouchée.
- **R (P2) — Promouvoir `climate_biome` + `river_discharge`** dans le set runtime par défaut (inchangé).

## 4. Verdict

| Question | Réponse J+19 run3 |
|---|---|
| Améliorations ? | **Oui — 9ᵉ capacité (D12 9/20) ; l'arc se referme (chaîne argile→feu→pot vécue).** |
| Rust ? | **Non** (ADR-0008). |
| Push ? | **Oui — `main`.** |
| Prochaine bouchée ? | **C6 limestone** (récolte, prépare C10) ou **C10 lime_burning / C13 copper_smelting** (transformations à deux intrants) ; + commencer le registre de capacités. |
