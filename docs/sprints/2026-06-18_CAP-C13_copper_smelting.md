# Cap. C13 — `copper_smelting` : la fonte du cuivre (transformation métallurgique)

**Date :** 2026-06-18 (J+8, run #2) · **Seed :** `0xBEEF` (prairie) · **Smoke :** `p145` (7/7)
**Tests :** +19 (`test_copper_smelting.py`) · **pytest : 653/653** (634→653, +1 skip)
**Mode :** scheduled task (World Realism System v2.0, user absent) · veille-first.

---

## 1. Pourquoi — la promesse que C12 différait explicitement

C12 `forced_draught` a porté un four enclos (C11) soufflé au charbon **au-delà du point
de fusion du cuivre** (1085 °C) et exposé `would_smelt_copper_here` comme un **potentiel
ground-truthé**, en différant *« la fonte effective (consommer le minerai → produire le
métal) »* à **Cap. C13**. Ce run la **réalise** : C13 est la **4ᵉ transformation** (après
C8/C9/C10) et la **1ʳᵉ métallurgique** — le **seuil chalcolithique**, le **premier métal**.

**Veille du jour (`2026-06-18_VEILLE_copper_smelting.md`) :** Belovode (~5000 av. J.-C.,
la plus ancienne fonte extractive datée) — malachite grillée + réduite à 1100–1200 °C →
prills de cuivre dans une scorie vitreuse ; archéométrie des sulfures (chalcopyrite : il
faut **griller** ~590 °C avant de fondre en matte) ; rendement-scorie honnête (la fonte
primitive ne récupère jamais tout le Cu). La physique de C13 en découle — **rien n'est
arbitraire** (méta-règle du substrat).

## 2. Ce qui est livré — LE COMBO + LA MUTATION

`runtime/engine/copper_smelting.py` — **lit** C12 `forced_draught`
(`forced_cue_for_chunk` : `would_smelt_copper_here`, `forced_peak_c`, `copper_mineral`)
**×** C1 `surface_mineralization` (le tell vert + `dig_depth_m`), et **RÉUTILISE
VERBATIM** le seuil `fd.COPPER_SMELT_TEMP_C` (C12) + le **rendement par élément du
catalogue minéral** (`Mineral.yields_per_kg_ore["Cu"]`, `Mineral.category`) — **aucune
teneur re-déclarée**.

La **SSOT** déterministe — la métallurgie que le monde s'engage à tenir :
- `copper_smelt_yield(ore_mineral, ore_kg, peak_c, *, roasted=False)` →
  `SmeltYield(recovered_cu_kg, slag_kg, bead_purity, requires_roasting, …)`.
  - **natif** (`native_copper`, déjà métal) : fonte directe ≥1085 °C, plafond **0,95**, pureté **0,97**.
  - **oxyde/carbonate** (malachite-type) : réduction directe, plafond **0,80**, pureté **0,92**.
  - **sulfure** (`chalcopyrite`) : **0 cru** (verrouillé en matte) ; après **grillage** (~590 °C), plafond **0,72**, pureté **0,85** (blister) ; teneur catalogue **0,35** Cu/kg.
  - rendement = teneur × efficacité ; efficacité = base de classe + bonus de surchauffe (saturant sur 200 °C), **plafonnée < 1.0** (la scorie garde toujours des prills).

`SmeltCue` expose : `copper_mineral`/`ore_class`/`requires_roasting`,
`smeltable_now`/`needs_roasting_first`, `recovered_cu_per_kg_ore` (direct, **0** pour un
sulfure cru) / `recovered_cu_per_kg_ore_roasted` (le potentiel après grillage),
`slag_per_kg_ore`, `bead_purity`, `roast_temp_c`. API oracle (non mutante,
déterministe) : `smelt_cue_for_chunk` / `prospect_smelt` / `smelt_preview` /
`discover_smelt_sites_by_sight` / `best_smelt_site_near` (`require_direct`) /
`smelt_summary`.

### La FONTE EFFECTIVE — `smelt_at` (le seul point d'entrée MUTANT de l'arc C1→C13)
`smelt_at(sim, row, *, charge_kg, roasted)` **consomme** une charge de minerai de la
colonne (réemploi de la SSOT d'extraction `geo.mine_at` — le minerai *disparaît* du sol)
et **rend** un `SmeltResult(recovered_cu_kg, slag_kg, bead_purity, …)`. C'est ce qui fait
de C13 une **vraie transformation** et non un 3ᵉ potentiel. « Le monde ne ment jamais »
devient **testable au sens fort** : le cuivre *réellement rendu* == celui que l'oracle
avait *promis* (`recovered_cu_per_kg_ore × ore_consumed_kg`, à 1e-4 près).

### Le mensonge rendu visible #4 — natif (facile) vs chalcopyrite (sulfure)
| Tell de surface (C1) | minéral | classe | fonte directe ? | rendu |
|----------------------|---------|--------|-----------------|-------|
| **tache verte** (mêmes rgb 80,140,70) | `native_copper` | natif | **oui** (≥1085 °C) | bouton de Cu (0,97) |
| **tache verte** (mêmes rgb) | `chalcopyrite` | sulfure | **non** — griller d'abord (~590 °C) | **cru → scorie seule** ; grillé → Cu (0,85) |

Le **même signe vert** couvre deux métallurgies opposées (les isotopes du plomb à
Belovode montrent que les fondeurs *connaissaient* la différence). `smelt_at` sur une
chalcopyrite crue **consomme** la charge et ne rend **que de la scorie** — la leçon
coûteuse, physiquement vraie, du sulfure. `best_smelt_site_near` (préfère le cuivre
récupérable) enseigne : **fonds le vert natif, grille le vert sulfuré.**

## 3. Invariants tenus

- **« Le monde ne ment jamais ».** Un cue ⇒ C12 `would_smelt_copper_here` : le four
  ≥1085 °C existe et le minerai (C1) est là ; `copper_mineral` == C1 ; cuivre rendu ≤
  cuivre contenu (catalogue) ; sulfure → 0 cru / >0 grillé. Au sens FORT : `smelt_at`
  rend *exactement* ce que l'oracle promet. Vérifié sur colonnes synthétiques ET monde
  Genesis réel (smoke `p145`, 0 viol).
- **Émergence absolue** ([[feedback_stone_age_emergence]], [[feedback_no_scripting]]) :
  on n'apprend pas à l'agent à « fondre la pierre verte ». On expose le fait physique —
  un four soufflé fait suinter le métal de telle roche verte (et seulement après
  grillage pour telle autre) — et l'agent découvre la fonte en agissant. Creuset,
  tuyère, fluxage, moulage : émergents.
- **Garde-fou D8 par composition (7ᵉ fois après C7…C12)** : pas de `_PROFILE`,
  **`PY_TO_RUST` reste 15**, hors glob `*_outcrop.py`, `test_introduces_no_new_tell`.
- **Déterminisme** : l'oracle est une composition pure de cues `prf_rng` + SSOT purs
  (seuil C12, catalogue). Bit-identique même-seed (0 RNG nouveau). `smelt_at` mute
  *volontairement* la géologie — c'est l'acte, pas l'oracle.
- **Coût tick nul** : oracle idempotent, dérivation paresseuse + mémoïsée, aucun hook
  sur `sim.step`.
- **Cargo-less** ([[reference_env_no_cargo]]) : Python pur ; ne ferme aucun item Rust
  Phase A/B (ADR-0008 inchangé).

## 4. Chiffres

- **pytest 653/653** (634 → 653, +19) · **ruff clean** · smoke **p145 7/7**.
- Monde réel 0xBEEF : **21/144 sites de fonte ÉMERGENTS** (sans injection) — **18 cuivre
  natif** (fonte directe, meilleur rendu **0,95** Cu/kg, pureté **0,97**) + **3
  chalcopyrite** (sulfure → grillage requis). Le mensonge #4 émerge du monde lui-même.
- Géologie/sociétés : métallurgie 80 → 81 (le premier métal effectivement coulé),
  global ~80,4 %.

## 5. Gap honnête

- La fonte est l'acte (`smelt_at`) ; le **creuset**, la **tuyère**, le **fluxage à la
  silice**, la **coulée**, le **martelage** restent émergents — non modélisés comme outils.
- Le **grillage** lui-même (consommer le sulfure cru → calcine grillée puis fondable) est
  exposé comme un **fait** (`needs_roasting_first`, `roast_temp_c`, `roasted=True` rend du
  métal) mais l'enchaînement opératoire grillage→fonte reste émergent (un feu ouvert C7/C9
  ≥590 °C suffit à griller — composition implicite non câblée).
- Le **bronze** (Cu + étain) exige de trouver *aussi* l'étain (`cassiterite` au catalogue)
  — mais l'étain ne porte **aucun tell de surface** (hors groupes d'expression C1) :
  l'agent doit l'explorer à l'aveugle. Capacité **future (Cap. C14)**, différée honnêtement.
- Le **bas-fourneau du fer** (`fd.reaches_iron_bloomery_temp`, paroi réfractaire,
  atmosphère réductrice CO) porte la chaîne plus loin encore — différé.
- La cinétique (rampe, séjour, atmosphère réductrice CO précise) est résumée en un
  rendement d'équilibre par classe — comme C9/C10/C11/C12.
