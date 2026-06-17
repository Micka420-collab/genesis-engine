# Cap. C11 — `kiln_draft` : le four à tirage (apparatus)

**Date :** 2026-06-17 (J+7, run #2) · **Seed :** `0xBEEF` (prairie) · **Smoke :** `p143` (7/7)
**Tests :** +23 (`test_kiln_draft.py`) · **pytest : 613/613** (590→613)
**Mode :** scheduled task (World Realism System v2.0, user absent) · veille-first.

---

## 1. Pourquoi — la VOÛTE que C9 ET C10 désignent toutes deux

C9 `ceramic_firing` laisse `vitrifies_if_kiln_fired` non réalisé ; C10 `lime_burning`
laisse `would_mortar_if_kiln_fired` non réalisé. **Les deux pointent vers le même outil
futur — un four.** Un feu nu plafonne (~850 °C, SSOT C9) parce qu'il perd presque
toute sa chaleur à l'air libre. **Enfermer** ce feu dans une enceinte d'argile (parois,
C5) et lui donner un **tirage** (tirage ascendant) le rend *plus chaud* et *plus
longtemps* : c'est un **four à tirage** (updraft kiln), ~1000–1100 °C — le régime qui
cuit le calcaire pur **à cœur** (mortier liant, C10 réalisé) et fritte le kaolin en
**corps sain** (C9 racheté).

**Veille du jour (run #2 — `2026-06-17_VEILLE_kiln_draft.md`) :** archéométrie de la
pyrotechnologie. Feu ouvert / bonfire ~600–900 °C (CONFIRME `OPEN_FIRE_MAX_C` 850) ;
four à tirage ~1000–1100 °C (enceinte + tirage + long séjour) ; fire-clay (kaolin)
1515–1775 °C, garnissage de four ; charbon + soufflet 1100–1300 °C (bas-fourneau). La
physique de C11 en découle — **rien n'est arbitraire** (méta-règle du substrat).

`kiln_draft.py` n'est **pas** une transformation de matière : c'est un **APPARATUS** —
le pendant de C7 `fire_ignition`. C7 expose « un feu *peut* être fait ici » ; C11 expose
« un **four** (un feu enclos plus chaud) *peut* être fait ici ». Il n'invente aucune
matière ; il **élève la température de pointe** que voit la matière, et c'est cette
pointe plus haute qui débloque les transformations différées de C9 et C10.

## 2. Ce qui est livré — LE COMBO

`runtime/engine/kiln_draft.py` — **lit** C5 `clay_outcrop` (`clay_cue_for_chunk` :
matière de paroi, `clay_class`, `ceramic_grade` = réfractaire ⇔ kaolin, `pottery_grade`)
**×** C7 `fire_ignition` (`ignition_cue_for_chunk` : feu faisable + `fine_fuel`) **×**
C6 `limestone_outcrop` (carbonate, pour réaliser le mortier), et **RÉUTILISE VERBATIM**
les SSOT de C9 (`open_fire_peak_temp_c` — *le combo* : la base est le feu nu ;
`clay_maturation_temp_c`, `fired_ware_quality`) et de C10 (`calcination_onset_c`,
`calcination_extent`, `quicklime_quality`). Aucune re-modélisation.

La **SSOT** déterministe — la physique que le monde s'engage à tenir :
- `kiln_peak_temp_c(fine_fuel, wall_refractory)` = pointe du feu nu (C9) + gain
  d'enceinte, **plafonné par la réfractarité de paroi**.
  - paroi commune (`shale`) : plafond `KILN_COMMON_WALL_CAP_C` = **1000 °C** (elle flue au-delà).
  - paroi réfractaire (kaolin, `fine_clay`) : plafond `KILN_REFRACTORY_WALL_CAP_C` = **1150 °C**.

`KilnCue` expose : `wall_material`/`wall_refractory`, `open_fire_peak_c` (baseline C9),
`kiln_peak_c`, `draft_gain_c`, `clay_firedness`/`fires_clay_sound`/`kiln_ware_quality`
(C9 recomposé), `vitrifies_watertight` (**toujours False** en tirage naturel) /
`vitrifies_if_forced_draught`, `limestone_here`/`realizes_binding_mortar`/
`mortar_lime_yield` (C10 réalisé). API : `kiln_cue_for_chunk` / `prospect_kiln` /
`kiln_preview` (non mutant) / `discover_kiln_sites_by_sight` / `best_kiln_site_near` /
`kiln_draft_summary`.

### L'inversion DE l'inversion (le rachat du kaolin C9 — mensonge rendu visible)
| Site (prairie, `fine_fuel` 0,80) | paroi | `kiln_peak_c` | kaolin firedness | Note |
|----------------------------------|-------|---------------|------------------|------|
| Argile commune (`shale`) | commune (plafond 1000) | **1000 °C** | 0,80 → **sous-cuit** | ne cuit JAMAIS le kaolin sain |
| Kaolin (`fine_clay`) | **réfractaire** (plafond 1150) | **1070 °C** | 0,86 → **SAIN** | le kaolin réfractaire (la *mauvaise* argile de poterie C9) est la **meilleure paroi** |

Le kaolin — sous-cuit comme *poterie* au feu ouvert (firedness 0,64, le mensonge de
C9) — est l'**argile de PAROI** idéale : c'est *grâce à lui* qu'on bâtit le four assez
chaud pour, enfin, cuire le kaolin **à cœur**. `best_kiln_site_near` (préfère la pointe
la plus haute) enseigne donc : **chemise ton four de l'argile blanche collante**.

### Le mortier liant réalisé (C10 différé → réalisé)
Le calcaire pur (`limestone_pure`, `mortar_grade`), **sous-cuit** au feu ouvert (C10,
extent 0,62 < `MORTAR_CALCINATION` 0,92), **se calcine à cœur** au four (extent → 1,0 ≥
0,92) : `realizes_binding_mortar` True. Dans le monde réel 0xBEEF, **87/144** sites de
four réalisent le mortier liant — la « plus ancienne industrie chimique » enfin atteinte.

### La marche différée honnête — le tirage FORCÉ (C12+)
Le tirage **naturel** plafonne sous la vitrification complète de la porcelaine
(~1250 °C) : `vitrifies_watertight` reste False et `vitrifies_if_forced_draught` porte
le **potentiel** du soufflet + charbon (1100–1300 °C, régime du bas-fourneau) —
exactement comme C9/C10 différaient *vers* le four. La chaîne reste ouverte.

## 3. Invariants tenus

- **« Le monde ne ment jamais ».** Un cue ⇒ `buildable` : l'argile (C5) et le feu (C7)
  existent réellement ; `kiln_peak_c` ≥ pointe du feu nu, ≤ plafond de paroi, == SSOT ;
  `kiln_ware_quality` == SSOT C9 ; mortier réalisé ⇒ carbonate mortar-grade présent (C6).
  Vérifié sur colonnes synthétiques ET monde Genesis réel (smoke `p143`, 0 viol).
- **Émergence absolue** ([[feedback_stone_age_emergence]], [[feedback_no_scripting]]) :
  on n'apprend pas à l'agent à « construire un four ». On expose le fait physique —
  entourer un feu d'argile réfractaire le rend plus chaud — et l'agent découvre le four
  en agissant. Forme, cheminée, tirage, empilement : émergents.
- **Garde-fou D8 par composition (5ᵉ fois après C7/C8/C9/C10)** : pas de `_PROFILE`,
  **`PY_TO_RUST` reste 15**, hors glob `*_outcrop.py`, `test_introduces_no_new_tell`.
- **Déterminisme** : composition pure de cues `prf_rng` + SSOT purs. Bit-identique
  même-seed.
- **Coût tick nul** : installation idempotente, dérivation paresseuse + mémoïsée, aucun
  hook sur `sim.step`.
- **Cargo-less** ([[reference_env_no_cargo]]) : Python pur ; ne ferme aucun item Rust
  Phase A/B (ADR-0008 inchangé).

## 4. Chiffres

- **pytest 613/613** (590 → 613, +23) · **ruff clean** · smoke **p143 7/7**.
- Monde réel 0xBEEF : 144/144 chunks constructibles, 17 parois réfractaires (kaolin),
  **87 réalisent le mortier liant**, 144 cuisent l'argile saine, pointe max **1070 °C**
  (gain d'enceinte +270 °C sur le feu nu).
- Géologie/sociétés : pyrotechnologie 78 → 79 (la voûte C9/C10 fermée), global ~80,1 %.

## 5. Gap honnête

- Le four lui-même est l'apparatus (pointe atteignable) ; la **construction** physique
  (parois, cheminée, alandier) reste émergente — non modélisée comme structure.
- Le **tirage forcé** (soufflet + charbon → vitrification complète + métallurgie) est
  explicitement différé (`vitrifies_if_forced_draught`) — prochaine capacité naturelle.
- La cinétique de cuisson (rampe, séjour, atmosphère oxydante/réductrice) est résumée
  en une pointe d'équilibre — simplification honnête, comme C9/C10.
