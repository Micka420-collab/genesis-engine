# WORLD_VEILLE_REPORT — 2026-06-18 (`forced_draught` / Cap. C12)

> Étape 0 obligatoire **avant tout code** (Morning Routine v3.0). Run automatique,
> *user absent*. Veille → Combo → Décision → Code → Push. La veille de C11
> (`2026-06-17`, run #2) avait **explicitement backloggé** la suite (D3 : « Tirage
> forcé (soufflet) + charbon de bois → régime métallurgique »,
> `vitrifies_if_forced_draught`). Ce run la **réalise**.

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-18"
  duree_recherche: "~18 min"
  contexte_env: "Python 3.14 SEUL — pas de cargo/rustc (cf. reference_env_no_cargo)."
  contrainte: >
    Toute découverte GPU/Rust/Bevy/WGSL/PQC/Kubernetes est, par construction, NON
    intégrable aujourd'hui (pas de compilateur Rust, pas de cluster ici). Classée
    BACKLOG_ROADMAP, jamais COMBO_TODAY. Le combo du jour DOIT être Python-pur,
    déterministe, cargo-less, sans dépendance réseau.
```

## Découvertes (5 axes de la routine)

```yaml
  decouvertes:
    - id: D1
      axe: "AXE 3+5 — archéométrie du bas-fourneau (bloomery) & tirage forcé"
      techno: "Soufflet + tuyère → 1100–1300 °C ; air injecté ~5 s/coup, flux constant"
      source: "EXARC issue-2020-2 (bloomery furnaces) ; MDPI Heritage 8(12):512 (2025, mobile furnace shaft) ; Springer s12520-022-01516-3 (decision-making in bloomery smelting) ; historicalmetallurgy.org datasheet 301"
      telecharge: false
      applicable_a: "Substrate · thermodynamique du tirage FORCÉ (Cap. C12)"
      gain_estime: "réalisme +1 palier pyrotechnologique (l'air forcé élève la pointe) ; RÉALISE la vitrification (C9/C11 différée) + OUVRE la métallurgie"
      action: COMBO_TODAY
      note: >
        L'air est injecté par tuyère via soufflet juste au-dessus du sol → 1200 °C
        atteints rapidement à la base ; expériences EXARC/MDPI 2025 : parois en
        argile + sable + paille, 1100–1300 °C via soufflage. Un flux STABLE et
        constant améliore la réduction. CONFIRME et étend la SSOT C11
        (kiln_peak_temp_c ≤1150) : le tirage forcé pousse la pointe +250 °C,
        plafonnée par la réfractarité de paroi (commune ~1100 / réfractaire ~1400).

    - id: D2
      axe: "AXE 5 (papers) + AXE 3 — métallurgie du cuivre chalcolithique"
      techno: "Malachite + charbon de bois + ~1100–1200 °C → cuivre + scorie vitreuse"
      source: "Belovode (Serbie) ~5000 av. J.-C. — slag/crucible/furnace ; Biblical Archaeology (Chalcolithic copper smelting) ; NCBI PMC10989616 (Kunal copper slags) ; thearchaeologist.org (first metalworkers)"
      telecharge: false
      applicable_a: "Substrate · l'OUVERTURE métallurgie (compose le tell cuivre C1)"
      gain_estime: "le seuil chalcolithique (premier métal) devient un POTENTIEL ground-truthé, honnête, différé pour la fonte effective (C13)"
      action: COMBO_TODAY
      note: >
        Fusion du cuivre 1085 °C ; réduction de la malachite (carbonate vert, le
        tell de surface C1) au charbon en petit four ~1100–1200 °C ; scorie noire
        VITREUSE (refroidie lentement à l'air) = la signature visible du smelting.
        Le four à tirage forcé est exactement le régime qui franchit ce seuil. La
        FONTE effective (consommer le minerai → bouton de cuivre) reste C13.

    - id: D3
      axe: "AXE 1 — multi-agent LLM simulation & émergence 2026"
      techno: "Project Sid (1000 agents, propagation culturelle), OASIS (1M agents X/Reddit), generative agents 85% fidélité"
      source: "arxiv 2411.00114 (Project Sid) ; arxiv 2507.19364 (LLM in ABM) ; arxiv 2509.03736 (behavioral coherence)"
      telecharge: false
      applicable_a: "couche Agentic / Social (cognition des agents)"
      gain_estime: "architectures de mémoire/coordination pour quand les agents consommeront les affordances de substrat"
      action: BACKLOG_ROADMAP
      raison_si_rejet: "Genesis est en âge de pierre émergent (substrat d'abord) ; brancher des LLM-agents = travail couche Agentic (ADR-0002/0008), pas le combo substrat cargo-less du jour."

    - id: D4
      axe: "AXE 5 — artificial life / world models 2026"
      techno: "ASAL (foundation models pour ALife : Lenia/Particle Life/NCA), Cosmos-style world models"
      source: "arxiv 2412.17799 (Automating ALife search) ; arxiv 2509.22447 (VLM-guided ALife) ; 2026.alife.org"
      telecharge: false
      applicable_a: "Substrate SYSTÈME G (recherche de mondes émergents)"
      gain_estime: "méthodo de recherche de substrats émergents (piste future)"
      action: BACKLOG_ROADMAP
      raison_si_rejet: "GPU/poids requis ; pas d'implémentation cargo-less prête ; à relire pour roadmap Phase A/B."

    - id: D5
      axe: "AXE 4 — déterminisme & reproductibilité (best practices 2026)"
      techno: "Seed unique au démarrage, jamais dans les boucles ; documenter le seed ; éviter le fork-reseed"
      source: "blog.scientific-python.org/numpy/numpy-rng ; Isaac Lab reproducibility docs"
      telecharge: false
      applicable_a: "discipline projet (prf_rng / seed unique — DÉJÀ en place)"
      gain_estime: "confirme la discipline existante (RNG dérivé du seed, 0 RNG nouveau par capacité)"
      action: CONFIRME_PRATIQUE
      note: >
        La pratique Genesis (prf_rng dérivé du seed, aucune capacité n'introduit de
        RNG nouveau, bit-identité same-seed asservie par test) EST l'état de l'art
        2026. C12 la respecte : composition pure de C11+C1, 0 RNG nouveau.

  cve_stack:
    - "AXE 3 (CVE) : aucune CVE critique sur le stack runtime Python (numpy/pytest) aujourd'hui ; les CVE Rust/tokio/gRPC/Kubernetes ne concernent pas le runtime cargo-less actuel (Rust gelé Wave 42, ADR-0008)."

  paper_du_jour:
    titre: "Experimental insights into bloomery furnaces / Chalcolithic copper smelting at Belovode"
    url: "https://exarc.net/issue-2020-2/ea/development-bloomery-furnaces ; https://www.biblicalarchaeology.org/daily/ancient-cultures/ancient-israel/how-to-smelt-chalcolithic-copper/"
    technique: >
      Le tirage FORCÉ (soufflet/tuyère) + le charbon de bois portent un four enclos
      de 1000–1150 °C (tirage naturel, C11) à 1100–1400 °C (régime du bas-fourneau) :
      assez pour vitrifier le kaolin réfractaire (céramique étanche) et fondre le
      cuivre (1085 °C). On encode `forced_draught_peak_c(fine_fuel, wall_refractory)`
      = pointe du four C11 + gain du soufflet, plafonnée par la paroi.
    effort: "~4 h · complexité 3"

  combo_retenu:
    techno: "Thermodynamique du tirage forcé (D1) × métallurgie du cuivre chalcolithique (D2)"
    cible: "nouveau module engine/forced_draught.py (Cap. C12) — l'apparatus 'soufflet + charbon'"
    gain: >
      RÉUTILISE VERBATIM la SSOT C11 `kiln_peak_temp_c` (le four naturel = base),
      AJOUTE le gain du tirage forcé plafonné par la réfractarité de paroi, et
      RECOMPOSE C9 à la nouvelle pointe pour RÉALISER la vitrification (C9/C11
      différée → `vitrifies_watertight` enfin True) et OUVRE la métallurgie en
      composant le tell cuivre de C1 (`would_smelt_copper_here`). Effet 1+1>2 : le
      four forcé ne se fait que là où un four (C11) ET assez de combustible-charbon
      coexistent ; il réalise la vitrification ET ouvre la fonte du cuivre.
    adr_requis: false   # apparatus = lecture dérivée du substrat ; ADR-0005/0008 inchangés
    garde_fou_D8: "par COMPOSITION (6ᵉ fois après C7/C8/C9/C10/C11) — aucun nouveau tell, PY_TO_RUST reste 15, hors glob *_outcrop.py."
```

## Décision

**COMBO_TODAY = Cap. C12 `forced_draught`** — l'apparatus *tirage forcé* (soufflet +
charbon de bois) : un four enclos (C11) alimenté en charbon et **soufflé** atteint une
pointe **plus haute** (~1100–1400 °C), **calculée** (D1) et **plafonnée par la
réfractarité de la paroi**. Il **RÉALISE** le potentiel différé de C9 *et* C11
(`vitrifies_if_forced_draught` → `vitrifies_watertight` enfin True pour le kaolin
réfractaire — l'arc « mensonge du kaolin C9 → paroi C11 → vitrification C12 » se
ferme), et il **OUVRE** la métallurgie : `reaches_copper_smelting_temp` (≥1085 °C) ×
`copper_ore_here` (tell vert C1) → `would_smelt_copper_here` (D2). Il **ouvre** la
marche différée suivante, honnête : la **fonte effective** du métal (C13) et le
**bas-fourneau du fer** (`reaches_iron_bloomery_temp`, paroi réfractaire requise).

Tout reste **émergent** : on n'apprend pas à l'agent à « souffler sur du charbon pour
fondre le métal ». On expose le **fait physique véridique** — un four de charbon soufflé
monte plus haut, vitrifie la céramique et fait suinter le cuivre de la pierre verte — et
l'agent **découvre** le tirage forcé en agissant. Soufflet, tuyère, charbonnage en meule,
coulée restent émergents.

**Décisions BACKLOG/REJET** : multi-agent LLM (Project Sid/OASIS, D3), world models /
ALife foundation models (D4), toute techno GPU/Rust/PQC/Kubernetes → BACKLOG_ROADMAP
(cargo-less + hors substrat, cf. `reference_env_no_cargo`, ADR-0008). Best-practices
déterminisme (D5) → déjà respectées.

## Sources (veille du jour)

- Bloomery / tirage forcé : [EXARC 2020-2](https://exarc.net/issue-2020-2/ea/development-bloomery-furnaces) · [MDPI Heritage 8(12):512 (2025)](https://www.mdpi.com/2571-9408/8/12/512) · [Springer s12520-022-01516-3](https://link.springer.com/article/10.1007/s12520-022-01516-3) · [HMS datasheet 301](https://historicalmetallurgy.org/media/l5dh3df0/hmsdatasheet301.pdf)
- Métallurgie du cuivre : [Biblical Archaeology — Chalcolithic copper](https://www.biblicalarchaeology.org/daily/ancient-cultures/ancient-israel/how-to-smelt-chalcolithic-copper/) · [NCBI PMC10989616 (Kunal slags)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10989616/) · [Grokipedia — Smelting](https://grokipedia.com/page/Smelting)
- Multi-agent / ALife : [arxiv 2411.00114 (Project Sid)](https://arxiv.org/html/2411.00114v1) · [arxiv 2412.17799 (ASAL)](https://arxiv.org/html/2412.17799v1) · [arxiv 2507.19364](https://arxiv.org/pdf/2507.19364)
- Déterminisme : [scientific-python.org — NumPy RNG](https://blog.scientific-python.org/numpy/numpy-rng/) · [Isaac Lab reproducibility](https://isaac-sim.github.io/IsaacLab/main/source/features/reproducibility.html)
