# Veille technologique — 2026-06-16 (J+6, run #2) — World Realism System v2.0

**Routine :** WORLD_REALISM v2.0 — *veille-first*. Aucune ligne de code n'a été
écrite avant la clôture de cette veille (RÈGLE D'OR de la routine Substrate).
**Mode :** scheduled task (user absent) · exécution autonome · internet libre.
**Durée recherche :** ~25 min · 6 axes (les 6 recherches mandatées par la routine).

---

## ÉTAPE 0 — Veille (6 axes, recherches parallèles, internet libre)

### Recherche 1 — Simulation hydraulique & érosion (GPU)
- Implémentations d'érosion hydraulique GPU par **compute shaders** (shallow-water
  + champ de vitesse) : 40–50 fps interactifs, « 1 M de gouttes en 10 s »
  (bshishov/UnityTerrainErosionGPU, makeitshaded). **Aucun benchmark WGSL 2026
  dédié** trouvé — l'état de l'art reste OpenGL/HLSL/Unity. → Couche **World (port
  Rust/WGPU)**, conditionné `cargo` (absent ici, ADR-0008) → **BACKLOG**.

### Recherche 2 — World models & cohérence physique neuronale
- **NVIDIA Cosmos 3 : Omnimodal World Models for Physical AI** (arxiv 2606.02800,
  sorti 2026-05-31) — architecture mixture-of-transformers unifiant raisonnement
  physique + simulation + génération d'action. **DeepMind Genie 3** : raisonnement
  physique *émergent* (gravité, collisions) sans moteur explicite, mondes 3D
  persistants 24 fps. **Enhancing Physical Consistency in Lightweight World
  Models** (arxiv 2509.12437) — pertinent pour un NIVEAU 2 *léger*. → SYSTÈME G
  (cohérence macro), conditionné Phase 5 → **BACKLOG**.

### Recherche 3 — Géologie procédurale & minéraux
- Modèles **voxel** de distribution minérale par **krigeage** ; *synthetic ore
  body models* (un seul rock_type par voxel) ; couplage déformation-fluide-chaleur
  (FLAC3D) pour prédire la minéralisation cachée. Confirme l'approche **filons =
  contact pluton × fracture** déjà dans `engine.geology`. Pas de nouvel outil
  open-source 2026 directement intégrable cargo-less → **BACKLOG**.

### Recherche 4 — Thermodynamique, atmosphère & météo
- **Neural GCM** (solveur différentiable + composantes ML pour météo/climat) ;
  schémas de condensation/convection simplifiés des GCM idéalisés. → SYSTÈME D
  (climat émergent), conditionné Phase 5 → **BACKLOG**.

### Recherche 5 — Biologie, végétation & écosystème
- **Modèle de Rothermel** (jalon 50 ans, 2022) ; reformulation *heterogeneous
  fuelbeds* ; rôle accru des combustibles vivants (humidité saisonnière). → **DÉJÀ
  INTÉGRÉ** dans `engine.wildfire` (Wave 14, feu spontané) ; la charge de
  combustible fin de C7 `fire_ignition` (`fine_fuel`) en dérive l'esprit.

### Recherche 6 — Archéométrie de la cuisson céramique ⟵ **AXE DU JOUR**
- **Seuils de transformation minérale à la cuisson** (Kostadinova-Avramova,
  *Archaeometry* 2025, doi 10.1111/arcm.13012) : calcite, hématite, spinelle,
  gehlénite, quartz, illite donnent des **marqueurs à 675 / 700 / 750 / 950 /
  1050 / 1100 / 1300 °C**. L'illite/kaolinite **fritte ~700–750 °C** ; la
  vitrification (gehlénite/spinelle) débute **~950–1050 °C**.
- **Bonfire / pit firing** (Gosselain ; Gibson & Woods ; EXARC 2025 ;
  expérience Santa Margarida, Martorell, mai 2025 — pic **950 °C**) : *« earthenware
  fired as low as 600 °C »*, poterie en fosse **typiquement < 800 °C**, vitrification
  (imperméabilité) **~800–900 °C**, plage 600–900 °C qui se chevauche entre
  techniques. → **PAPER_DU_JOUR + COMBO_RETENU.**

---

## SYNTHÈSE VEILLE (format obligatoire WORLD_VEILLE_REPORT)

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-16"
  duree_recherche: "~25 min"
  decouvertes:
    - id: D1
      techno: "Archéométrie de la cuisson — seuils thermiques (Archaeometry 2025 ;
               Bonfire ; EXARC 2025)"
      source: "doi 10.1111/arcm.13012 ; sciencedirect S2352409X25002226 ; exarc.org"
      telecharge: false   # lecture en ligne (résumés + tables de seuils)
      applicable_a: "Cap. C9 ceramic_firing (transformation argile→céramique)"
      gain_estime: "réalisme : T° de feu ouvert 600–850 °C × maturation argile
                    (terre ~700, kaolin réfractaire ~1250) — cuisson CALCULÉE,
                    jamais arbitraire ; +1 capacité de transformation actionnable"
      action: "COMBO_TODAY"
    - id: D2
      techno: "NVIDIA Cosmos 3 (omnimodal world model) ; DeepMind Genie 3"
      source: "arxiv 2606.02800 ; github.com/nvidia/cosmos"
      telecharge: false
      applicable_a: "SYSTÈME G — cohérence macro NIVEAU 2 (Phase 5)"
      gain_estime: "cohérence régionale sans calcul exact"
      action: "BACKLOG_ROADMAP"   # cargo-less + Phase 5 (ADR-0008)
    - id: D3
      techno: "Érosion hydraulique GPU (shallow-water compute shaders)"
      source: "github bshishov/UnityTerrainErosionGPU ; makeitshaded"
      telecharge: false
      applicable_a: "SYSTÈME B — érosion (port Rust/WGPU)"
      gain_estime: "perf temps réel"
      action: "BACKLOG_ROADMAP"   # cargo absent ici
  cve_stack:
    - "aucune CVE critique applicable — 0 surface réseau en ère cargo-less
       (ADR-0008) ; aucun endpoint/agent LLM câblé ; sandboxing tenu."
  paper_du_jour:
    titre: "Pottery firing temperatures — bonfire/pit thresholds (Archaeometry 2025
            + Bonfire corpus)"
    url: "https://onlinelibrary.wiley.com/doi/10.1111/arcm.13012"
    technique: "feu ouvert 600–850 °C ; illite/kaolinite frittage ~700–750 °C ;
                vitrification ~950–1050 °C ; kaolin réfractaire (sous-cuit au feu nu)"
    effort: "~3 h · complexité 2"
  world_model_updates:
    cosmos: "Cosmos 3 omnimodal (2026-05-31, arxiv 2606.02800) — backlog Phase 5"
    genie3: "raisonnement physique émergent sans moteur — backlog Phase 5"
    autre: "Enhancing Physical Consistency in Lightweight World Models (2509.12437)"
  combo_retenu:
    techno: "Seuils de cuisson archéométriques × Cap. C9 ceramic_firing"
    cible: "engine.ceramic_firing (transformation par composition C5 × C7)"
    gain: "cuisson physiquement gouvernée (peak feu × maturation argile) ;
           inversion réfractaire émergente ; +18 tests ; 0 surface réseau"
    adr_requis: false   # confirme ADR-0005 (lecture L1) + ADR-0008 (frontière)
```

---

## ÉTAPE 1 — Moteur de combinaison (COMBO-GENESIS)

```
COMBO_RETENU : Seuils thermiques de cuisson (archéométrie 2025)
               × Cap. C9 ceramic_firing (2ᵉ transformation par composition)
  Gain        : la cuisson devient un phénomène CALCULÉ — température de pointe du
                feu ouvert (600–850 °C selon fine_fuel) confrontée à la maturation
                de l'argile (terre commune ~700 °C, kaolin réfractaire ~1250 °C).
                Émergence : l'INVERSION RÉFRACTAIRE (la meilleure argile sous-cuit
                au feu nu) naît du calcul, jamais scriptée. +18 tests ; coût tick nul.
  Coût        : ~3 h · complexité 2 · risque régression 1 (capacité additive,
                composition pure de C5 × C7, aucune mutation du substrat).
  Couche      : Substrate (runtime/engine Python).
  Intégration : C9 lit C5 (argile + pottery_grade + ceramic_grade) × C7 (feu +
                fine_fuel) → ware_quality déterministe borné ; AUCUNE entrée
                PY_TO_RUST (garde-fou D8 par composition, 3ᵉ fois après C7/C8).
  ADR requis  : NON — confirme ADR-0005 (lecture L1) + ADR-0008 (frontière) existants.

COMBO_BACKLOG: Cosmos 3 / Genie 3 (SYSTÈME G, NIVEAU 2, Phase 5) ; érosion GPU
               shallow-water (SYSTÈME B, port Rust) ; Neural GCM (SYSTÈME D, météo).
               → restent en ROADMAP (cargo-less / Phase 5, garde-fou 60 j).
COMBO_REJETÉ : world model NIVEAU 2 *aujourd'hui* — aucun runtime Rust/GPU câblé en
               ère cargo-less ; l'intégrer serait du code mort non testable ici.
```

---

## ÉTAPE 2 — Tâche du jour

- **PHASE :** 4 (émergence civilisationnelle) ; couches actives = Substrate +
  World (Python). **P0_BLOQUANTS : aucun.**
- **TÂCHE_JOUR :** Cap. **C9 `ceramic_firing`** — 2ᵉ transformation par composition
  (suite logique de C8 : C5 argile × C7 feu → céramique), méta-règle « un phénomène
  naturel de plus, physiquement cohérent, chaque jour ».
- **IMPACTÉ_PAR_VEILLE : OUI** — le COMBO_RETENU (seuils de cuisson) *gouverne*
  directement la physique de C9 : les températures ne sont pas inventées, elles
  viennent de l'archéométrie 2025 (feu ouvert 600–850 °C ; kaolin réfractaire).

Livré ce jour : **Cap. C9 `engine.ceramic_firing`** (18 tests + smoke `p141` 7/7,
pytest 552→570). Le monde est plus vrai ce soir : l'argile cuit pour de vraies
raisons thermiques, et la belle argile blanche déçoit au feu de camp — comme dans
la réalité.
