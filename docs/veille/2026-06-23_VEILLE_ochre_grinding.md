# Veille technologique — 2026-06-23 (J+13, `ochre_grinding`)

**Mode :** scheduled task `continue-la-cration-de-genesis-enginer` (routine
veille-first v3.0), run **automatique**, user **absent**. **Contrainte env :**
`cargo`/`rustc` absents ([ADR-0008](../../adr/0008-python-rust-frontier.md), D7) ;
Python 3.14 seul ; CI = vérité pour toute affirmation Rust. La veille **précède**
tout code (règle d'or).

---

## ÉTAPE 0 — Veille (5 axes en parallèle)

### Axe 1 — IA & agents multi-LLM
`multi-agent LLM simulation 2026`, `LLM agent long-term memory`, `small LM
inference`. Convergence : **Emergence World** (arxiv 2606.08367, déjà ROADMAP),
**AIvilization v0** (2602.10429), **LightMem / Memory3 / Mem0** (mémoire
hiérarchique agent, KV-cache −40 %). → **GATED LLM tier-2** (Phase 5 inactive).
Aucun combo cargo-less ce jour.

### Axe 2 — Rust / ECS / moteur
`Bevy 0.16/0.18`, `Rust ECS 2026`, `WGPU GPU compute`. Bevy : ECS Relationships,
GPU-driven rendering, ray-tracing wgpu. → **GATED cargo** (P1 scaffolding Rust pas
vert). Déjà inscrit ROADMAP P5 (Bevy 0.18).

### Axe 3 — Crypto & sécurité
`post-quantum ML-KEM 2026`, `CVE Rust tokio gRPC k8s`. ML-KEM (FIPS 203) en
déploiement TLS 1.3/QUIC hybride ; PQC-in-Kubernetes (k8s blog 2025). **Aucune CVE
critique** à surface live Genesis (aucun endpoint réseau en prod ; PQC non
compilée). → **GATED endpoint** (déjà ROADMAP P5 : X-Wing X25519×ML-KEM-768).

### Axe 4 — Infra & data
`vector DB 2026`, `Neo4j vecteurs natifs`, `NATS JetStream`, `WebGPU API`. → tous
**GATED** déploiement Observatory Phase 5+ (déjà ROADMAP : Neo4j Native Vector Type).

### Axe 5 — Papers arXiv du jour
`artificial life`, `emergent civilization`, `generative agents`, `world models`.
**Flow-Lenia** (2506.08569, automates continus conservatifs), **Critiques of World
Models** (2507.05169), **Look Back to Reason Forward** (2509.23040, mémoire agent
revisitable). → rien d'applicable cargo-less sous 7 j (tous Phase 5 / world-model
neural).

### Axe substrat — l'archéochimie du pigment (la physique de C18)

La capacité du jour est l'**ocre broyée** — premier pigment, substrat du dessin.
La veille a donc porté sur la **physique** que le module calcule (jamais invente,
méta-règle du substrat). Recherche ciblée *« red ochre hematite vs yellow ochre
goethite pigment iron oxide lightfast prehistoric grinding »* — convergence des
sources :

- **L'ocre EST l'oxyde de fer terreux** : ocre **rouge** = **hématite** (`Fe₂O₃`) ;
  ocre **jaune** = **goethite** (`FeO(OH)`) / limonite. Le **noir** d'oxyde de fer =
  **magnétite** (`Fe₃O₄`). Ce sont les **oxydes** qui donnent le pigment.
- **Préparation** : on **mine la terre ocreuse, on la broie, on la lave** (séparer
  les grosses particules). Geste **à froid**, mécanique — le **broyage** est l'acte.
- **Lightfastness** : l'ocre rouge (hématite) est **extrêmement stable, lightfaste,
  compatible avec tous les liants** — d'où sa permanence (Lascaux, Altamira,
  Blombos ~100 ka, usage ≥ 300 ka).
- **Ocre brûlée** (transformation *fire-based*) : calciner la goethite jaune à
  **250–400 °C** la déshydrate en hématite → vire au rouge. → **différée
  honnêtement** à une future capacité (pendant de la calcination de la chaux C10 /
  vitrification C12 ; C18 reste **non-fire**).

→ **DIRECTEMENT APPLICABLE** : ces faits calibrent la SSOT `ochre_grind_yield`
(seuls les **oxydes** de fer = pigment ; hématite rouge / magnétite noir ;
sulfure pyrite & non-fer galène/sphalérite = **aucun pigment** ; lightfast ;
force colorante ∝ finesse de broyage, plafonnée). Aucune constante n'est inventée.

---

## WORLD_VEILLE_REPORT

```yaml
date: "2026-06-23"
duree_recherche: "~18 min (5 axes + ciblée archéochimie du pigment)"

decouvertes:
  - id: D1
    techno: "Archéochimie de l'ocre — le pigment EST l'oxyde de fer terreux (hématite rouge / goethite jaune / magnétite noir)"
    source: "Wikipedia Ochre/Hematite ; Ars Pictoria Red Ochre ; ScienceDirect ochres Namibia ; Chemistry World campfire pigment"
    telecharge: false
    applicable_a: "engine.ochre_grinding (Cap. C18) — SSOT ochre_grind_yield"
    gain_estime: "réalisme : le pigment devient physiquement vrai (oxyde→couleur, sulfure→rien, lightfast)"
    action: "COMBO_TODAY"
  - id: D2
    techno: "Préparation à froid (mine → broie → lave) + ocre brûlée goethite→hématite 250–400 °C"
    source: "Ars Pictoria ; Artslookup Stone-Age ochre ; Discover Magazine"
    telecharge: false
    applicable_a: "engine.ochre_grinding — le verbe BROYER (non-fire) ; calcination différée (fire, future cap)"
    gain_estime: "9ᵉ opérateur orthogonal non-fire ; ouvre l'axe symbolique (dessin)"
    action: "COMBO_TODAY"

cve_stack:
  - "Aucune CVE critique à surface live Genesis (aucun endpoint réseau prod ; PQC non compilée)."

paper_du_jour:
  titre: "rien de nouvel applicable cargo-less sous 7 j (Emergence World / AIvilization / Flow-Lenia tous Phase 5 ou world-model neural)"

world_model_updates:
  cosmos: "aucune (gated cargo)"
  autre: "Bevy 0.18 / ML-KEM-768 / Neo4j vecteurs natifs / mémoire agent (LightMem) — BACKLOG déjà inscrit ROADMAP P5"

combo_retenu:
  techno: "Archéochimie de l'ocre (D1) + broyage à froid (D2)"
  cible: "engine.ochre_grinding — broie le chapeau de fer C1 (à froid) → pigment d'oxyde"
  gain: "Cap. C18 : 9ᵉ opérateur orthogonal (broyer), 1ʳᵉ avancée axe symbolique, 108/144 sites émergents seed 0x42, 0 viol."
  adr_requis: false   # composition pure (D8, 12ᵉ) ; non mutant (D10 gelé)
```

---

## ÉTAPE 1 — COMBO retenu

- **COMBO_RETENU : aucun combo *externe* intégrable** (cargo / LLM tier-2 / endpoint
  tous gated — 5 axes confirment).
- **COMBO_INTERNE (le vrai combo du jour)** : C1 `surface_mineralization` (le
  **chapeau de fer** gossan) **×** le catalogue minéral (`category`,
  `yields_per_kg_ore["Fe"]`) **×** l'archéochimie du pigment (D1/D2). Effet
  **orthogonal sur la MÊME matière** : C17 réduit le gossan **à chaud → métal** ;
  C18 le broie **à froid → pigment**. Une lecture du monde, deux civilisations.
- **COMBO_BACKLOG :** Bevy 0.18 / multi-agent LLM / ML-KEM-768 / Neo4j vecteurs /
  mémoire agent hiérarchique (déjà ROADMAP P5).

**Décision :** Cap. **C18 `ochre_grinding`** — le 9ᵉ opérateur orthogonal
(*broyer*), **non-fire** (rompt à nouveau après C17 fire-based → D9 = 0, reco
`R-J12r3-1`), **non mutant** (D10 gelé), **D8 par composition** (12ᵉ ;
`PY_TO_RUST` reste 15). 1ʳᵉ avancée de l'**axe symbolique / dessin** (pilier
d'émergence jusqu'ici immobile). Mensonge rendu visible **#9** : le chapeau de
fer ment **aussi au peintre** (oxyde → couleur ; pyrite/plomb/zinc → rien).

---

## Sources

- [Ochre — Wikipedia](https://en.wikipedia.org/wiki/Ochre)
- [Hematite — Wikipedia](https://en.wikipedia.org/wiki/Hematite)
- [Red Ochre Pigment: History & Properties — Ars Pictoria](https://arspictoria.com/materials-and-tools/colors/red-ochre/)
- [Ochre Pigments in the Stone Age: Hematite & Goethite — Artslookup](https://www.artslookup.com/prehistoric/ochre-pigments-stone-age.html)
- [Mineralogical characterization of ochres (Himba/Nama, Namibia) — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S2352409X22003534)
- [Simple campfire chemistry hints how ancient humans produced pigments — Chemistry World](https://www.chemistryworld.com/news/simple-campfire-chemistry-hints-how-ancient-humans-produced-pigments/4014845.article)
- [Emergence World: long-horizon multi-agent autonomy — arXiv 2606.08367](https://arxiv.org/html/2606.08367)
- [Bevy 0.16 release notes](https://bevy.org/news/bevy-0-16/)
- [Post-Quantum Cryptography in Kubernetes — kubernetes.io blog](https://kubernetes.io/blog/2025/07/18/pqc-in-k8s/)
