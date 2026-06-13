# WORLD_VEILLE_REPORT — 2026-06-13 (Cap. C4 — affleurement de combustible)

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-13"
  duree_recherche: "~25 min"
  contexte: >
    2ᵉ action du jour (la 1ʳᵉ session a livré le garde-fou cross-langage
    géologie / ADR-0007 ce matin). Cible substrate : SYSTÈME C (Géologie 3D
    & ressources, branche ORGANIQUE) + SYSTÈME F (Découverte agent — chaîne
    « CHARBON → ÉNERGIE ») du prompt World Realism v2.0. Env = Python 3.14
    SEUL, aucun cargo/rustc (cf. memory reference_env_no_cargo) → toute piste
    Rust/GPU est BACKLOG (CI = vérité), le code du jour reste Python pur.

  decouvertes:
    - id: D1
      techno: "Rang des combustibles fossiles & pouvoir calorifique (tourbe < lignite < bitumineux < anthracite)"
      source: "https://en.wikipedia.org/wiki/Lignite ; https://www.britannica.com/science/lignite ; https://cfdflowengineering.com/calorific-value-of-fuel-calculations/"
      telecharge: false
      applicable_a: "engine.combustible_outcrop — grade calorifique intrinsèque par matériau organique"
      gain_estime: "réalisme : grade énergétique physiquement fondé (rang houiller) au lieu d'un nombre arbitraire ; débloque la chaîne feu→four→métallurgie"
      action: "COMBO_TODAY"
      raison_si_rejet: ""
      chiffres_retenus:
        - "Tourbe (peat)      : rang le plus bas ; O/H très élevés, C fixe et PCI faibles ; humidité native > 75 %"
        - "Lignite/brun       : 25–35 % C ; PCI ~10 000–20 000 kJ/kg (~17 MJ/kg) ; humidité native jusqu'à 70 %"
        - "Bitumineux (coal)  : PCI nettement supérieur ; rang houiller mûr"
        - "Anthracite         : PCI le plus haut de la série (réf. haut de grade)"
        - "Bois (réf.)        : ~15–18 MJ/kg sec → un combustible 'noir' sec dépasse vite le bois"

    - id: D2
      techno: "Tourbière : formation paludique anoxique & contrôle par l'humidité (acrotelme/catotelme)"
      source: "https://microbewiki.kenyon.edu/index.php/Peat_Bogs ; https://www.nature.com/articles/srep28758 ; https://iere.org/what-is-a-peat-bog/"
      telecharge: false
      applicable_a: "engine.combustible_outcrop — porte d'humidité (moisture-of-extinction) + vérité 'bog = surface gorgée d'eau'"
      gain_estime: "réalisme : un combustible gorgé d'eau ne brûle pas tant qu'il n'est pas coupé & séché → boucle émergente coupe→sèche→brûle (vérité physique, pas script)"
      action: "COMBO_TODAY"
      raison_si_rejet: ""
      chiffres_retenus:
        - "Bog = milieu gorgé d'eau, acide, anoxique : NPP > décomposition → accumulation de tourbe"
        - "Acrotelme (oxique, ~2–4 cm) vs catotelme (anoxique, gorgé) : décompo. ÷ 100 à 1000 en profondeur"
        - "Tourbières = 3 % des terres mais ~30 % du carbone des sols (~550 Gt C)"
        - "Le séchage d'un charbon brun ramène son PCI à l'équivalent charbon noir (combustion spontanée ↓)"

    - id: D3
      techno: "NVIDIA Cosmos 3 — world foundation model omnimodal (physical consistency)"
      source: "https://research.nvidia.com/labs/cosmos-lab/cosmos3/technical-report.pdf ; https://nvidianews.nvidia.com/news/nvidia-launches-cosmos-3-the-open-frontier-foundation-model-for-physical-ai (lancé 2026-06-01)"
      telecharge: false
      applicable_a: "SYSTÈME G — world-model NIVEAU 2 (cohérence macro régionale)"
      gain_estime: "génération d'état cohérent (text/image/vidéo/action) avec sous-métrique 'physical plausibility'"
      action: "BACKLOG_ROADMAP"
      raison_si_rejet: >
        Pas de runtime ML lourd ni GPU dans l'env (Python pur). Intégrer un
        world-model omnimodal est un chantier macro hors-périmètre, et contraire
        à la règle stone-age (pas de solveur/oracle injecté). Noté pour la
        roadmap NIVEAU 2 du SYSTÈME G.

    - id: D4
      techno: "Physical consistency in Lightweight World Models"
      source: "https://arxiv.org/pdf/2509.12437"
      telecharge: false
      applicable_a: "SYSTÈME G — variante légère du world-model macro (sans GPU datacenter)"
      gain_estime: "cohérence physique à coût réduit — plus réaliste pour une intégration future locale"
      action: "BACKLOG_ROADMAP"
      raison_si_rejet: "Même raison que D3 (pas de runtime ML ici) ; meilleure piste 'légère' à réévaluer quand un câblage Rust/GPU existera."

    - id: D5
      techno: "Érosion hydraulique GPU (Unity/CUDA/Godot ; pas de WGSL dominant nouveau)"
      source: "https://github.com/bshishov/UnityTerrainErosionGPU ; https://github.com/GuilBlack/Erosion ; https://huw-man.github.io/Interactive-Erosion-Simulator-on-GPU/"
      telecharge: false
      applicable_a: "SYSTÈME B — érosion"
      gain_estime: "n/a aujourd'hui"
      action: "REJETÉ"
      raison_si_rejet: "Aucune implémentation WGSL/WGPU nouvelle dépassant l'existant ; et pas de GPU/cargo ici. Le substrat Python a déjà l'érosion d'Exner (Wave 57) côté graphe D8."

  cve_stack:
    - "aucune CVE critique nouvelle aujourd'hui (stack Python pur ; alerte BadHost CVE-2026-48710 déjà traitée veille 2026-06-03)"

  paper_du_jour:
    titre: "Rang houiller & contrôle de l'humidité sur la combustion (synthèse Britannica/KGS lignite + microbiologie des tourbières)"
    url: "https://www.britannica.com/science/lignite + https://microbewiki.kenyon.edu/index.php/Peat_Bogs"
    technique: >
      Le rang houiller (tourbe→lignite→bitumineux→anthracite) ordonne un grade
      calorifique intrinsèque, ET l'humidité native (jusqu'à >70 %) impose un
      seuil de combustibilité (moisture-of-extinction, cf. Rothermel du prompt
      SYSTÈME E). Un combustible 'noir mat' n'allume pas un feu durable tant
      qu'il est gorgé d'eau : il faut le COUPER puis le SÉCHER. C'est une vérité
      physique parfaite pour une chaîne de découverte émergente.
    effort: "~3 h · complexité 2/5"

  world_model_updates:
    cosmos: "Cosmos 3 lancé 2026-06-01 (omnimodal, physical consistency) → BACKLOG NIVEAU 2 (pas de GPU ici)"
    genie3: "rival texte→environnement ; aucune nouveauté exploitable hors GPU aujourd'hui"
    autre: "arxiv 2509.12437 (lightweight world models, cohérence physique) → BACKLOG"

  combo_retenu:
    techno: "D1 (rang houiller / grade calorifique) × D2 (porte d'humidité tourbière)"
    cible: "engine.combustible_outcrop (NOUVELLE capacité C4)"
    gain: >
      Comble une MUETTE totale : toute la branche ORGANIQUE de la géologie
      (peat / coal / oil_shale, déjà semée dans `ore_mix` par `engine.geology`)
      est invisible — aucun signal ne dit à un agent où trouver « la roche/terre
      qui brûle ». C4 expose le signal véridique (exposition noire-mate
      carbonée + son humidité) dérivé de truths indépendantes (couche organique
      peu profonde dans `chunk_geology`, champ `chunk.water`, biome). Invariant
      « le monde ne ment jamais ». Effet 1+1>2 : la porte d'humidité (D2) relie
      la géologie organique (SYSTÈME C) à l'hydrologie de surface (SYSTÈME A) →
      boucle émergente coupe→sèche→brûle, puis grade calorifique → seuil de
      fusion (chaîne feu→four→métallurgie du SYSTÈME F).
    couche: "Substrate (Genesis-L1 Earth-Seed)"
    adr: "aucun nouvel ADR — réutilise ADR-0005 (lecture dérivée du substrat, comme C1/C2/C3)"
    estimation: "~3 h"
```

## Décision

**Construire Cap. C4 — `engine.combustible_outcrop`** : la découverte émergente
du **combustible** (tourbe / charbon / schiste bitumineux). C'est le maillon
qui débloque la chaîne énergétique du SYSTÈME F (« roche noire mate qui brûle
longtemps → révolution énergie → four → métallurgie ») et le pendant
géologique-organique de C1 (minerai métallique), C2 (pierre taillable) et C3
(eau potable).

**Pourquoi maintenant** : le substrat porte déjà la vérité (les minéraux
`peat`/`coal`/`oil_shale` de la catégorie `ORGANIC` sont semés dans l'`ore_mix`
des couches par `engine.geology`), mais **aucun signal de surface** ne les
trahit — exactement la muette que C1/C2 ont comblée pour le métal et la pierre.
Et le garde-fou de ce matin (ADR-0007) **exige** que toute nouvelle capacité
**enrichisse `PY_TO_RUST`** : C4 le fait en surfaçant enfin `coal` (déjà mappé,
jamais exposé) et en ajoutant `peat` — avec un **verrou byte-exact** du tell
charbon `(20,20,20)` ⇔ `Mineral::Coal::surface_color()` du crate Rust, miroir
du tell cuivre/malachite `(80,140,70)`.

**Émergence absolue** : on rend l'exposition carbonée *perceptible* (noir mat,
terre spongieuse gorgée d'eau d'une tourbière, veine sombre d'une saignée) et
son **humidité** perceptible. On ne scripte JAMAIS « ceci brûle » — l'agent
apprend la corrélation noir-mat + sec ↔ feu durable en agissant. Aucun hook
`sim.step`, coût tick nul → conforme au moratoire observateurs.

**Effet multiplicateur (combo D1×D2)** : la porte d'humidité fait que la même
tourbière qui *émet* un indice (on VOIT la tourbe noire) n'est **pas brûlable
maintenant** tant qu'elle est gorgée d'eau → boucle émergente *couper → sécher →
brûler*, physiquement vraie (cf. acrotelme/catotelme, séchage = PCI ↑). Le grade
calorifique pilote ensuite un seuil `smelting_grade` (charbon oui, tourbe non) →
le signal devient un *activateur de technologie* émergent (quel combustible
atteindra un jour la température de fusion du métal).

**Gap honnête (audit)** : (1) C4 est une **perception** — on n'altère ni le feu
(`engine.fire`/Rothermel) ni la combustion réelle ; on expose le signal, l'agent
agit. (2) Ne ferme **aucun** item Rust Phase A/B (A3/A4/A5/B1–B8 restent ouverts,
`cargo` absent → CI = vérité) ; c'est une capacité du runtime Python live. (3) La
diagenèse tourbe→charbon (houillification par enfouissement/T°) n'est pas
simulée : les rangs sont des matériaux distincts du catalogue, pas un continuum
temporel.

Sources :
[Lignite (Wikipedia)](https://en.wikipedia.org/wiki/Lignite) ·
[Lignite (Britannica)](https://www.britannica.com/science/lignite) ·
[Calorific value of coal & wood (CFD Flow Eng.)](https://cfdflowengineering.com/calorific-value-of-fuel-calculations/) ·
[Peat bogs (MicrobeWiki)](https://microbewiki.kenyon.edu/index.php/Peat_Bogs) ·
[Peatland carbon sink (Nature Sci. Reports)](https://www.nature.com/articles/srep28758) ·
[NVIDIA Cosmos 3 (2026-06-01)](https://nvidianews.nvidia.com/news/nvidia-launches-cosmos-3-the-open-frontier-foundation-model-for-physical-ai) ·
[Lightweight world models (arXiv 2509.12437)](https://arxiv.org/pdf/2509.12437)
