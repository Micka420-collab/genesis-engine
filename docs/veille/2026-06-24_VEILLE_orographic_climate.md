# WORLD_VEILLE_REPORT — 2026-06-24 (orographic climate coupling)

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-24"
  duree_recherche: "~20 min"

  decouvertes:
    - id: D1
      techno: "Environmental lapse rate as the elevation→temperature operator"
      source: "https://en.wikipedia.org/wiki/Lapse_rate ; observed basin values 0.45–0.8 °C/100 m (Nature Sci. Reports s41598-022-18047-5, 2022)"
      telecharge: false
      applicable_a: "engine.climate_biome — chunk-path climate (D11)"
      gain_estime: "réalisme: la météo chunk RÉPOND enfin au relief vivant ; +1 phénomène physique réel sur le chemin agent"
      action: COMBO_TODAY
      raison_si_rejet: ""
    - id: D2
      techno: "Coupled tectonic-uplift / erosion / climate / vegetation feedback (negative climate-erosion feedback ; orographic precip ; biome migration)"
      source: "WRF-Landlab (ScienceDirect S0098300420306038) ; HESS 25/2459/2021 topo-climate coupling ; Oasis: Real-Time Hydraulic & Aeolian Erosion w/ Dynamic Vegetation (2025)"
      telecharge: false
      applicable_a: "valide la DIRECTION : uplift→refroidit→migration biome, érosion→réchauffe"
      gain_estime: "cohérence causale : couple deux systèmes jusqu'ici disjoints (autonomous_world ↔ chunk path)"
      action: COMBO_TODAY
      raison_si_rejet: ""
    - id: D3
      techno: "Elevation-dependent climate change in mountain environments"
      source: "Nature Reviews Earth & Environment s43017-025-00740-4 (2025)"
      telecharge: false
      applicable_a: "confirme que le signal température est spatialement variable (per-chunk), pas un scalaire global"
      gain_estime: "justifie le terme orographique PAR CHUNK plutôt que l'anomalie globale scalaire existante"
      action: COMBO_TODAY
      raison_si_rejet: ""

  cve_stack:
    - "aucune CVE critique aujourd'hui (numpy / PCG64 clean)"

  paper_du_jour:
    titre: "Oasis: A Real-Time Hydraulic and Aeolian Erosion Simulation with Dynamic Vegetation (2025)"
    url: "https://www.researchgate.net/publication/389578619"
    technique: "boucle temps-réel érosion↔végétation bidirectionnelle — confirme que le relief vivant doit piloter la végétation. Ici, version cargo-less : le relief pilote la MIGRATION de biome via le lapse rate."
    effort: "intégré aujourd'hui (le terme lapse, déjà SSOT earth_laws.LAPSE_K_PER_M) · complexité 2/5"

  world_model_updates:
    cosmos: "aucune nouveauté applicable (GPU/Rust gelé ADR-0008, cargo-less)"
    genie3: "aucune nouveauté applicable"
    autre: "GraphCast/GenCast météo neuronale — backlog (gated GPU/poids ; hors env Python pur)"

  combo_retenu:
    techno: "lapse-rate orographic coupling (D1) × live elevation_m déjà muté par plate_tectonics_live/novel_operators (D2)"
    cible: "engine.climate_biome — source `macro` (placeholder `return 0.0`) + nouveau terme orographique par chunk"
    gain: "ferme la moitié chunk-path de D11 : le relief vivant atteint enfin les biomes que l'agent voit ; anomalie = -6.5 K/km exactement, 0 sur monde statique (back-compat)"
    adr_requis: false   # additif, opt-out, lecture-seule du macro ; pas de décision architecturale nouvelle (cohérent ADR-0008)
```

## Synthèse 1 ligne

La littérature 2022–2025 (lapse rate observé, couplage tectonique↔érosion↔climat↔végétation,
climat dépendant de l'altitude) valide d'utiliser le **lapse rate environnemental** (SSOT
`earth_laws.LAPSE_K_PER_M`, déjà cuit dans la température macro de base par `world_genesis`)
comme l'opérateur qui transforme la **dérive d'élévation vivante** (déjà produite par
`plate_tectonics_live`/`novel_operators` dans la boucle `autonomous_world`) en une **anomalie
de température par chunk** — refermant la moitié chemin-agent de **D11** sans cargo, sans RNG,
sans mensonge (lecture-seule du macro, identiquement 0 sur monde statique).
