# Cap. C9 — `ceramic_firing` : cuisson de la céramique (transformation)

**Date :** 2026-06-16 (J+6, run #2) · **Seed :** `0xBEEF` (prairie) · **Smoke :** `p141` (7/7)
**Tests :** +18 (`test_ceramic_firing.py`) · **pytest : 570/570** (552→570)
**Mode :** scheduled task (WORLD_REALISM v2.0, user absent) · veille-first.

---

## 1. Pourquoi — la deuxième capacité de TRANSFORMATION

C8 `lithic_tempering` a posé la première transformation (chauffer la pierre).
C9 enchaîne par la **transformation néolithique fondatrice** : cuire une **argile**
(C5) dans un **feu** (C7) pour créer la **céramique**. C8 améliorait une propriété
(`knap_quality`) ; C9 **crée un matériau qui n'existe pas dans la nature** — la
terre molle, façonnée puis chauffée au-delà de la déshydroxylation (~550–600 °C),
devient pierre artificielle, irréversible. C'est le récipient qui *contient* l'eau
(C3), le grain et — plus tard — le métal : il rend le **stockage**, donc le surplus,
donc la sédentarité, possibles.

**Veille du jour (PAPER_DU_JOUR) :** seuils thermiques de la cuisson céramique
(Kostadinova-Avramova, *Archaeometry* 2025 ; corpus *Bonfire* ; EXARC 2025 ;
expérience Santa Margarida mai 2025, pic 950 °C). Feu ouvert **600–850 °C** ;
illite/kaolinite frittent **~700–750 °C** ; vitrification **~950–1050 °C**. La
physique de C9 en découle directement — **rien n'est arbitraire** (méta-règle du
substrat). Combo retenu : **seuils archéométriques × C9**.

## 2. Ce qui est livré

`runtime/engine/ceramic_firing.py` — **lit** C5 `clay_outcrop` (`clay_cue_for_chunk`
: argile, `pottery_grade`, `ceramic_grade`, fenêtre de plasticité d'Atterberg) **×**
C7 `fire_ignition` (`ignition_cue_for_chunk` : feu faisable + `fine_fuel`).

Trois **SSOT** déterministes — la physique que le monde s'engage à tenir :
- `open_fire_peak_temp_c(fine_fuel)` — pointe d'un feu **nu** : 600 °C (feu maigre)
  → 850 °C (feu riche). Un feu ouvert n'atteint **jamais** une température de four.
- `clay_maturation_temp_c(ceramic_grade)` — maturation : terre commune **700 °C**,
  kaolin réfractaire **1250 °C** (clé sur le `ceramic_grade` de C5, pas de doublon).
- `fired_ware_quality(pottery_grade, firedness)` — qualité du tesson, bornée [0,1].

`FiringCue` expose : argile, `peak_temp_c`, `maturation_temp_c`, `firedness`,
`is_sound`/`underfired`, `watertight` (toujours False en feu ouvert),
`vitrifies_if_kiln_fired`, `ware_quality`, `confidence`, + gardes de mise en forme
(`must_wet_clay_first`/`must_dry_clay_first`, lien implicite à l'eau C3). API :
`firing_cue_for_chunk` / `prospect_firing` / `firing_preview` (non mutant) /
`discover_firing_sites_by_sight` / `best_firing_site_near` / `firing_summary`.

### L'inversion réfractaire (le mensonge rendu visible — pendant de l'obsidienne C8)
| Argile | `ceramic_grade` | Feu ouvert (≤850 °C) | `ware_quality` | Note |
|--------|-----------------|----------------------|----------------|------|
| Terre schisteuse commune (`shale`, fondants Fe/chaux) | False | maturation 700 °C → **saine** | **0,45** | cuit dans un simple feu de camp |
| **Kaolin** (`fine_clay`, argile plastique) | **True** | maturation 1250 °C → **sous-cuit** | **0,16** | **le mensonge** : la *meilleure* argile (pottery_grade 0,85), mais réfractaire — il faut un **four** |

`best_firing_site_near` (préfère la plus haute `ware_quality`) enseigne donc la
leçon émergente : **cuis la terre banale, pas la belle argile blanche** — tant que
tu n'as qu'un feu nu. Réaliser le potentiel du kaolin (`vitrifies_if_kiln_fired`)
exigera une **capacité future « four »** (≥ ~1100 °C). Le monde ne ment pas : il
montre l'étanchéité comme un *potentiel non réalisé*, pas comme un pot fini.

## 3. Invariants tenus

- **« Le monde ne ment jamais ».** Un cue ⇒ `fireable` : l'argile existe réellement
  (C5, même colonne que `mine_at`) **ET** le feu est faisable (C7) ; `ware_quality`
  == SSOT ; `watertight` toujours False (pas de vitrification au feu ouvert). Prouvé
  sur le monde Genesis réel (seed `0xBEEF`, **144/144 chunks cuisibles = 127 terre
  saine + 17 kaolin sous-cuit, 0 violation**) + boucle **argile+foyer cuit / kaolin
  vu comme idéal mais sous-cuit** (`firing_preview` non mutant).
- **Effet 1+1>2.** Cuisson possible QUE si argile (C5) ET feu (C7) coexistent : une
  argile en forêt boréale détrempée (C7 muet) n'est pas cuisible *ici* ; un feu sur
  dalle rocheuse sans argile non plus. Une seule vérité de substrat, une lecture
  nouvelle.
- **Émergence absolue.** On rend détectable que *cette argile-ci, cuite dans ce
  feu, donnerait telle poterie* — jamais « cuis l'argile pour faire un pot ». La
  boulette, le colombin, le tour, le four restent émergents. L'agent découvre la
  corrélation argile+feu→récipient durable en agissant.
- **Garde-fou D8 par COMPOSITION (3ᵉ démonstration après C7 et C8).** Pas de
  `_PROFILE`, **aucune** entrée `PY_TO_RUST`/`PY_CATALOGUE_ONLY` ; fichier **hors
  glob** `*_outcrop.py`. Asservi par `test_introduces_no_new_tell`. `PY_TO_RUST`
  reste à **15 entrées** (inchangé depuis C6).
- **Capacité, pas observateur.** 0 hook `sim.step`, dérivation paresseuse memoïsée,
  **coût tick nul** → conforme au moratoire (garde D1).
- **Déterminisme bit-à-bit** (composition de cues `prf_rng`, 0 RNG nouveau).

## 4. Gap honnête

- **Pas de four.** Seul le **feu ouvert** (≤ ~850 °C) est disponible depuis C7 ; la
  vitrification (poterie étanche, fusion du métal) exige une enceinte/un tirage —
  une **capacité « four » future**. C9 expose cette limite (`watertight` False,
  `vitrifies_if_kiln_fired` True pour le kaolin) sans la masquer.
- **Cinétique non simulée** (rampe de température, durée d'enfournement, choc
  thermique/casse, atmosphère oxydante vs réductrice → couleur). C9 expose
  l'affordance et l'**outcome ground-truthé**, pas une thermodynamique de four.
- La mise en forme (façonnage, séchage avant cuisson) est reportée en garde
  honnête (`must_wet_clay_first`/`must_dry_clay_first`) via la fenêtre d'Atterberg
  de C5, pas modélisée comme étape mécanique.
- **Ne ferme aucun item Rust Phase A/B** (transformation Python ; worldgen Rust
  gelé Wave 42, cf. ADR-0008).

---

**Fichiers :** `runtime/engine/ceramic_firing.py`,
`runtime/tests/test_ceramic_firing.py`,
`runtime/scripts/p141_ceramic_firing_smoke.py`,
`docs/veille/2026-06-16_VEILLE_ceramic_firing.md`.
