# WORLD_VEILLE_REPORT — 2026-06-12 (Cap. C3 — potabilité de l'eau)

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-12"
  duree_recherche: "~20 min"
  contexte: >
    2ᵉ veille du jour (la 1ʳᵉ a porté Cap. C2 lithic_outcrop ce matin).
    Cible substrate : SYSTÈME A (Eau & Hydrologie) + SYSTÈME F (Découverte
    agent) du prompt World Realism v2.0. Env = Python 3.14 SEUL, aucun
    cargo/rustc (cf. memory reference_env_no_cargo) → toute piste Rust/GPU
    est BACKLOG (CI = vérité), le code du jour reste Python pur.

  decouvertes:
    - id: D1
      techno: "Seuils de salinité potable (WHO/EPA TDS, classification eau)"
      source: "https://www.who.int/ (Guidelines for drinking-water quality, TDS) ; EPA secondary MCL 500 mg/L ; classification océanographique fresh/brackish/saline"
      telecharge: false
      applicable_a: "engine.water_potability — calibration des bandes de salinité"
      gain_estime: "réalisme : potabilité physiquement fondée (ppt mesurables) au lieu d'un seuil arbitraire"
      action: "COMBO_TODAY"
      raison_si_rejet: ""
      chiffres_retenus:
        - "Eau douce (fresh)      : < 0.5 ppt          → potable, palatable"
        - "EPA secondaire (TDS)   : < 500 mg/L = 0.5 ppt (limite palatabilité 'bonne')"
        - "WHO palatabilité       : bonne < 600 mg/L ; 'increasingly unpalatable' > 1000 mg/L (1 ppt)"
        - "Eau saumâtre (brackish): 0.5 – 30 ppt"
        - "Non potable régulier   : > ~5 ppt (5000 ppm de sel) → déshydratation nette"
        - "Eau de mer             : ~35 ppt (35 000 mg/L TDS) — létale à la consommation"
        - "Saumure évaporitique   : 35 – ~300 ppt (sources salées sur halite)"

    - id: D2
      techno: "NeuralGCM (Google) — modèle de circulation différentiable hybride"
      source: "https://www.science.org/doi/10.1126/sciadv.adv6891 ; arxiv 2311.07222"
      telecharge: false
      applicable_a: "SYSTÈME D/G — météo & world-model macro (précipitation)"
      gain_estime: "précipitation supérieure à ERA5 / GCM classiques ; pourrait piloter le forçage pluie du cycle de l'eau"
      action: "BACKLOG_ROADMAP"
      raison_si_rejet: >
        Pas de runtime ML lourd ni GPU dans l'env ; et le module du jour est
        une CAPACITÉ de perception, pas un solveur — l'intégration d'un GCM
        neuronal est un chantier macro hors-périmètre (et contraire à la règle
        stone-age : pas de solveur analytique injecté).

    - id: D3
      techno: "Modèles hydrologiques différentiables physics-embedded (δHBV-globe1.0-hydroDL)"
      source: "https://gmd.copernicus.org/articles/17/7181/2024/ ; https://www.nature.com/articles/s41467-025-64367-1 ; arxiv 2504.10707"
      telecharge: false
      applicable_a: "SYSTÈME A — recharge de nappe / baseflow / ET émergents (3753 bassins mondiaux)"
      gain_estime: "diagnostic de variables non-entraînées : recharge groundwater, baseflow, snowmelt, ET"
      action: "BACKLOG_ROADMAP"
      raison_si_rejet: >
        Excellente piste pour une future couche groundwater (la nappe
        phréatique du prompt SYSTÈME A n'est PAS encore modélisée dans le
        substrat Python — l'eau y est un champ de surface `chunk.water`).
        Aujourd'hui on ne grève pas le scope : on perçoit la POTABILITÉ de
        l'eau de surface existante. La nappe est notée en gap honnête.

  cve_stack:
    - "aucune CVE critique nouvelle aujourd'hui (alerte BadHost CVE-2026-48710 déjà traitée veille 2026-06-03 ; stack Python pur ici)"

  paper_du_jour:
    titre: "Classification océanographique de la salinité & limites de potabilité (synthèse WHO/EPA + océanographie)"
    url: "https://www.science.org/doi/10.1126/sciadv.adv6891 (contexte cycle de l'eau) + guidelines WHO/EPA TDS"
    technique: >
      Bandes de salinité fresh/brackish/saline et seuil physiologique de
      déshydratation nette (~5 ppt) → calibrent directement la potabilité
      émergente. Constante eau de mer 35 ppt = celle du tableau du prompt
      (densité 1025 kg/m³, salinité 35 ppt).
    effort: "~3 h · complexité 2/5"

  world_model_updates:
    cosmos: "aucune nouveauté exploitable aujourd'hui"
    genie3: "aucune nouveauté exploitable aujourd'hui"
    autre: "NeuralGCM precipitation (Science Adv. 2026) + δHBV-globe hydro différentiable → BACKLOG nappe phréatique"

  combo_retenu:
    techno: "D1 — bandes de salinité potable physiquement fondées"
    cible: "engine.water_potability (NOUVELLE capacité C3)"
    gain: >
      Comble une MUETTE physiquement fausse : `physiology.DRINK` réduit la soif
      pour N'IMPORTE QUELLE cellule d'eau, y compris l'eau de mer — le monde ne
      dit jamais à un agent quelle eau le sustente vs laquelle le tue. C3 expose
      le signal véridique (goût / croûte de sel / rivage stérile vs verdoyant)
      dérivé de truths indépendantes (biome OCEAN, halite peu profonde en
      géologie, champ `chunk.water`). Invariant « le monde ne ment jamais ».
    couche: "Substrate (Genesis-L1 Earth-Seed)"
    adr: "aucun nouvel ADR — réutilise ADR-0005 (lecture dérivée du substrat, comme C1/C2)"
    estimation: "~3 h"
```

## Décision

**Construire Cap. C3 — `engine.water_potability`** : la découverte émergente de
la **potabilité** de l'eau de surface. C'est le pendant hydrologique de C1
(minerai) et C2 (pierre taillable), et la ressource la plus fondamentale de
toutes pour la survie d'un agent (on meurt de soif en ~3 jours, avant la faim,
avant l'outil).

**Pourquoi maintenant** : la 2ᵉ veille a confirmé que le substrat porte déjà
toutes les vérités indépendantes nécessaires (biome `OCEAN`, halite en géologie,
champ `chunk.water`), et que `physiology._patch_drink_and_eat` consomme l'eau
**sans aucune notion de salinité** — un agent peut « boire » de l'eau de mer et
être hydraté. C'est une muette à la fois fondamentale ET physiquement fausse.

**Émergence absolue** : on rend la salinité *perceptible* (goût salé, croûte
d'efflorescence blanche, rivage stérile). On ne scripte JAMAIS « ne bois pas
l'eau de mer » — l'agent apprend la corrélation goût↔hydratation en agissant.
Aucun hook `sim.step`, coût tick nul → conforme au moratoire observateurs.

**Gap honnête (audit)** : (1) la **nappe phréatique** (groundwater / Darcy du
prompt SYSTÈME A) n'est pas modélisée — l'eau reste un champ de surface ; D3 est
la piste future. (2) On **n'altère pas** `physiology.DRINK` pour pénaliser l'eau
salée (changement comportemental à risque, hors moratoire) : C3 livre la
*perception*, pas la sanction. Ne ferme aucun item Rust Phase A/B.

Sources : [WHO/EPA salinité potable (EWASH)](https://www.ewash.org/what-is-the-maximum-salinity-you-can-drink/) ·
[Brackish vs fresh (Frizzlife)](https://www.frizzlife.com/blogs/guide/what-is-a-brackish-water-fresh-water-vs-brackish-water) ·
[NeuralGCM precipitation (Science Advances)](https://www.science.org/doi/10.1126/sciadv.adv6891) ·
[δHBV-globe hydro différentiable (GMD)](https://gmd.copernicus.org/articles/17/7181/2024/) ·
[physics-embedded hydrology (Nature Comms)](https://www.nature.com/articles/s41467-025-64367-1)
