# WORLD_VEILLE_REPORT — 2026-06-18 (`copper_smelting` / Cap. C13)

> Étape 0 obligatoire **avant tout code** (World Realism System v2.0 — *Veille → Combo →
> Décision → Code → Push*). Run automatique, *user absent*. La veille de C12
> (`2026-06-18`, `forced_draught`) avait **explicitement différé** *« la fonte effective
> (consommer le minerai → produire le métal) »* à C13. Ce run la **réalise**.

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-18"
  duree_recherche: "~20 min"
  contexte_env: "Python 3.14 SEUL — pas de cargo/rustc (cf. reference_env_no_cargo)."
  contrainte: >
    Toute découverte GPU/Rust/Bevy/WGSL est, par construction, NON intégrable
    aujourd'hui (pas de compilateur Rust ici). Classée BACKLOG_ROADMAP, jamais
    COMBO_TODAY. Le combo du jour DOIT être Python-pur, déterministe, cargo-less,
    sans dépendance réseau au runtime.
```

## Découvertes

```yaml
  decouvertes:
    - id: D1
      axe: "RECHERCHE 3 (géologie/minéraux) + archéométrie — la PLUS ancienne fonte de cuivre"
      techno: "Malachite (carbonate vert) grillée puis réduite en conditions réductrices à 1100–1200 °C → prills de cuivre + cuprite dans une matrice vitreuse silicatée"
      source: "Radivojević et al., J. Archaeological Science (Belovode, Serbie ~5000 av. J.-C., la plus ancienne fonte datée) ; Springer 'Early Balkan Metallurgy 6200–3700 BC'"
      telecharge: false
      applicable_a: "Substrate · SSOT copper_smelt_yield (le seuil chalcolithique)"
      gain_estime: "réalisme : le premier métal devient une TRANSFORMATION effective ground-truthée (mutation géologique), pas un potentiel"
      action: COMBO_TODAY
      note: >
        Belovode : 1ʳᵉ fonte extractive sécurisée au monde, ~5000 av. J.-C. ; minerais
        de malachite ; réduction à 1100–1200 °C ; scorie = prills de Cu métallique +
        cuprite + spinelles + delafossite dans une matrice vitreuse. Les isotopes du
        plomb montrent que les fondeurs CONNAISSAIENT les propriétés des minerais —
        d'où le mensonge rendu visible C13 (natif vs sulfure, même tell vert C1).

    - id: D2
      axe: "RECHERCHE 3 — pourquoi les minerais SULFURÉS sont venus plus tard"
      techno: "Chalcopyrite (CuFeS₂) : grillage oxydant partiel ~590 °C (chasse le SO₂) PUIS fonte en matte ~1200 °C avec fluxage à la silice"
      source: "Rostoker et al. 'Direct reduction to copper metal by oxide-sulfide mineral interaction' (Archeomaterials 1989) ; 911Metallurgist 'Copper Smelting' ; Kawatra MTU 'Primary Metal Production' ; Wikipedia Chalcopyrite"
      telecharge: false
      applicable_a: "Substrate · le MENSONGE rendu visible #4 (sulfure réfractaire sous le tell vert)"
      gain_estime: "le même tell vert C1 (native_copper + chalcopyrite) → métallurgie OPPOSÉE : direct vs grillage-d'abord"
      action: COMBO_TODAY
      note: >
        Un sulfure ne se réduit PAS directement comme un oxyde : S et Fe verrouillent
        le cuivre dans une matte. Il faut d'abord GRILLER (oxydation partielle ~590 °C,
        un simple feu ouvert C7/C9 suffit) puis fondre en matte avec flux silice. C'est
        pourquoi les natifs/oxydes (fonte directe) ont précédé les sulfures de plusieurs
        millénaires. On encode : chalcopyrite crue → 0 métal (scorie seule) ; grillée →
        rendement modéré (0,35 Cu/kg au catalogue, blister).

    - id: D3
      axe: "RECHERCHE 3 — rendement de récupération & scorie (fonte primitive)"
      techno: "La fonte ne récupère JAMAIS tout le cuivre contenu ; la scorie en retient des prills ; un bain plus chaud + fluxage silice décante mieux le métal"
      source: "MDPI Metals 15(10):1070 (2025, flux haute-silice : Cu en scorie 10%→4,5%) ; MDPI Metals 11(6):992 (settling furnace, Cu dissous) ; Springer JOM 2012 (minimisation des pertes Cu en scorie ~0,55 %)"
      telecharge: false
      applicable_a: "Substrate · plafonds de rendement honnêtes (recovery_ceiling < 1.0) + bonus de surchauffe"
      gain_estime: "rendement honnête : base par classe + gain de surchauffe (saturant), plafonné <1.0 (la scorie garde toujours du Cu)"
      action: COMBO_TODAY
      note: >
        Même industriellement la scorie retient du Cu (0,55–10 %). Pour la fonte
        primitive : natif (déjà métal, fonte+coalescence) plafond ~0,95 ; oxyde
        ~0,80 ; sulfure grillé ~0,72. Le rendement monte avec la surchauffe au-dessus
        de 1085 °C (meilleure décantation), saturant sur ~200 °C.

    - id: D4
      axe: "RECHERCHE 1+2 — érosion GPU / world models 2026 (scan obligatoire)"
      techno: "Shallow-water hydraulic erosion GPU (Mei et al. 2007, toujours l'état de l'art applicatif) ; pas de papier 2026 changeant la donne ; world-model physical-consistency (Cosmos/Genie) requiert GPU/poids"
      source: "IEEE 4392715 (Fast Hydraulic Erosion GPU) ; arxiv 2210.14496 (tile-based erosion) ; daydreamsoft (GPU terrain erosion 2025) ; bshishov/UnityTerrainErosionGPU"
      telecharge: false
      applicable_a: "Substrate SYSTÈME A/B (eau/érosion) — couche GPU/Rust"
      gain_estime: "néant aujourd'hui (cargo-less)"
      action: BACKLOG_ROADMAP
      raison_si_rejet: "GPU/WGSL/Rust requis ; non compilable ici. Le Saint-Venant déjà décrit dans le SKILL reste la référence ; aucun breakthrough 2026 indexé n'oblige à recoder aujourd'hui."

  cve_stack:
    - "Aucune CVE critique sur le stack runtime Python (numpy/pytest) aujourd'hui ; les CVE Rust/Bevy/WGPU ne concernent pas le runtime cargo-less (Rust gelé Wave 42, ADR-0008)."

  paper_du_jour:
    titre: "On the origins of extractive metallurgy: new evidence from Europe (Belovode) + Direct reduction to copper metal by oxide-sulfide mineral interaction"
    url: "https://www.sciencedirect.com/science/article/abs/pii/S0305440310001986 ; https://os.pennds.org/archaeobib_filestore/pdf_articles/Archeomaterials/1989_3_Rostokeretal.pdf"
    technique: >
      Le seuil chalcolithique : un four à tirage forcé (C12) ≥1085 °C réduit/fond un
      minerai de cuivre en bouton de métal + scorie. La classe minéralogique gouverne
      la facilité : natif (déjà métal, fonte directe) ; oxyde/carbonate (réduction
      directe) ; sulfure (grillage ~590 °C OBLIGATOIRE puis matte). On encode
      copper_smelt_yield(ore, kg, peak, roasted) = teneur catalogue × rendement de classe
      (plafonné, + surchauffe). smelt_at consomme réellement le minerai (geo.mine_at).
    effort: "~4 h · complexité 3"

  world_model_updates:
    cosmos: "aucune nouveauté intégrable cargo-less"
    genie3: "aucune nouveauté intégrable cargo-less"
    autre: "aucun"

  combo_retenu:
    techno: "Fonte du cuivre chalcolithique (D1) × métallurgie des sulfures/grillage (D2) × rendement-scorie honnête (D3)"
    cible: "nouveau module engine/copper_smelting.py (Cap. C13) — la 1ʳᵉ transformation métallurgique, la fonte effective"
    gain: >
      RÉALISE la promesse différée de C12 (would_smelt_copper_here → fonte EFFECTIVE :
      smelt_at consomme le minerai via geo.mine_at et rend un bouton + scorie). RÉUTILISE
      le seuil fd.COPPER_SMELT_TEMP_C (C12) + le rendement par élément du catalogue
      minéral (yields_per_kg_ore["Cu"], category) — aucune teneur re-déclarée. Expose le
      MENSONGE #4 : même tell vert C1, métallurgie opposée (natif facile / chalcopyrite
      sulfurée → grillage d'abord). Effet 1+1>2 : fonte QUE là où four ≥1085 °C (C12) ET
      minerai (C1) coexistent.
    adr_requis: false   # transformation = lecture/acte dérivé du substrat ; ADR-0005/0008 inchangés
    garde_fou_D8: "par COMPOSITION (7ᵉ fois après C7/C8/C9/C10/C11/C12) — aucun nouveau tell, PY_TO_RUST reste 15, hors glob *_outcrop.py."
```

## Décision

**COMBO_TODAY = Cap. C13 `copper_smelting`** — la **1ʳᵉ transformation métallurgique**,
le **seuil chalcolithique**, le **premier métal**. Un four à tirage forcé (C12) ≥1085 °C
**fond effectivement** le minerai de cuivre que C1 montre (tache verte) : `smelt_at`
**consomme** le minerai (mutation géologique réelle) et **rend** un bouton de cuivre + de
la scorie, **exactement** comme l'oracle `smelt_cue_for_chunk` s'y engage. C'est la
**réalisation** de `would_smelt_copper_here` (C12), comme C12 réalisait la vitrification
de C9/C11.

Le **mensonge rendu visible #4** (après l'obsidienne C8, le kaolin C9) : C1 surface le
cuivre **natif** ET la **chalcopyrite** sous le **même tell vert** — mais le natif fond
directement (≥1085 °C) tandis que la chalcopyrite est un **sulfure réfractaire** qui
exige un **grillage** (~590 °C) avant de rendre du métal. Cru, il ne rend que de la
scorie : la leçon coûteuse, physiquement vraie. `best_smelt_site_near` l'enseigne (il
préfère le cuivre réellement récupérable).

Tout reste **émergent** : on n'apprend pas à l'agent à « fondre la pierre verte au
charbon ». On expose le **fait physique véridique** — un four soufflé assez chaud fait
suinter le métal de telle roche verte, et seulement après grillage pour telle autre — et
l'agent **découvre** la fonte en agissant. Creuset, tuyère, fluxage, moulage, martelage
restent émergents. La marche différée suivante, honnête : le **bronze** (Cu + étain —
`cassiterite` au catalogue, mais SANS tell de surface → exploration à l'aveugle, Cap.
C14) et le **bas-fourneau du fer** (`reaches_iron_bloomery_temp`, paroi réfractaire).

**Décisions BACKLOG/REJET** : érosion GPU / world models (D4) → BACKLOG_ROADMAP
(cargo-less + couche GPU/Rust, cf. `reference_env_no_cargo`, ADR-0008).

## Sources (veille du jour)

- Fonte chalcolithique : [ScienceDirect — Origins of extractive metallurgy (Belovode)](https://www.sciencedirect.com/science/article/abs/pii/S0305440310001986) · [Springer — Early Balkan Metallurgy 6200–3700 BC](https://link.springer.com/article/10.1007/s10963-021-09155-7) · [Rock&Gem — Malachite the first ore](https://www.rockngem.com/malachite-the-first-ore/)
- Sulfures / grillage : [Rostoker et al. 1989 (oxide-sulfide reduction, PDF)](https://os.pennds.org/archaeobib_filestore/pdf_articles/Archeomaterials/1989_3_Rostokeretal.pdf) · [911Metallurgist — Copper Smelting](https://www.911metallurgist.com/blog/copper-smelting/) · [Kawatra MTU — Primary Metal Production (PDF)](https://www.chem.mtu.edu/chem_eng/faculty/kawatra/CM2200_Primary_Metals.pdf) · [Wikipedia — Chalcopyrite](https://en.wikipedia.org/wiki/Chalcopyrite)
- Rendement / scorie : [MDPI Metals 15(10):1070 (2025, high-silica flux)](https://www.mdpi.com/2075-4701/15/10/1070) · [MDPI Metals 11(6):992 (settling furnace)](https://www.mdpi.com/2075-4701/11/6/992) · [Springer JOM 2012 (Cu losses in slag)](https://link.springer.com/article/10.1007/s11837-012-0454-6)
- Érosion GPU (scan, backlog) : [IEEE — Fast Hydraulic Erosion on GPU](https://ieeexplore.ieee.org/document/4392715/) · [arxiv 2210.14496](https://arxiv.org/pdf/2210.14496)
