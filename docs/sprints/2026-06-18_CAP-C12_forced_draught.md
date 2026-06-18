# Cap. C12 — `forced_draught` : le tirage forcé (apparatus)

**Date :** 2026-06-18 (J+8) · **Seed :** `0xBEEF` (prairie) · **Smoke :** `p144` (7/7)
**Tests :** +21 (`test_forced_draught.py`) · **pytest : 634/634** (613→634)
**Mode :** scheduled task (Morning Routine v3.0, user absent) · veille-first.

---

## 1. Pourquoi — la VOÛTE que C9 ET C11 désignent toutes deux

C9 `ceramic_firing` laisse `vitrifies_if_kiln_fired` non réalisé ; C11 `kiln_draft`
laisse `vitrifies_if_forced_draught` non réalisé — **les deux pointent vers le même
outil : un tirage forcé.** Un four à tirage *naturel* (C11) plafonne (~1000–1150 °C)
sous la vitrification de la porcelaine (~1250 °C) et sous la métallurgie. Le pas qui
manque est un **soufflet** (qui injecte l'air bien au-delà de la convection) + un
**charbon de bois** (dense, sans volatils, sans flamme refroidissante). Souffler de
l'air sur du charbon enclos pousse la pointe dans le **régime du bas-fourneau**
(~1100–1400 °C) : assez chaud pour **vitrifier** le kaolin réfractaire (céramique
étanche) et **fondre le cuivre** (1085 °C, le seuil chalcolithique, le premier métal).

**Veille du jour (`2026-06-18_VEILLE_forced_draught.md`) :** archéométrie du bas-
fourneau (EXARC, MDPI Heritage 2025 : soufflet/tuyère → 1100–1300 °C) et de la
métallurgie du cuivre chalcolithique (Belovode ~5000 av. J.-C. : malachite + charbon +
~1100–1200 °C → cuivre + scorie vitreuse). La physique de C12 en découle — **rien n'est
arbitraire** (méta-règle du substrat). La veille de C11 avait *déjà backloggé* ce palier
(D3) : C12 le réalise.

`forced_draught.py` n'est **pas** une transformation de matière : c'est un **APPARATUS**
— le pendant de C11. C11 expose « un **four** *peut* être fait ici » ; C12 expose « un
**four à tirage forcé** (soufflet + charbon) *peut* être fait ici ». Il n'invente aucune
matière ; il **élève encore la pointe**, et cette pointe **réalise** la vitrification
(différée par C9 puis C11) et **ouvre** la métallurgie.

## 2. Ce qui est livré — LE COMBO

`runtime/engine/forced_draught.py` — **lit** C11 `kiln_draft` (`kiln_cue_for_chunk` :
paroi, `wall_refractory`, `fine_fuel`, `clay_pottery_grade`, `clay_ceramic_grade`) **×**
C1 `surface_mineralization` (`surface_cue_for_chunk` : le tell vert cuivre
malachite/azurite), et **RÉUTILISE VERBATIM** les SSOT de C11 (`kiln_peak_temp_c` — *le
combo* : la base est le four naturel) et de C9 (`clay_maturation_temp_c`,
`fired_ware_quality`, `VITRIFICATION_FIREDNESS`). Aucune re-modélisation.

La **SSOT** déterministe — la physique que le monde s'engage à tenir :
- `forced_draught_peak_c(fine_fuel, wall_refractory)` = pointe du four naturel (C11) +
  gain du tirage forcé, **plafonné par la réfractarité de paroi sous soufflet**.
  - paroi commune (`shale`) : plafond `FORCED_COMMON_WALL_CAP_C` = **1100 °C** (slumpe juste au-delà du cuivre).
  - paroi réfractaire (kaolin, `fine_clay`) : plafond `FORCED_REFRACTORY_WALL_CAP_C` = **1400 °C** (régime du bas-fourneau).
- Seuils métallurgie : `COPPER_SMELT_TEMP_C` = **1085 °C** (fusion du cuivre) ;
  `IRON_BLOOMERY_TEMP_C` = **1200 °C** (réduction du fer — paroi réfractaire seule).
- Porte du charbon : `CHARCOAL_FUEL_FLOOR` = **0,45** (combustible ligneux suffisant
  pour charbonner + alimenter le soufflet).

`ForcedDraughtCue` expose : `wall_material`/`wall_refractory`, `kiln_peak_c` (baseline
C11), `forced_peak_c`, `forced_gain_c`, `charcoal_makeable` ; la **RÉALISATION** :
`clay_firedness`/`fires_clay_sound`/`vitrifies_watertight` (**enfin True** pour le
kaolin) / `vitrified_ware_quality` (C9 recomposé) ; l'**OUVERTURE** :
`reaches_copper_smelting_temp` × `copper_ore_here`/`copper_mineral` →
`would_smelt_copper_here` / `smelts_copper_if_ore_present`, et
`reaches_iron_bloomery_temp` (différé). API : `forced_cue_for_chunk` /
`prospect_forced_draught` / `forced_draught_preview` (non mutant) /
`discover_forced_sites_by_sight` / `best_forced_site_near` (`require_smelting`,
`require_vitrifying`) / `forced_draught_summary`.

### La RÉALISATION — l'arc « mensonge du kaolin » se ferme (C9 → C11 → C12)
| Étape | régime | kaolin firedness | watertight |
|-------|--------|------------------|------------|
| C9 `ceramic_firing` | feu nu (~800 °C) | 0,64 → **sous-cuit** | False (le mensonge) |
| C11 `kiln_draft` | four naturel (1070 °C) | 0,86 → **sain** mais pas étanche | False |
| **C12 `forced_draught`** | **soufflet+charbon (1295 °C)** | **1,00 → VITRIFIE** | **True** ✅ |

La paroi réfractaire (la *mauvaise* argile de poterie C9, la meilleure paroi C11) est
*la même* qui, sous tirage forcé, **vitrifie** enfin le corps de kaolin ET atteint le
régime du fer. La pire argile de poterie est la **seule clé** de la haute
pyrotechnologie. `best_forced_site_near` (préfère la pointe la plus haute) l'enseigne.

### L'OUVERTURE — la métallurgie du cuivre (différée pour la fonte effective)
C1 montre la « tache verte » du cuivre comme une enseigne. C12 dit la vérité honnête :
`reaches_copper_smelting_temp` (four ≥ 1085 °C) × `copper_ore_here` (C1 voit le cuivre
ici) → `would_smelt_copper_here`. La **fonte effective** (consommer la malachite →
bouton de cuivre + scorie) reste une **transformation différée (Cap. C13)** — exactement
comme C9/C11 différaient *vers* le four puis le tirage forcé. La chaîne reste ouverte.

## 3. Invariants tenus

- **« Le monde ne ment jamais ».** Un cue ⇒ `forceable` : le four (C11) existe
  réellement et le combustible est de grade charbon ; `forced_peak_c` ≥ pointe du four
  naturel, ≤ plafond de paroi, == SSOT ; `vitrified_ware_quality` == SSOT C9 ; cuivre
  co-localisé ⇒ C1 le voit. Vérifié sur colonnes synthétiques ET monde Genesis réel
  (smoke `p144`, 0 viol).
- **Émergence absolue** ([[feedback_stone_age_emergence]], [[feedback_no_scripting]]) :
  on n'apprend pas à l'agent à « souffler sur du charbon pour fondre le métal ». On
  expose le fait physique — un four de charbon soufflé monte plus haut, vitrifie la
  céramique, fait suinter le cuivre — et l'agent découvre le tirage forcé en agissant.
  Soufflet, tuyère, charbonnage en meule, coulée : émergents.
- **Garde-fou D8 par composition (6ᵉ fois après C7/C8/C9/C10/C11)** : pas de `_PROFILE`,
  **`PY_TO_RUST` reste 15**, hors glob `*_outcrop.py`, `test_introduces_no_new_tell`.
- **Déterminisme** : composition pure de cues `prf_rng` + SSOT purs. Bit-identique
  même-seed (0 RNG nouveau).
- **Coût tick nul** : installation idempotente, dérivation paresseuse + mémoïsée, aucun
  hook sur `sim.step`.
- **Cargo-less** ([[reference_env_no_cargo]]) : Python pur ; ne ferme aucun item Rust
  Phase A/B (ADR-0008 inchangé).

## 4. Chiffres

- **pytest 634/634** (613 → 634, +21) · **ruff clean** · smoke **p144 7/7**.
- Monde réel 0xBEEF : 144/144 chunks forçables, 17 parois réfractaires (kaolin) qui
  **vitrifient watertight** (là où C9/C11 laissaient False), **144 atteignent le seuil
  du cuivre** (1085 °C), 17 atteignent le régime du fer (1200 °C). Pointe max **1295 °C**
  (gain du soufflet +225 °C sur le four naturel).
- Géologie/sociétés : pyrotechnologie 79 → 80 (vitrification + seuil métallurgie),
  global ~80,2 %.

## 5. Gap honnête

- Le four à tirage forcé est l'apparatus (pointe atteignable) ; le **soufflet**, la
  **tuyère**, le **charbonnage en meule** restent émergents — non modélisés comme outils.
- La **fonte effective** du métal (consommer le minerai → bouton de cuivre + scorie) est
  explicitement différée (`would_smelt_copper_here` n'est qu'un potentiel ground-truthé)
  — prochaine capacité naturelle (Cap. C13 `copper_smelting`, 1ʳᵉ transformation
  métallurgique).
- Le **bas-fourneau du fer** (`reaches_iron_bloomery_temp`, paroi réfractaire requise)
  porte la chaîne plus loin encore — atmosphère réductrice CO, fluxage : différé.
- La porte du charbon (`CHARCOAL_FUEL_FLOOR`) utilise le proxy `fine_fuel` (pas un signal
  « bois » distinct) : dans le jeu de biomes actuel, tout site four-constructible est
  aussi charbonnable — la porte est donc **défensive** (elle mord au niveau SSOT, garde
  un futur biome « feu-mais-peu-de-bois »). Simplification honnête.
- La cinétique (rampe, séjour, atmosphère) est résumée en une pointe d'équilibre —
  comme C9/C10/C11.
