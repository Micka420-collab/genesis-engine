# Veille technologique — 2026-06-17 (J+7) — Morning Routine v3.0

**Routine :** GENESIS MORNING ROUTINE v3.0 — *veille-first*. Aucune ligne de code
n'a été écrite avant la clôture de cette veille (RÈGLE D'OR de la routine).
**Mode :** scheduled task (user absent) · exécution autonome · internet libre.
**Durée recherche :** ~18 min · 5 axes (les 5 recherches mandatées par la routine).

---

## ÉTAPE 0 — Veille (5 axes, recherches parallèles, internet libre)

### Recherche 1 — Nouvelles techno IA & agents
- **Generative Agents** (mémoire observe→réflexion→plan) restent l'état de l'art du
  comportement social émergent ; travaux 2025-2026 simulant **>1000 individus réels**
  via mémoires dérivées d'interviews (**85 % de fidélité** sur prédictions d'enquête,
  biais démographiques réduits). Récupération mémoire : décroissance temporelle ×
  importance × similarité vectorielle (arxiv 2510.18155 ; PMC12092450). → Couche
  **Agentic / Social**, conditionnée Phase 5 (aucun endpoint LLM câblé, cargo-less,
  ADR-0008) → **BACKLOG**.

### Recherche 2 — Nouvelles techno Rust / ECS / moteur
- **Bevy 0.16** : **ECS Relationships** (modélisation entité-entité robuste),
  **rendu GPU-driven** + **occlusion culling**, propagation de transform statique
  fortement optimisée ; backend **wgpu** (Vulkan/Metal/D3D12/WebGPU). Crate
  communautaire **`bevy_gpu_compute`** (offload GPU en Rust pur, sans WGSL). →
  Couche **Substrate / World (port Rust/WGPU)**, conditionnée `cargo` (absent ici)
  → **BACKLOG**.

### Recherche 3 — Cryptographie & sécurité
- **ML-KEM** (FIPS 203) en déploiement industriel 2026 : **AWS retire CRYSTALS-Kyber
  au profit de ML-KEM** sur tous ses endpoints en 2026 ; Chrome/Firefox/Safari en
  accord de clé hybride. Côté Rust : `rustls` + feature `prefer-post-quantum`.
  Défense prompt-injection : **DefensiveTokens** (arxiv 2507.07974), signatures
  d'instruction / référencement de l'instruction exécutée (arxiv 2504.20472). →
  Couche **Platform**. **CVE_ACTIVES : aucune critique applicable** — 0 surface
  réseau en ère cargo-less (ADR-0008), aucun endpoint/agent LLM câblé, sandboxing
  tenu. ML-KEM-768 hybride X25519 reste la cible **J1 de réactivation** (runbook
  PQ existant) → **BACKLOG**.

### Recherche 4 — Nouvelles techno infra & data
- **Neo4j** : nouveau **type Vector natif** (intégrité par contrainte de type,
  index/fonctions vectorielles) ; combinaison **graphe × vecteur** (TigerVector,
  arxiv 2501.11216) pour RAG avancé. **ClickHouse** intègre NATS ; **NATS
  JetStream** = persistance distribuée. → Couche **Observatory / Platform**,
  conditionnée Phase 5 → **BACKLOG**.

### Recherche 5 — Papers arXiv du jour
- **NVIDIA Cosmos / world models omnimodaux** ; **Emergent Language as an Approach
  to Conscious AI** (arxiv 2606.06380, 2026) — langage émergent depuis conditions
  minimales sous *pression de tâche seule* (résonne avec la règle d'émergence
  absolue du projet) ; **Multi-Agent Systems: from Classical Paradigms to LFM-Enabled
  Futures** (arxiv 2604.18133). → **System G / Agentic**, backlog Phase 5.
- **AXE DU JOUR — Archéométrie de la chaux (calcination du calcaire).** La veille C9
  (2026-06-16) avait introduit la **pointe du feu ouvert** `open_fire_peak_temp_c`
  (600–850 °C) pour la cuisson de l'argile. Le **pendant exact** restait à livrer :
  **brûler le calcaire C6 dans ce même feu C7 → chaux**. Thermochimie (Boynton,
  *Chemistry and Technology of Lime and Limestone* ; littérature décomposition
  CaCO₃) : décomposition complète de la calcite pure à **~898 °C** (P(CO₂)=1 atm) ;
  carbonate **fondu / dolomitique** (MgCO₃, fondants argileux/Fe/alcalins) décarbonate
  **plus bas** (~680–750 °C) ; un **feu ouvert (≤850 °C) sous-cuit donc le calcaire
  pur réfractaire** — le *mortier liant* a historiquement exigé un **four à chaux**
  (chaux néolithique en grands feux/tas : enduits de Göbekli Tepe ~9500 av. J.-C.).
  → **PAPER_DU_JOUR + COMBO_RETENU.**

---

## SYNTHÈSE VEILLE (format obligatoire)

```yaml
GENESIS_VEILLE_REPORT:
  date: "2026-06-17"
  duree_recherche: "~18 min"
  decouvertes:
    - id: D1
      techno: "Archéométrie de la chaux — thermochimie de la calcination du
               calcaire (Boynton ; décomposition CaCO3 ~898 °C ; MgCO3/fondants
               abaissent l'onset)"
      couche: "Substrate (capacité agent C10)"
      gain_estime: "réalisme : T° de feu ouvert (réemploi C9) × seuil de
                    décarbonatation (commun ~680 / pur ~770, complet ~898) —
                    calcination CALCULÉE, jamais arbitraire ; +1 capacité de
                    transformation actionnable (chaux/mortier)"
      action: "COMBO_TODAY"
    - id: D2
      techno: "ML-KEM (FIPS 203) en déploiement industriel — AWS retire Kyber 2026 ;
               rustls prefer-post-quantum ; DefensiveTokens (prompt injection)"
      couche: "Platform"
      gain_estime: "sécurité : ML-KEM-768 hybride X25519 sur tout endpoint à la
                    réactivation (J1) ; défense prompt-injection durcie"
      action: "BACKLOG_ROADMAP"   # 0 surface réseau cargo-less (ADR-0008)
    - id: D3
      techno: "Bevy 0.16 (ECS Relationships, rendu GPU-driven, occlusion culling) ;
               bevy_gpu_compute"
      couche: "Substrate / World (port Rust/WGPU)"
      gain_estime: "perf : offload GPU, hiérarchies d'entités robustes"
      action: "BACKLOG_ROADMAP"   # cargo absent ici (ADR-0008)
  cve_stack:
    - "aucune CVE critique applicable — 0 surface réseau en ère cargo-less
       (ADR-0008) ; aucun endpoint/agent LLM câblé ; sandboxing tenu."
  paper_du_jour:
    titre: "Lime calcination thermochemistry — CaCO3 decomposition thresholds
            (Boynton, Chemistry and Technology of Lime and Limestone)"
    technique: "décarbonatation : carbonate commun/dolomitique ~680 °C, calcaire pur
                réfractaire ~770 °C, conversion complète ~898 °C (P(CO2)=1 atm) ;
                feu ouvert ≤850 °C sous-cuit le pur → mortier liant exige un four"
    effort: "~3 h · complexité 2"
  combo_retenu:
    titre: "COMBO — réemploi de open_fire_peak_temp_c (C9) × lime_class (C6)"
    description: "C10 lime_burning RÉUTILISE verbatim la SSOT de température du feu
                  ouvert introduite par C9 (au lieu de la re-modéliser) et la
                  confronte au seuil de décarbonatation dérivé de la classe de
                  carbonate de C6 — un seul feu, deux pyrotransformations."
    gain: "+1 capacité agent (C10), 0 duplication de physique, inversion réfractaire
           réelle (calcaire pur sous-cuit < calcaire commun cuit), cap. four future"
    cout: "~3 h · complexité 2 · risque régression 1 (composition pure, 0 nouveau tell)"
    couche: "Substrate"
    adr_requis: "NON (capacité dérivée du substrat, ADR-0005 ; garde-fou D8 par
                 composition — 4ᵉ fois après C7/C8/C9, PY_TO_RUST inchangé à 15)"
  world_model_updates:
    cosmos: "world models omnimodaux — backlog Phase 5"
    emergent_language: "arxiv 2606.06380 — langage émergent sous pression de tâche
                        seule ; résonne avec la règle d'émergence absolue — veille"
```

---

## ÉTAPE 1 — Moteur de combinaison (COMBO-GENESIS)

**COMBO_RETENU :** `cf.open_fire_peak_temp_c` (C9) × `limestone_outcrop.lime_class`
(C6) → **Cap. C10 `lime_burning`**.

- **Q1 (existe déjà ?)** La physique du feu ouvert existe (C9) ; le calcaire est
  perçu (C6) ; mais **aucune transformation calcaire→chaux** n'existait. → *extend*.
- **Q2 (se combine avec ?)** C6 `limestone_outcrop` (matière + `lime_grade` +
  `lime_class` + `mortar_grade`) × C7 `fire_ignition` (feu + `fine_fuel`) × C9
  `ceramic_firing` (SSOT `open_fire_peak_temp_c`, réemployée). Lien implicite à
  C3 (extinction de la chaux vive à l'eau).
- **Q3 (gain mesurable ?)** +1 capacité agent (10ᵉ) ; inversion réfractaire réelle
  sur monde Genesis (seed 0xBEEF) : calcaire pur sous-cuit (lime 0,12) < calcaire
  commun cuit (lime 0,72) ; 0 nouveau tell ; pose la capacité **four à chaux** future.
- **Q4 (coût ?)** ~3 h · complexité 2 · risque régression 1 (composition pure).

**COMBO_BACKLOG :** ML-KEM-768 hybride (J1 réactivation), Bevy 0.16 / `bevy_gpu_compute`
(port Rust), Neo4j vector type (Observatory) → notés ROADMAP.
**COMBO_REJETÉ :** aucun (les 4 autres axes sont des backlogs Phase 5 / cargo-less,
pas des rejets).
