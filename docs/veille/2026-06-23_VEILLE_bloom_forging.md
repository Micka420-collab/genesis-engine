# Veille technologique — 2026-06-23 (J+13 run #2, `bloom_forging`)

**Mode :** scheduled task `genesis-engine--world-realism-system-v20`
(Substrate Layer, routine veille-first), run **automatique**, user **absent**.
**Contrainte env :** `cargo`/`rustc` absents
([ADR-0008](../../adr/0008-python-rust-frontier.md), D7) ; Python 3.14 seul ;
CI = vérité pour toute affirmation Rust. La veille **précède** tout code
(règle d'or). Internet libre disponible ce jour (WebSearch).

---

## ÉTAPE 0 — Veille (5 axes + ciblée archéométrie de la forge)

### Axe 1 — IA & agents multi-LLM
`multi-agent LLM simulation 2026`, `agent long-term memory`. Convergence inchangée
depuis J+13 run #1 : **Emergence World** (arxiv 2606.08367, déjà ROADMAP),
**AIvilization v0**, **LightMem / Memory3** (mémoire hiérarchique). → **GATED LLM
tier-2** (Phase 5 inactive). Aucun combo cargo-less ce jour.

### Axe 2 — Rust / ECS / moteur
`Bevy 0.16/0.18`, `WGPU GPU compute`. → **GATED cargo** (P1 scaffolding Rust pas
vert ; ADR-0008). Déjà inscrit ROADMAP P5 (Bevy 0.18).

### Axe 3 — Crypto & sécurité
`post-quantum ML-KEM 2026`, `CVE Rust tokio gRPC`. **Aucune CVE critique** à surface
live Genesis (aucun endpoint réseau prod ; PQC non compilée). → **GATED endpoint**
(déjà ROADMAP P5 : X-Wing X25519×ML-KEM-768).

### Axe 4 — Infra & data
`vector DB`, `Neo4j vecteurs natifs`, `WebGPU`. → tous **GATED** déploiement
Observatory Phase 5+ (déjà ROADMAP).

### Axe 5 — Papers arXiv du jour
`artificial life`, `emergent civilization`, `world models`. Rien d'applicable
cargo-less sous 7 j (tous Phase 5 / world-model neural). Inchangé J+13 run #1.

### Axe substrat — l'archéométrie de la consolidation (la physique de C19)

La capacité du jour **ferme la chaîne du fer** : C17 a livré la **loupe** spongieuse
(`requires_forging` True, différé honnête) ; C19 la martèle. La veille a donc porté
sur la **physique** que le module calcule (jamais inventée, méta-règle du substrat).
Deux recherches ciblées — convergence des sources :

1. *« bloomery iron bloom consolidation shingling fayalite slag expulsion hot working
   wrought iron archaeometallurgy »* :
   - La loupe = **éponge** de fer métallique + **scorie de fayalite** (`Fe₂SiO₄`),
     réduite ~1100 °C, **sous** le point de fusion du fer.
   - **Cinglage primaire** (primary smithing) : on **réchauffe** la loupe pour que le
     fer passe en **austénite** (~900 °C) **et** que la fayalite devienne **fondue**
     (**1200–1300 °C**) ; on **martèle à chaud** pour **expulser la scorie** et
     **consolider** le métal en un billon — **plusieurs chaudes** successives à haute
     température de soudage.
   - Le produit est du **fer forgé** (wrought iron), **jamais** de la fonte.
   - → calibre `SLAG_EXPULSION_TEMP_C` (réemploi `fd.IRON_BLOOMERY_TEMP_C` = 1200 °C,
     le régime où la fayalite coule — **un feu nu ≤ 850 °C est trop froid**) ;
     `EXPEL_PER_HEAT` (fraction géométrique expulsée par chaude) ; `SCALE_LOSS_PER_HEAT`
     (battitures FeO en feu oxydant) ; `melted` toujours False (solid-state).

2. *« hot shortness red short sulfur iron forging cracks fire scale loss »* :
   - Le **soufre** (loupe de **pyrite**, C17 `red_short`) forme du **FeS** aux joints
     de grain ; FeS **fond sous la température de forge** → **phase liquide
     intergranulaire** → **fissuration pendant le martelage à chaud** (*hot-shortness*).
   - C'est exactement pourquoi la pyrite est un mauvais minerai de fer **jusqu'au
     marteau** : le fer est obtenu (C17) puis **se brise à la forge** (C19).
   - → calibre `RED_SHORT_CRACK_LOSS` (le fer qui s'éclate) + `RED_SHORT_SOUNDNESS_CEIL`
     (jamais sain). **Mensonge rendu visible #10**, pendant à l'étape suivante de
     l'inversion à 5 voies de C17.

→ **DIRECTEMENT APPLICABLE** : ces faits calibrent la SSOT `wrought_yield` (oxyde →
fer forgé sain ; pyrite red-short → fissure, rendement effondré ; chaleur < seuil →
rien ; conservation Fe `wrought + scale + crack == bloom`). Aucune constante n'est
inventée.

---

## WORLD_VEILLE_REPORT

```yaml
date: "2026-06-23"
duree_recherche: "~22 min (5 axes + 2 recherches ciblées archéométrie de la consolidation)"

decouvertes:
  - id: D1
    techno: "Cinglage / consolidation de la loupe — réchauffe 1200-1300 °C → fayalite liquide → martelage expulse la scorie → fer forgé (solid-state, jamais fonte)"
    source: "EXARC Journal (bloomery furnaces) ; Wikipedia Bloomery/Ferrous metallurgy ; tandfonline Hoeke ironworking ; SI Handrails (wrought iron process)"
    telecharge: false
    applicable_a: "engine.bloom_forging (Cap. C19) — SSOT wrought_yield ; seuil SLAG_EXPULSION_TEMP_C (réemploi C12)"
    gain_estime: "réalisme : la consolidation devient physiquement vraie (slag expulsée géométriquement, battitures FeO, jamais fondu) ; ferme la chaîne du fer"
    action: "COMBO_TODAY"
  - id: D2
    techno: "Hot-shortness / red-short — FeS aux joints de grain fond sous la chaleur de forge → fissuration intergranulaire au martelage"
    source: "Quora/IspatGuru/Corrosionpedia/metalzenith (sulphur in steel, hot shortness)"
    telecharge: false
    applicable_a: "engine.bloom_forging — RED_SHORT_CRACK_LOSS + RED_SHORT_SOUNDNESS_CEIL (la loupe de pyrite se brise)"
    gain_estime: "mensonge rendu visible #10 : le fer du chapeau pyriteux se brise sous le marteau (pendant, à l'étape suivante, du red_short C17)"
    action: "COMBO_TODAY"

cve_stack:
  - "Aucune CVE critique à surface live Genesis (aucun endpoint réseau prod ; PQC non compilée)."

paper_du_jour:
  titre: "rien de nouvel applicable cargo-less sous 7 j (Emergence World / AIvilization tous Phase 5 ou world-model neural)"

world_model_updates:
  cosmos: "aucune (gated cargo)"
  autre: "Bevy 0.18 / ML-KEM-768 / Neo4j vecteurs natifs / mémoire agent — BACKLOG déjà inscrit ROADMAP P5"

combo_retenu:
  techno: "Archéométrie de la consolidation (D1) + hot-shortness du soufre (D2)"
  cible: "engine.bloom_forging — martèle la loupe C17 (à chaud, foyer C12) → fer forgé"
  gain: "Cap. C19 : 6e transformation, 3e métallurgique, FERME la chaîne du fer ; 78/144 sites émergents seed 0x42 (47 oxyde sains + 31 pyrite fissurées), 0 viol."
  adr_requis: false   # composition pure (D8, 13e) ; non mutant (D10 gelé)
```

---

## ÉTAPE 1 — COMBO retenu

- **COMBO_RETENU : aucun combo *externe* intégrable** (cargo / LLM tier-2 / endpoint
  tous gated — 5 axes confirment, inchangé depuis J+13 run #1).
- **COMBO_INTERNE (le vrai combo du jour)** : C17 `iron_bloomery` (la **loupe**
  spongieuse, elle-même C12×C1) **×** l'archéométrie de la consolidation (D1) **×** la
  métallurgie du soufre (D2). Effet **« étape suivante » sur la MÊME matière** : C17
  réduit le chapeau de fer **à chaud → loupe** (mutant) ; C19 la cingle **à chaud →
  fer forgé** (non mutant). Le fer du gossan pyriteux, obtenu en C17, **se brise** en
  C19 — le mensonge se paie plus tard et plus cher dans la chaîne.
- **COMBO_BACKLOG :** Bevy 0.18 / multi-agent LLM / ML-KEM-768 / Neo4j vecteurs /
  mémoire agent hiérarchique (déjà ROADMAP P5).

**Décision :** Cap. **C19 `bloom_forging`** — la 6ᵉ TRANSFORMATION et la 3ᵉ
MÉTALLURGIQUE, qui **ferme la chaîne opératoire du fer** (exécute la reco
`R-J12r3-2` de l'audit J+12 : *« la forge de consolidation ferme la chaîne du fer —
sans nouveau tell, sans feu nouveau »*). **Fire-based** (la forge à chaud est
**physiquement obligatoire** — aucun travail à froid ne chasse la scorie d'une
loupe) → D9 **0 → 1** après le non-feu C18 : **alternance** propre, pas un treadmill.
**Non mutant** (D10 gelé — transforme un produit tenu, pas la géologie). **D8 par
composition** (13ᵉ ; `PY_TO_RUST` reste 15, hors glob `*_outcrop.py`). Mensonge rendu
visible **#10** : le fer du chapeau pyriteux **se brise sous le marteau** (red-short
hot-shortness).

---

## Sources

- [Smelting Conditions and Smelting Products — The EXARC Journal](https://exarc.net/issue-2020-2/ea/development-bloomery-furnaces)
- [Bloomery — Wikipedia](https://en.wikipedia.org/wiki/Bloomery)
- [Ferrous metallurgy — Wikipedia](https://en.wikipedia.org/wiki/Ferrous_metallurgy)
- [Archaeometallurgical research, Medieval Harbour at Hoeke (Belgium) — Taylor & Francis](https://www.tandfonline.com/doi/full/10.1080/20548923.2023.2257067)
- [How Is Wrought Iron Made? — SI Handrails](https://sihandrails.com/blogs/article/how-is-wrought-iron-made-the-traditional-process-explained)
- [Sulphur in Steels — IspatGuru](https://www.ispatguru.com/sulphur-in-steels/)
- [Hot Shortness — Corrosionpedia](https://www.corrosionpedia.com/definition/638/hot-shortness)
- [Emergence World: long-horizon multi-agent autonomy — arXiv 2606.08367](https://arxiv.org/html/2606.08367)
