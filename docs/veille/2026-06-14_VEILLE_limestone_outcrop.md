# WORLD_VEILLE_REPORT — 2026-06-14 (session Cap. C6 `limestone_outcrop`)

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-14"
  duree_recherche: "~25 min"

  decouvertes:
    - id: D1
      techno: "Calcination du calcaire → chaux vive (CaCO3 → CaO + CO2)"
      source: "researchgate 222047492 (Effects of Limestone Characteristics and
               Calcination Temperature on Quicklime Reactivity) ;
               link.springer 10.1007/s12520-022-01535-0 ; ispatguru.com"
      telecharge: false
      applicable_a: "Cap. C6 limestone_outcrop — porte de grade chaux/mortier"
      gain_estime: "réalisme : grade de chaux dérivé de la PURETÉ carbonatée
                    (décarbonatation 700–900 °C, max ~782 °C) ; +1 type de
                    découverte agent (chaux vive → mortier/enduit)"
      action: "COMBO_TODAY"
      raison_si_rejet: ""

    - id: D2
      techno: "La chaux = le PLUS ANCIEN liant connu — Néolithique 9000–6000 av.
               J.-C. (sols d'enduit de chaux à Göbekli Tepe ~9500 av. J.-C.),
               ANTÉRIEUR à la métallurgie, au verre et parfois à l'agriculture"
      source: "link.springer 10.1007/s12520-022-01535-0 ; youblob 'Burning Lime
               from Limestone — Oldest Chemical Industry on Earth'"
      telecharge: false
      applicable_a: "justification stone-age de C6 (capacité, pas observateur)"
      gain_estime: "ancre la capacité dans l'âge de pierre : la chaux précède
                    le métal → place C6 juste après C5 (argile) dans l'échelle"
      action: "COMBO_TODAY"
      raison_si_rejet: ""

    - id: D3
      techno: "Karstification : dissolution du carbonate par l'eau de pluie
               légèrement acide (CO2) ; « plus la teneur en calcite est élevée,
               plus le potentiel de dissolution est grand »"
      source: "en.wikipedia.org/wiki/Karst ; springer 10.1007/s13146-022-00813-1
               (rain-induced weathering dissolution of limestone) ;
               PMC11999295 (2025, carbonate dissolution kinetics)"
      telecharge: false
      applicable_a: "Cap. C6 — porte d'altération (pierre saine vs karst fissuré)"
      gain_estime: "réalisme : la même exposition blanche n'est dressable en
                    blocs que si elle est SAINE (sèche/tempérée) ; humide → karst
                    fissuré, gel → cryoclastie (lien Wave 50). Effet 1+1>2
                    hydrologie (SYSTÈME A) × géologie (SYSTÈME C) × frost (Wave 50)"
      action: "COMBO_TODAY"
      raison_si_rejet: ""

    - id: D4
      techno: "Érosion hydraulique GPU — « Multigrid-inspired Eulerian hydraulic
               erosion » (2025) : bilan d'eau eulérien, conservation de masse
               sans opérations atomiques → plus GPU-friendly que pipes Theobald"
      source: "sapereaude1490.itch.io/eulerian-erosion ;
               bshishov/UnityTerrainErosionGPU (shallow-water + compute)"
      telecharge: false
      applicable_a: "SYSTÈME B (érosion) — backlog Rust/WGPU (cargo absent ici)"
      gain_estime: "perf GPU (suppression des atomics) — non chiffrable sans banc"
      action: "BACKLOG_ROADMAP"
      raison_si_rejet: "câblage GPU = item Phase A (cargo indisponible cet env)"

    - id: D5
      techno: "Modélisation 3D de gisements calcaire/gypse par ML non-supervisé +
               inversion géophysique (borehole + résistivité), voxel-refinement
               de roche carbonatée numérique"
      source: "link.springer 10.1007/s13146-025-01122-z (2025) ;
               USGS mrdata 'Carbonate Shelf Sequence' (plateforme carbonatée)"
      telecharge: false
      applicable_a: "SYSTÈME C (géologie procédurale) — calibration future"
      gain_estime: "réalisme distribution carbonatée (plateforme = lowland/marin
                    peu profond) → confirme le biome_affinity de limestone_pure"
      action: "BACKLOG_ROADMAP"
      raison_si_rejet: "pas de besoin d'un dataset externe aujourd'hui ; le combo
                        D1×D2×D3 suffit et reste 100 % émergent"

  cve_stack:
    - "RUSTSEC-2026-0009 (crate `time` : DoS par épuisement de pile). Non
       impactant : `time` n'est pas une dépendance directe du substrat Genesis.
       À surveiller au câblage Rust Phase A (audit `cargo`)."
    - "Rust Blog 2026-02-13 : mise à jour de la politique de notification des
       crates malicieux — informatif, aucune action."
    - "Stack Python (env réel) : aucune CVE critique aujourd'hui."

  paper_du_jour:
    titre: "The Effects of Limestone Characteristics and Calcination Temperature
            on the Reactivity of Quicklime"
    url: "https://www.researchgate.net/publication/222047492"
    technique: "La réactivité de la chaux vive dépend de la pureté du calcaire et
                de la température de cuisson (700–900 °C, décarbonatation maximale
                ~782 °C). Extraction : un GRADE DE CHAUX (lime_grade) ∝ pureté
                carbonatée → seuil mortier/plâtre. La pureté gouverne AUSSI la
                karstifiabilité (D3) — tension honnête : le carbonate le plus pur
                fait la meilleure chaux ET se dissout le plus."
    effort: "0.5 j · complexité 2/5 (capacité Python, dérivation pure)"

  world_model_updates:
    cosmos: "NVIDIA Cosmos 3 (rapport technique 2026-06-01, 'Omnimodal World
             Models for Physical AI') — cohérence physique stricte (robotique).
             Toujours non câblable ici (pas de GPU/cargo). Backlog NIVEAU 2."
    genie3: "DeepMind Genie 3 — monde interactif 24 fps, raisonnement physique
             émergent SANS moteur physique explicite. Intérêt conceptuel pour
             NIVEAU 2 (macro), non intégrable cet env."
    autre: "arXiv 2509.12437 'Enhancing Physical Consistency in Lightweight World
            Models' — piste PINN légère pour le NIVEAU 2, backlog."

  combo_retenu:
    techno: "D1 (calcination → grade chaux) × D2 (chaux = liant néolithique le
             plus ancien) × D3 (karstification = porte d'altération de la pierre)"
    cible: "engine/limestone_outcrop.py (Cap. C6) — affleurement calcaire :
            pierre à bâtir + chaux vive → mortier. Pendant construction de C5
            (argile=récipient ; calcaire=maçonnerie+mortier). Ferme l'orphelin
            Rust Mineral::LimestonePure (catalogue limestone_pure, tell byte-exact
            (245,240,225), PY_TO_RUST enrichi — garde-fou ADR-0007)."
    gain: "+1 capacité agent ; géologie 77→78 ; +1 minéral catalogue ;
           4ᵉ référence couleur verrouillée cross-langage ; 0 coût tick"
    adr_requis: false   # réutilise ADR-0005 (lecture substrat) + ADR-0007 (garde-fou)
```

## Note méthodologique

Conforme à l'ORDRE ABSOLU (`0. VEILLE → 1. COMBO → 2. DÉCISION → 3. CODE → 4. PUSH`) :
aucune ligne de code n'a été écrite avant ce rapport. Le combo retenu est
**100 % émergent** (on rend le carbonate, sa pureté et son altération
détectables ; jamais « construis un mur » ni « fais du mortier ») et **dérivé du
substrat existant** (lithologie `limestone` + ores carbonatés + biome +
`chunk.water`), donc **zéro coût tick** et **déterministe** (`prf_rng`). Le
câblage moteur Rust (D4/D5, GPU/cargo) reste un item **Phase A** hors de portée
de cet environnement Python-seul (CI = vérité).
