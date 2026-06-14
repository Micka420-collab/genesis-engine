# Cap. C6 — `limestone_outcrop` : découverte émergente du calcaire

**Date** : 2026-06-14 · **Type** : capacité agent (6ᵉ, pas un observateur) ·
**Couche** : World/Substrate · **Smoke** : `p138` (7/7) ·
**Tests** : `tests/test_limestone_outcrop.py` (25) + contrat cross-langage (+1)

> Veille du jour : [`docs/veille/2026-06-14_VEILLE_limestone_outcrop.md`](../veille/2026-06-14_VEILLE_limestone_outcrop.md)

---

## Pourquoi

C5 a livré l'**argile** — le matériau qui *contient* (récipient de l'eau C3, four
du feu C4, creuset du métal, brique). Son **pendant construction** est le calcaire,
le matériau qui *bâtit* et *colle* : la **pierre de taille** et la **chaux** qui
lie les pierres entre elles. La veille du jour ancre ce maillon dans l'âge de
pierre : la **chaux est le plus ancien liant connu** — néolithique (9000–6000 av.
J.-C., sols d'enduit de chaux à Göbekli Tepe ~9500 av. J.-C.), **antérieur à la
métallurgie**, au verre, parfois à l'agriculture (*Burning Lime — the oldest
chemical industry on Earth*).

Or **le calcaire restait muet** côté découverte :

- la géologie portait une lithologie `limestone` (couverture sédimentaire des
  plateformes carbonatées, ~5 m) et des ores carbonatés (`calcite`, `dolomite`),
  sans aucun signal exploitable comme pierre à bâtir / source de chaux ;
- la crate Rust `genesis-geology` réservait depuis Wave 43 un
  `Mineral::LimestonePure` (« Quicklime precursor — pure carbonate beds », couleur
  `[245,240,225]`) — **orphelin** : le contrat cross-langage le notait *« Python
  models as limestone/calcite (catalogue), coarse Rust bins it »*.

## Ce que fait la capacité

`engine.limestone_outcrop` rend l'**affleurement carbonaté** perceptible, sans rien
scripter. Un agent ne *sait* pas qu'on en fait du mortier : il **VOIT** une falaise
blanche, en détache un bloc (sain ⇒ tient l'arête), le **brûle** (carbonate pur ⇒
chaux vive), l'**éteint** à l'eau (pâte qui durcit) — le mortier / l'enduit / la
maçonnerie émergent.

### Combo veille 1+1>2 — deux propriétés honnêtes et **orthogonales**

- **D1 — grade de chaux (pureté carbonatée → mortier)** : la décarbonatation
  (CaCO3 → CaO + CO2) se produit vers 700–900 °C (max ~782 °C). Tout carbonate
  calcine, mais seul le **pur** donne une chaux vive réactive →
  - `limestone_pure` (ore, calcaire de haute pureté) → `lime_grade = 0.95`,
    `mortar_grade` ✓ (chaux/plâtre). C'est le `LimestonePure` du crate Rust, tell
    `(245,240,225)` **byte-exact** ;
  - `calcite` (0.92), `marble` (0.86) → également mortier ;
  - `limestone` (0.72, lithologie commune, légèrement argileuse), `dolomite`
    (0.55) → pierre à bâtir + chaux faible seulement (`mortar_grade` ✗).
  Seuil `MORTAR_GRADE = 0.80`. **Intrinsèque au matériau** : on peut brûler une
  pierre fissurée — la chaux ne demande pas un bloc sain.
- **D3 — aptitude au dressage (altération → blocs)** : la même falaise blanche
  n'est pierre de taille que **saine**. L'eau de pluie légèrement acide dissout
  le carbonate (karstification — « plus la calcite est pure, plus elle se
  dissout ») :
  - exposition humide (`ambient > KARST_MOISTURE = 0.62`) → `karst_fissured`
    (cavités, lapiez ; carrer la roche saine en dessous) ;
  - biome gelant (ICE/TUNDRA) → `frost_shattered` (cryoclastie — lien **Wave 50**
    frost weathering) ;
  - sinon → `sound_quarry` → `dressable_now` ✓.
  Les trois états sont **mutuellement exclusifs et exhaustifs**. Effet 1+1>2 :
  hydrologie de surface (SYSTÈME A) × géologie (SYSTÈME C) × gel (Wave 50) —
  une seule vérité de substrat (biome + `chunk.water`), plusieurs lectures
  (C4 veut le **sec**, C5 le **plastique**, C6 le **sain**).

`mortar_grade` (chaux) et `dressable_now` (blocs) sont **indépendants** : un
calcaire pur karst-fissuré brûle en bon mortier mais ne se dresse pas en blocs ;
un calcaire commun sain se dresse en blocs mais ne fait qu'une chaux faible.

### « Le monde ne ment jamais »

Un indice n'est émis QUE si le carbonate existe réellement dans la même colonne
`chunk_geology` que `mine_at` : `lithology` ⇒ couche peu profonde `rock_type ∈
{limestone, marble}` ; `ore` ⇒ couche peu profonde avec carbonate ≥ seuil de
visibilité. `mortar_grade` ⇒ `lime_grade ≥ 0.80`. `dressable_now` ⇒ exposition
saine ET pierre de taille. Réciproque volontairement faible (un banc sous 50 m de
grès ne trahit rien) → émergence préservée. `work_preview` est un **oracle non
mutant** : `can_dress` vrai seulement si carbonate réel + sain + pierre de taille
→ le mensonge (falaise karst *vue* mais infaçonnable en blocs) rendu visible.

## Émergence & moratoire

**Émergence absolue** : on rend le carbonate, sa pureté et son altération
détectables, jamais « construis un mur » ni « fais du mortier ». **Capacité, pas
observateur** : aucun hook `sim.step`, coût tick nul (cues paresseux mémoïsés) →
conforme au moratoire observateurs (Wave-64+). Déterminisme pur (`prf_rng` via
`chunk_geology` + biome + `chunk.water`), bit-identique même-seed.

## Garde-fou ADR-0007 (cross-langage)

C6 **ferme l'orphelin `LimestonePure`** :
1. ajout d'un vrai `limestone_pure` (calcaire pur `CaCO3`, catégorie CARBONATE)
   au catalogue Python (appendu en fin de `MINERALS` → `MINERAL_INDEX` stable) ;
2. `PY_TO_RUST` enrichi `limestone_pure → LimestonePure` (sorti de `RUST_ONLY`) ;
3. tell `(245,240,225)` verrouillé **byte-exact** ⇔
   `Mineral::LimestonePure::surface_color()` — **4ᵉ référence couleur** après
   malachite (cuivre), charbon, et fine_clay (argile).

Risque de perturbation de `_select_ore_mix` par le nouveau minéral : **vérifié nul**
— smokes C1/C4/C5 (dont `p137`, même seed `0xC1A7`) restent verts (le `fine_clay`
de C5 n'est pas déplacé), suite pytest verte.

## Validation

- `tests/test_limestone_outcrop.py` : 25 tests (hiérarchie/seuils, tell byte-exact,
  pierre de taille vs veine, dérivation pure, portes pureté + altération
  karst/gel/sain, orthogonalité mortier/dressage, monde ne ment jamais synthétique
  + réel seed `0xC1A7`, `work_preview` non mutant, `best_limestone_near` filtres,
  déterminisme, install idempotent).
- `tests/test_geology_cross_language_contract.py` : +1
  (`test_limestone_pure_tell_is_byte_exact`).
- `scripts/p138_limestone_outcrop_smoke.py` : 7/7 sur monde Genesis réel (seed
  `0xC1A7` : 144 chunks, 123 calcaire pur + 21 calcaire commun, 123 grade mortier,
  144 dressables, 0 violation).
- Makefile `validate-all` + CI smoke list : `p138` ajouté.

## Gap honnête

- La cinétique de calcination (température/durée du four à chaux) et le cycle de la
  chaux (CaO → Ca(OH)₂ → CaCO₃ par recarbonatation) ne sont pas simulés : le grade
  de chaux est intrinsèque au matériau, pas un processus de cuisson.
- La distinction chaux **aérienne** vs **hydraulique** (selon la teneur en argile)
  n'est pas modélisée (les deux classes sont des seuils, pas un continuum
  argilo-calcaire).
- Ne ferme **aucun** item Rust Phase A/B (D5-wiring reste dû ; `cargo` absent →
  CI = vérité). C'est une capacité du **runtime Python live**.
