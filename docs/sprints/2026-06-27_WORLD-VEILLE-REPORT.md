# WORLD_VEILLE_REPORT — 2026-06-27 (Wave 65)

> Substrate layer · scheduled task `genesis-engine--world-realism-system-v20`.
> Veille **first**, then combo, then code, then push. Internet libre.

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-27"
  duree_recherche: "~20 min (ciblée : précipitation orographique)"

  contexte_moteur:
    # L'audit J+13 (AUDIT-DELTA-2026-06-23) classe le substrat A–G en R0 (D11) :
    # figé sur le chemin agent/chunk. Deux moitiés de D11 déjà fermées :
    #   - température orographique (climate_biome, 2026-06-24, p154)
    #   - débit des rivières (river_discharge, 2026-06-25, p156)
    # Backlog #7 nommait explicitement la moitié restante : "recoupler
    # l'atmosphère -> temp_c/precip_mm". La moitié temp_c est faite ; il reste
    # precip_mm. river_discharge.py:37 le nomme aussi comme backlog explicite
    # ("the windward/leeward orographic precip enhancement remains backlog").

  decouvertes:
    - id: D1
      techno: "Smith & Barstad (2004) — Linear Theory of Orographic Precipitation"
      source: "https://journals.ametsoc.org/view/journals/atsc/61/12/1520-0469_2004_061_1377_altoop_2.0.co_2.xml"
      telecharge: false
      applicable_a: "climate_biome — couplage précipitation live"
      gain_estime: "réalisme : modèle de référence (FFT, fonction de transfert)"
      action: "BACKLOG_ROADMAP"
      raison_si_rejet: >
        Le modèle worldgen existant (_orographic_precipitation) EST déjà de la
        famille upslope+advection que Smith-Barstad généralise (Smith 2003
        advection + upslope model). La variante FFT Smith-Barstad
        REMPLACERAIT le modèle worldgen (plus lourde, casse la réutilisation
        SSOT et la garantie « monde statique bit-identique »). Déféré : pas un
        gain incrémental cargo-less aujourd'hui.

    - id: D2
      techno: "QGIS LinearTheoryOrographicPrecipitation (impl. Smith-Barstad 2004)"
      source: "https://plugins.qgis.org/plugins/LinearTheoryOrographicPrecipitation/"
      telecharge: false
      applicable_a: "référence d'implémentation FFT"
      gain_estime: "validation : montre que la LT est implémentable proprement"
      action: "BACKLOG_ROADMAP"
      raison_si_rejet: "Même raison que D1 — remplacement, pas extension."

    - id: D3
      techno: "Lapse rate environnemental ~6.5 °C/1000 m + lift windward / Foehn lee"
      source: "https://earthweb.ess.washington.edu/roe/GerardWeb/Publications_files/MinderRoe_OrogPrecEncyc.pdf ; https://www.eoas.ubc.ca/courses/atsc113/snow/met_concepts/06-met_concepts/06e-orographic-uplift-lee-shadowing/"
      telecharge: false
      applicable_a: "confirme la physique du couplage retenu"
      gain_estime: "0 (validation) — confirme LAPSE_K_PER_M=0.0065 déjà en place"
      action: "COMBO_TODAY"
      raison_si_rejet: ""

  cve_stack:
    - "aucune CVE critique aujourd'hui (env Python pur, pas de nouvelle dep)"

  paper_du_jour:
    titre: "Smith & Barstad 2004 — A Linear Theory of Orographic Precipitation (J. Atmos. Sci. 61)"
    url: "https://ui.adsabs.harvard.edu/abs/2004JAtS...61.1377S/abstract"
    technique: >
      Air humide forcé à monter au vent (upslope) -> condensation -> pluie ;
      advection de l'eau condensée sous le vent -> évaporation descendante
      (Foehn) -> rain shadow. Le modèle worldgen Genesis est la version
      itérative upslope+advection de cette famille.
    effort: "réutilisation directe du modèle worldgen : 0 h de nouveau modèle"

  world_model_updates:
    cosmos: "aucune nouveauté applicable (gated, ADR-0008 cargo-less)"
    genie3: "aucune nouveauté applicable"
    autre: "aucun — la cohérence macro est déjà fournie par le worldgen déterministe"

  combo_retenu:
    techno: "Modèle orographique worldgen (_orographic_precipitation) — SSOT"
    cible: "engine.climate_biome — proxy de précipitation par chunk"
    gain: >
      precip_mm devient VIVANT : la précipitation par chunk suit le relief vif
      (gain au vent + rain shadow sous le vent). Ferme la moitié precip de D11
      backlog #7. Propage en aval -> échelle dry/wet des biomes (désertif. lee)
      et (futur) river_discharge qui gèle encore la précip à sa baseline.
    couche: "Substrate"
    adr: false   # pas de décision architecturale nouvelle ; étend ADR existante
    estimation: "réalisé ce run (Wave 65)"
```

## Verdict veille

La veille **n'a pas changé** le code d'aujourd'hui mais l'a **validé** : le
couplage de précipitation orographique retenu réutilise *verbatim* le modèle
worldgen (famille upslope+advection de Smith-Barstad), avec le lapse
6.5 °C/km déjà en place. Le saut FFT Smith-Barstad est un **remplacement**
(backlog), pas une extension cargo-less. Les items Rust/GPU/Bevy/WGPU du
prompt v2.0 restent **gelés** (ADR-0008, env sans `cargo`/`rustc`) → backlog
« session cargo ».

**Règle d'or respectée** : veille → combo → code → tests → push.
