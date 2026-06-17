# WORLD_VEILLE_REPORT — 2026-06-17 (run #2, `kiln_draft` / Cap. C11)

> Étape 0 obligatoire **avant tout code** (Morning Routine v3.0 — World Realism
> System v2.0). Run automatique, *user absent*. Veille → Combo → Décision → Code →
> Push. Le run #1 du jour a livré C10 `lime_burning` (commit `4f113d3`) ; ce run #2
> enchaîne sur la suite **explicitement signposted par C9 ET C10** : le **four**.

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-17"
  duree_recherche: "~25 min"
  contexte_env: "Python 3.14 SEUL — pas de cargo/rustc (cf. reference_env_no_cargo)."
  contrainte: >
    Toute découverte GPU/Rust/Bevy/WGSL est, par construction, NON intégrable
    aujourd'hui (pas de compilateur Rust ici). Elle est donc classée BACKLOG_ROADMAP,
    jamais COMBO_TODAY. Le combo du jour DOIT être Python-pur, déterministe, cargo-less.
```

## Découvertes

```yaml
  decouvertes:
    - id: D1
      techno: "Archéométrie de la pyrotechnologie — four à tirage vs feu ouvert"
      source: "academia.edu Wood-firing Experiments (Updraft Kiln); ScienceDirect S016913171000308X (bonfire temp); Wikipedia Pottery"
      telecharge: false
      applicable_a: "Substrate · combustion thermodynamique de l'ENCEINTE (Cap. C11)"
      gain_estime: "réalisme +1 phénomène (l'enceinte élève la température de pointe) ; débloque 2 transformations différées (C9 vitrif. / C10 mortier)"
      action: COMBO_TODAY
      note: >
        Feu ouvert / feu de surface (bonfire, pit) : ~600–900 °C, montée rapide,
        court séjour — CONFIRME la SSOT C9 (OPEN_FIRE_MAX_C = 850 °C). Four à tirage
        (updraft, enceinte + tirage + long séjour) : ~1000–1100 °C — LE régime qui
        vitrifie la poterie et cuit le calcaire pur à cœur (mortier liant). La
        différence n'est PAS arbitraire : enceinte (réduit les pertes) + tirage
        (apport O₂, intensité de combustion) → pic plus haut, soutenu plus longtemps.

    - id: D2
      techno: "Argile réfractaire (fire-clay / kaolin) comme garnissage de four"
      source: "Wikipedia Fire clay ; VITCAS Refractory Fire Bricks ; thermalprocessing.com Insulating firebricks ; NCBI PMC6864342 (kaolinite thermal conductivity)"
      telecharge: false
      applicable_a: "Substrate · qualité de paroi du four (lecture C5 clay_outcrop)"
      gain_estime: "ferme l'arc du 'mensonge du kaolin' (C9) — inversion de l'inversion"
      action: COMBO_TODAY
      note: >
        La fire-clay (kaolin/aluminosilicate) tient 1515–1775 °C et sert de
        garnissage / brique isolante de four. Plus l'alumine (kaolin) est haute,
        plus la température de service est élevée. CONSÉQUENCE physique majeure : le
        kaolin — la 'mauvaise' argile de C9 (réfractaire, SOUS-CUITE en poterie au
        feu ouvert) — est la MEILLEURE argile de PAROI. C'est elle qui permet le
        four assez chaud pour, enfin, cuire le kaolin à cœur. Le monde ne ment pas :
        la matière piégée comme objet est précieuse comme outil.

    - id: D3
      techno: "Tirage forcé (soufflet) + charbon de bois → régime métallurgique"
      source: "Wikipedia Bloomery ; EXARC issue-2020-2 (bloomery furnaces) ; Wealden Iron Research Group"
      telecharge: false
      applicable_a: "Substrate · le PALIER différé au-delà du four à tirage naturel (C12+)"
      gain_estime: "garde le motif 'potentiel non réalisé qui pointe vers l'avant'"
      action: BACKLOG_ROADMAP
      note: >
        Charbon de bois ~1100 °C (vs bois ~600 °C) ; bas-fourneau à tirage forcé
        (soufflets/tuyère) 1100–1300 °C — vitrification complète de la porcelaine et
        réduction du fer (bloomery). C11 (tirage NATUREL) ne va pas si haut ; le
        tirage FORCÉ reste donc la prochaine marche différée
        (`vitrifies_if_forced_draught`) — exactement comme C9/C10 différaient le four.

    - id: D4
      techno: "NVIDIA Cosmos 3 (omnimodal world model, physical AI) — 2026-06-01"
      source: "research.nvidia.com/labs/cosmos-lab/cosmos3/technical-report.pdf ; developer.nvidia.com/blog ; introl.com World Models Race 2026"
      telecharge: false
      applicable_a: "Substrate SYSTÈME G (cohérence macro Niveau 2)"
      gain_estime: "cohérence régionale sans calcul exact — mais GPU/poids requis"
      action: BACKLOG_ROADMAP
      raison_si_rejet: "cargo-less + pas de GPU/poids ici ; intégration = travail Phase A/B (ADR-0008), pas cargo-less aujourd'hui."

    - id: D5
      techno: "arXiv 2509.12437 — Enhancing Physical Consistency in Lightweight World Models"
      source: "arxiv.org/pdf/2509.12437"
      telecharge: false
      applicable_a: "Substrate SYSTÈME G (prior physique léger)"
      gain_estime: "world model léger physiquement cohérent (piste future)"
      action: BACKLOG_ROADMAP
      raison_si_rejet: "papier théorique ; pas d'implémentation cargo-less prête ; à relire pour roadmap."

  cve_stack:
    - "aucune CVE critique sur le stack runtime Python (numpy/pytest) aujourd'hui."

  paper_du_jour:
    titre: "Wood-firing Experiments: Testing the Efficiency of an Updraft Kiln + bonfire firing temperatures"
    url: "https://www.academia.edu/44131018 ; https://www.sciencedirect.com/science/article/abs/pii/S016913171000308X"
    technique: >
      L'enceinte d'un four à tirage élève la température de pointe au-dessus du
      plafond d'un feu nu (≈850 °C) vers ~1000–1100 °C ; la qualité de paroi
      (argile réfractaire = kaolin) plafonne la température atteignable sans que la
      paroi s'effondre. On encode `kiln_peak_temp_c(fine_fuel, wall_refractory)`.
    effort: "~4 h · complexité 3"

  world_model_updates:
    cosmos: "Cosmos 3 (2026-06-01) — omnimodal physical-AI ; BACKLOG (GPU/Rust)."
    genie3: "Genie 3 (août 2025) — physique implicite émergente ; BACKLOG."
    autre: "arXiv 2509.12437 lightweight physical-consistency world model ; BACKLOG."

  combo_retenu:
    techno: "Thermodynamique de l'enceinte (D1) × argile réfractaire de paroi (D2)"
    cible: "nouveau module engine/kiln_draft.py (Cap. C11) — l'apparatus 'four à tirage'"
    gain: >
      RÉUTILISE VERBATIM la SSOT C9 `open_fire_peak_temp_c` (le feu nu = base), AJOUTE
      le gain d'enceinte plafonné par la réfractarité de paroi (C5), et RECOMPOSE
      C9/C10 à la nouvelle pointe pour RÉALISER le mortier liant (C10 différé) et
      rendre le kaolin SAIN (C9 amélioré). Effet 1+1>2 : le four ne se fait que là où
      argile-de-paroi (C5) ET feu (C7) coexistent, et il débloque 2 transformations.
    adr_requis: false   # lecture dérivée du substrat (apparatus), pas de frontière nouvelle ; ADR-0005/0008 inchangés
    garde_fou_D8: "par COMPOSITION (5ᵉ fois après C7/C8/C9/C10) — aucun nouveau tell, PY_TO_RUST reste 15, hors glob *_outcrop.py."
```

## Décision

**COMBO_TODAY = Cap. C11 `kiln_draft`** — l'apparatus *four à tirage* : une enceinte
d'argile (parois, C5) autour d'un feu (C7) atteint une température de pointe **plus
haute** qu'un feu ouvert, **calculée** (D1) et **plafonnée par la réfractarité de la
paroi** (D2). Le four **réalise** le potentiel différé de C10 (`would_mortar_if_kiln_fired`
→ mortier liant pour le calcaire pur) et **rend sain** le kaolin de C9 (sous-cuit au
feu ouvert → corps sain en four réfractaire). Il **ouvre** une nouvelle marche
différée honnête : le **tirage forcé** (soufflet + charbon, D3) pour la
vitrification complète et la métallurgie (`vitrifies_if_forced_draught`).

Tout reste **émergent** : on n'apprend pas à l'agent à « construire un four ». On
expose le **fait physique véridique** — entourer un feu d'argile réfractaire et lui
donner un tirage le rend plus chaud — et l'agent **découvre** le four en agissant.
La forme du four, la cheminée, le tirage, l'empilement restent émergents.

**Décisions BACKLOG/REJET** : toute techno GPU/Rust (Cosmos 3, world models légers,
érosion GPU, crates Bevy/WGPU) → BACKLOG_ROADMAP (cargo-less, cf. `reference_env_no_cargo`).
