# WORLD_VEILLE_REPORT — 2026-06-28

> Routine `genesis-engine--world-realism-system-v20`, run autonome (user absent).
> Ordre imposé : **VEILLE → COMBO → DÉCISION → CODE → PUSH**. Ce rapport est le
> livrable de l'ÉTAPE 0 ; le code livré aujourd'hui en découle (§ COMBO_RETENU).

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-28"
  duree_recherche: "~15 min (3 requêtes ciblées + lecture résumés)"

  contexte_env: |
    Environnement = Python 3.14 SEUL, AUCUN cargo/rustc (cf. reference_env_no_cargo).
    ADR-0008 gèle le substrat Rust (Wave 42) ; runtime/engine Python = couche de
    simulation/perception active. Toute « techno GPU/WGSL/crate » de la veille est
    donc, au mieux, BACKLOG (session cargo), jamais COMBO_TODAY.

  decouvertes:
    - id: D1
      techno: "JaxWildfire — GPU-accelerated wildfire simulator for RL (JAX)"
      source: "arxiv.org/abs/2512.06102"
      telecharge: false
      applicable_a: "engine.wildfire (propagation Rothermel spontanée, Wave 14)"
      gain_estime: "perf ×10 sur la propagation — MAIS JAX/GPU, hors env cargo-less Python-pur"
      action: "REJETÉ"
      raison_si_rejet: |
        JAX non installé, pas de GPU exploitable dans l'env de routine ; nous avons
        déjà une propagation Rothermel (engine.wildfire). Aucun gain de RÉALISME, que
        de la perf, sur un sous-système non sur le chemin agent. Hors-scope aujourd'hui.

    - id: D2
      techno: "Highly Parallel Forest-Fire Propagation on GPU (Rothermel CUDA, 64–229×)"
      source: "cse.unr.edu/~fredh/papers/conf/162-hpioffpmotg/paper.pdf ; ieeexplore 7568432"
      telecharge: false
      applicable_a: "engine.wildfire"
      gain_estime: "perf"
      action: "BACKLOG_ROADMAP"
      raison_si_rejet: "CUDA → session GPU/cargo. Noté pour la file 'session cargo' (Phase A5 erosion/GPU)."

    - id: D3
      techno: "JaxLife — open-ended agentic simulator (agents NN évoluent culture + outils)"
      source: "arxiv.org/abs/2409.00853"
      telecharge: false
      applicable_a: "boucle agent (ADR-0009, campagne D12)"
      gain_estime: "validation d'architecture (pas une techno à intégrer)"
      action: "COMBO_TODAY (validation, pas intégration)"
      raison_si_rejet: ""

    - id: D4
      techno: "Project Sid (Minecraft, 500 agents) ; AIvilization v0 ; SimWorld"
      source: "arxiv 2411.00114 ; 2602.10429 ; 2512.01078"
      telecharge: false
      applicable_a: "thèse moteur : civilisations émergentes multi-agents"
      gain_estime: "validation de la thèse 'la techno doit être VÉCUE, pas scriptée'"
      action: "BACKLOG_ROADMAP"
      raison_si_rejet: "Tous LLM-driven (gated env cargo-less + sandbox). Confortent la direction, n'apportent pas de brique intégrable aujourd'hui."

  cve_stack:
    - "aucune CVE critique remontée aujourd'hui sur le stack Python actif (numpy 2.4.4, pytest 9.x)."

  paper_du_jour:
    titre: "JaxLife: An Open-Ended Agentic Simulator (Nisioti et al.)"
    url: "arxiv.org/abs/2409.00853"
    technique: |
      Des agents incarnés (réseaux de neurones) ÉVOLUENT pour accumuler une culture
      et des technologies open-ended à travers les générations (communication
      rudimentaire, agriculture, USAGE D'OUTILS émergent). Conclusion transposable :
      une capacité technologique n'a de valeur que si la BOUCLE AGENT la VIT — la
      prouver « possible » dans une lib ne suffit pas. C'est exactement le diagnostic
      D12/R0 de notre AUDIT-DELTA-2026-06-23 et la justification de la campagne
      ADR-0009 (brancher l'arc C1→C20 dans perceive→decide→act→remember).
    effort: "0 h d'intégration (validation) — confirme la priorité D12 du jour"

  world_model_updates:
    cosmos: "aucune nouveauté intégrable (gated)"
    genie3: "aucune nouveauté intégrable (gated)"
    autre: "SimWorld (Unreal) — moteur lourd, hors env ; aucun apport intégrable"

  combo_retenu:
    techno: "Aucune techno externe — combo INTERNE validé par la veille (D3/D4)"
    cible: "engine.cognition : brancher C7 fire_ignition dans la boucle agent (ActionKind.IGNITE)"
    gain: |
      RÉALISME COMPORTEMENTAL : la VOÛTE de l'arc (le feu) cesse d'être seulement
      'prouvée possible' et devient VÉCUE — un agent curieux/frileux perçoit un
      firestone, frappe une étincelle (percussion pyrite+percuteur OU friction
      amadou sec), se réchauffe (drive thermique baisse) et APPREND (has_made_fire).
      6ᵉ bouchée de D12/R0 ; +1 type de découverte agent ; 0 régression (gate sur
      cache C7, branche curiosité sous survie satisfaite → aucun impact mort-en-masse).
    couche: "Agentic (sur substrat Substrate inchangé)"
    adr_requis: false   # couvert par ADR-0009 (agent-consumer-loop) — pas de décision archi nouvelle
    estimation: "réalisé (≈ session)"

  combo_backlog:
    - "D2 (Rothermel GPU CUDA) → file 'session cargo' / Phase A5."
  combo_rejete:
    - "D1 (JaxWildfire) : JAX/GPU hors env, déjà couvert par engine.wildfire ; perf-only."
```

## Décision

Conforme à la **RÈGLE D'OR** (pas de code avant veille terminée) : la veille ne
fournit **aucune** brique externe intégrable dans l'environnement cargo-less /
ADR-0008 (constat stable, cf. mémoire). Elle **valide** en revanche la priorité
interne **D12/R0** (la techno doit être *vécue* — JaxLife, Project Sid). Le combo
retenu est donc **interne** : le 6ᵉ branchement de l'arc dans la boucle agent, et
le plus important — **le feu (C7)**, la voûte qui rendra ensuite *actionnables* la
métallurgie (C1/C13/C17), la cuisson (C9), la calcination (C10), le four (C11/C12).

**Livré ce jour** (le monde est « plus vrai ce soir » au sens comportemental) :
`ActionKind.IGNITE` + `cognition._seek_firesite` + bloc d'application + mémoire de
feu (`has_made_fire`/`last_fire_method`/`known_firesite_locations`). 11 tests +
smoke **p161** 8/8, suite pytest verte, ruff propre sur les fichiers neufs. Voir
`ROADMAP.md` (section ADR-0009) et la mémoire projet du jour.
