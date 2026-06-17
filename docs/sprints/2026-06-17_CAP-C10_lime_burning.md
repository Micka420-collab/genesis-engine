# Cap. C10 — `lime_burning` : cuisson de la chaux (transformation)

**Date :** 2026-06-17 (J+7) · **Seed :** `0xBEEF` (prairie) · **Smoke :** `p142` (7/7)
**Tests :** +20 (`test_lime_burning.py`) · **pytest : 590/590** (570→590)
**Mode :** scheduled task (Morning Routine v3.0, user absent) · veille-first.

---

## 1. Pourquoi — la troisième capacité de TRANSFORMATION (pendant exact de C9)

C8 `lithic_tempering` a posé la première transformation (chauffer la pierre), C9
`ceramic_firing` la deuxième (cuire l'argile → céramique). C10 est le **pendant
exact de C9** : C9 cuit l'**argile** (C5) dans un **feu** (C7) → céramique ; C10
brûle le **calcaire** (C6) dans le **même feu** (C7) → **chaux** (CaCO₃ → CaO +
CO₂↑). L'argile *contient* (récipient), le calcaire *lie* (mortier) : la **chaux est
le plus ancien liant chimique connu** — enduits de sol néolithiques de Göbekli Tepe
(~9500 av. J.-C.), *« Burning Lime, the oldest chemical industry on Earth »* —
antérieure à la métallurgie, parfois à l'agriculture. La chaux vive obtenue est un
matériau **qui n'existe pas dans la nature** : elle se réhydrate aussitôt (extinction
violente à l'eau — lien C3).

**Veille du jour (PAPER_DU_JOUR + COMBO_RETENU) :** thermochimie de la calcination
(Boynton, *Chemistry and Technology of Lime and Limestone*). Décomposition complète
de la calcite pure à **~898 °C** (P(CO₂)=1 atm) ; carbonate **commun/dolomitique**
(MgCO₃, fondants Fe/argile/alcalins) décarbonate **plus bas** (~680 °C) ; un **feu
ouvert (≤850 °C) sous-cuit donc le calcaire pur réfractaire**. La physique de C10 en
découle — **rien n'est arbitraire** (méta-règle du substrat).

## 2. Ce qui est livré — LE COMBO

`runtime/engine/lime_burning.py` — **lit** C6 `limestone_outcrop`
(`limestone_cue_for_chunk` : carbonate, `lime_grade`, `lime_class`, `mortar_grade`)
**×** C7 `fire_ignition` (`ignition_cue_for_chunk` : feu faisable + `fine_fuel`), et
**RÉUTILISE VERBATIM** la SSOT de C9 `cf.open_fire_peak_temp_c` — **le combo de la
veille** : un seul feu, deux pyrotransformations. Aucune re-modélisation de la
température du feu.

Trois **SSOT** déterministes — la physique que le monde s'engage à tenir :
- `calcination_onset_c(lime_class)` — seuil de décarbonatation : carbonate **commun**
  680 °C, **pur** réfractaire 770 °C (clé sur le `lime_class` de C6, pas de doublon).
- `calcination_extent(peak, onset)` — degré de décarbonatation `(peak−onset)/(898−onset)`
  ∈ [0,1]. Un feu nu (≤850 °C) ne décarbonate **jamais** complètement.
- `quicklime_quality(lime_grade, extent)` — qualité de la chaux, bornée [0,1].

`LimeBurnCue` expose : carbonate, `peak_temp_c`, `calcination_onset_c`,
`calcination_extent`, `well_burnt`/`underburnt`, `mortar_ready` (**toujours False**
en feu ouvert), `would_mortar_if_kiln_fired`, `lime_yield`, `confidence`,
`also_dressable_stone` (lien C6). API : `lime_burning_cue_for_chunk` /
`prospect_lime_burning` / `burn_preview` (non mutant) /
`discover_burning_sites_by_sight` / `best_burning_site_near` / `lime_burning_summary`.

### L'inversion réfractaire (le mensonge rendu visible — pendant du kaolin C9 / de l'obsidienne C8)
| Carbonate | `lime_class` | Feu ouvert (~800 °C) | `lime_yield` | Note |
|-----------|--------------|----------------------|--------------|------|
| Calcaire commun (`limestone`, fondu) | COMMON | onset 680 °C → **bien cuit** (extent 0,55) | **0,72** | brûle dans un simple grand feu |
| Dolomie (`dolomite`, Mg) | COMMON | onset 680 °C → **bien cuit** | **0,55** | chaux magnésienne |
| **Calcaire pur** (`limestone_pure`, `mortar_grade`) | **PURE** | onset 770 °C → **sous-cuit** (extent 0,23) | **0,12** | **le mensonge** : la *meilleure* pierre (lime_grade 0,95, peut lier le mortier), mais réfractaire — il faut un **four à chaux** |
| Calcite / marbre | PURE | onset 770 °C → **sous-cuit** | ~0,12 | idem |

`best_burning_site_near` (préfère la plus haute `lime_yield`) enseigne donc la leçon
émergente : **brûle la pierre grise banale, pas la belle pierre blanche** — tant que
tu n'as qu'un feu nu. Réaliser le potentiel du calcaire pur (`would_mortar_if_kiln_fired`)
exigera une **capacité future « four à chaux »** (≥ ~900 °C soutenu). Le monde ne ment
pas : il montre le mortier comme un *potentiel non réalisé*, pas comme un liant fini
(`mortar_ready` toujours False — la pointe max d'un feu nu n'atteint jamais
`MORTAR_CALCINATION`).

## 3. Invariants tenus

- **« Le monde ne ment jamais ».** Un cue ⇒ `burnable` : le carbonate existe réellement
  (C6, même colonne que `mine_at`) **ET** le feu est faisable (C7) ; `lime_yield` ==
  SSOT ; `mortar_ready` toujours False (pas de mortier liant au feu ouvert). Prouvé
  sur le monde Genesis réel (seed `0xBEEF`, **131/144 chunks cuisibles = 44 bien cuits
  (calcaire commun + dolomie) + 87 sous-cuits (calcaire pur + calcite + marbre), 0
  violation**) + boucle **calcaire+foyer cuit / calcaire pur vu idéal mais sous-cuit**
  (`burn_preview` non mutant). L'inversion vit dans le monde réel.
- **Effet 1+1>2.** Calcination possible QUE si calcaire (C6) ET feu (C7) coexistent :
  un calcaire en forêt boréale détrempée (C7 muet) n'est pas cuisible *ici* ; un feu
  sur dalle de granite sans calcaire non plus. Une seule vérité de substrat, une
  lecture nouvelle.
- **Émergence absolue.** On rend détectable que *ce calcaire-ci, calciné dans ce feu,
  donnerait telle chaux* — jamais « brûle le calcaire pour faire du mortier ». Le tas
  de cuisson, le four à chaux, le mortier, l'enduit, la maçonnerie restent émergents.
  L'agent découvre la corrélation calcaire+grand feu→liant en agissant.
- **Garde-fou D8 par COMPOSITION (4ᵉ démonstration après C7, C8 et C9).** Pas de
  `_PROFILE`, **aucune** entrée `PY_TO_RUST`/`PY_CATALOGUE_ONLY` ; fichier **hors glob**
  `*_outcrop.py`. Asservi par `test_introduces_no_new_tell`. `PY_TO_RUST` reste à
  **15 entrées** (inchangé depuis C6).
- **Capacité, pas observateur.** 0 hook `sim.step`, dérivation paresseuse memoïsée,
  **coût tick nul** → conforme au moratoire (garde D1).
- **Déterminisme bit-à-bit** (composition de cues `prf_rng`, 0 RNG nouveau).

## 4. Gap honnête

- **Pas de four à chaux.** Seul le **feu ouvert** (≤ ~850 °C) est disponible depuis
  C7 ; le mortier liant (calcination complète du carbonate pur) exige une enceinte
  soutenant ~900 °C — une **capacité « four à chaux » future** (la même enceinte qui
  vitrifiera la céramique de C9 : `vitrifies_if_kiln_fired` ⟷ `would_mortar_if_kiln_fired`).
  C10 expose cette limite (`mortar_ready` False, `would_mortar_if_kiln_fired` True pour
  le pur) sans la masquer.
- **Cycle de la chaux non simulé** au-delà de la cuisson : extinction (CaO + H₂O →
  Ca(OH)₂, lien C3), prise par carbonatation (Ca(OH)₂ + CO₂ → CaCO₃), chaux
  hydraulique (calcaire argileux). C10 expose l'affordance et l'**outcome
  ground-truthé** de la *cuisson*, pas la chimie de prise.
- **Onset keyé sur la classe de C6**, pas sur la minéralogie fine (la dolomie a deux
  paliers MgCO₃/CaCO₃ ; les fondants varient) — simplification honnête documentée
  dans la docstring, fidèle au sens (impuretés/Mg abaissent l'onset).
- **Ne ferme aucun item Rust Phase A/B** (transformation Python ; worldgen Rust gelé
  Wave 42, cf. ADR-0008).

---

**Fichiers :** `runtime/engine/lime_burning.py`,
`runtime/tests/test_lime_burning.py`,
`runtime/scripts/p142_lime_burning_smoke.py`,
`docs/veille/2026-06-17_VEILLE_lime_burning.md`.
