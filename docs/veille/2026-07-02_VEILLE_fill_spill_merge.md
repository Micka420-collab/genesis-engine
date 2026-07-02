# Veille technologique — 2026-07-02 (World Realism System v2.0, étape 0)

> Veille-first. Recherche **avant** toute ligne de code. Genesis est *cargo-less*
> (Python 3.14 / numpy seul, ADR-0008), *no-LLM-brain* (ADR-0002), déterministe.
> Un combo n'est « intégrable aujourd'hui » que s'il respecte ces trois contraintes
> **et** l'émergence pure (0 phénomène scripté — [feedback emergence-only]).
>
> Axe du jour : **Substrate / hydrologie** — suite directe du 2026-07-01. La
> fondation topographique (Priority-Flood, Wave 66) a livré les **contenants** ;
> aujourd'hui on promeut la `DÉCOUVERTE_2` déjà notée (Fill–Spill–Merge) en
> livrant sa **version volume-fini** : verser l'apport routé (Wave 64) dans ces
> contenants → lacs partiels, playas, salinité concentrée. **Additif read-only**
> (ne mute ni `river_discharge` ni `lake_hydrology`), garde-fou P5 respecté.

## Les 5 axes (routine matinale)

### Recherche 1 — IA & agents multi-LLM
- **Emergence World** (arXiv [2606.08367](https://arxiv.org/html/2606.08367)),
  **AIvilization v0** ([2602.10429](https://arxiv.org/pdf/2602.10429)) — bancs
  d'évaluation autonomie long-horizon (15 jours réels continus, modèle comme
  variable contrôlée). Pertinents pour la couche Social/Agentic mais **gated**
  (nécessitent Phase 5 LLM tier-2 — backlog P5 inchangé, déjà noté).
- **CAMO** ([2604.14691](https://arxiv.org/pdf/2604.14691)) — découverte causale
  automatisée micro→macro dans les simulations d'agents LLM. Voisin de
  l'observabilité d'émergence ; **gated** (LLM).

### Recherche 2 — Rust / ECS / moteur
- Bevy / WGPU : gated (P1 scaffolding Rust — `cargo` absent, ADR-0008). Backlog
  P5 inchangé.

### Recherche 3 — Cryptographie & sécurité
- Vuln python.org (release-mgmt API, 23 fév 2026) : hors-scope (l'arc n'a pas de
  surface réseau ; le module `network/` est isolé). Numpy-seul, pas de socket
  dans l'arc. **CVE_ACTIVES : aucune critique pour l'arc Substrate aujourd'hui.**

### Recherche 4 — Infra & data
- ClickHouse / NATS / Neo4j : gated (Observatory Phase 5+). Backlog P5 inchangé.

### Recherche 5 — Papers arXiv du jour + hydrologie
- **Fill–Spill–Merge** (Barnes, Callaghan & Wickert 2020/2021, *Earth Surface
  Dynamics* 9, 105 ; [ESurf](https://esurf.copernicus.org/articles/9/105/2021/) ;
  NSF [par.10263903](https://par.nsf.gov/servlets/purl/10263903) ; réf. C++
  [r-barnes/Barnes2020-FillSpillMerge](https://github.com/r-barnes/Barnes2020-FillSpillMerge)).
  Routage volume-fini dans une **hiérarchie de dépressions** : le ruissellement
  remplit une dépression, **déborde** (spill) sur sa voisine, et deux dépressions
  pleines **fusionnent** (merge). Log-linéaire. Produit des lacs **partiellement**
  remplis → endoréisme quand apport < capacité. **Applicable directement** :
  numpy + le routage déterministe déjà présent (Wave 64 `route_runoff`).
  → **COMBO_TODAY**.
- **Priority-Flood modifié / hash-heap** (T&F 2026,
  [19475683.2026.2617191](https://www.tandfonline.com/doi/full/10.1080/19475683.2026.2617191))
  — variante d'efficacité de PF. **Non nécessaire** : Wave 66 (numpy+heapq) suffit
  à la résolution 64² du substrat. Noté, non intégré.

## Validation « rien de plus récent ne supplante le plan »
FSM (2021) reste **l'algorithme de référence** pour distribuer un apport fini dans
une hiérarchie de dépressions. La littérature 2025-2026 sur l'endoréisme (≈ 20 %
des terres) **valide l'importance** des lacs terminaux / playas mais **ne supplante
pas** FSM. Plan **actuel et sain** — Wave 66 (contenants) → Wave 67 (remplissage).

## SYNTHÈSE VEILLE (format obligatoire)

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-07-02"
  duree_recherche: "~20 min"

  decouvertes:
    - id: D1
      techno: "Fill–Spill–Merge (Barnes/Callaghan/Wickert 2021) — remplissage volume-fini"
      source: "https://esurf.copernicus.org/articles/9/105/2021/"
      telecharge: false   # algorithme réimplémenté numpy (pas de dépendance)
      applicable_a: "Substrate/hydrologie — verse Wave 64 (discharge routé) dans les contenants Wave 66"
      gain_estime: "réalisme: lacs PARTIELS, playas (bassin affamé), sel concentré — ÉMERGENTS"
      action: "COMBO_TODAY"

    - id: D2
      techno: "Emergence World / AIvilization v0 (bancs autonomie long-horizon)"
      source: "https://arxiv.org/html/2606.08367"
      telecharge: false
      applicable_a: "Social/Agentic — métriques d'émergence long-horizon"
      gain_estime: "comparaison externe d'internalisation du contrat social"
      action: "BACKLOG_ROADMAP"   # gated Phase 5 LLM tier-2 (déjà au backlog P5)
      raison_si_rejet: "n/a (différé)"

  cve_stack:
    - "aucune CVE critique pour l'arc Substrate (numpy-seul, no-socket, no-LLM)"

  paper_du_jour:
    titre: "Computing water flow through complex landscapes — Part 3: Fill–Spill–Merge"
    url: "https://esurf.copernicus.org/articles/9/105/2021/"
    technique: "verser un apport routé dans une hiérarchie de dépressions: fill → spill over sill → merge; remplissage hypsométrique (le niveau où Σ max(h-eᵢ,0)·A == V)"
    effort: "~4 h · complexité 3/5 (additif, déterministe, mais couple 2 modules testés en lecture)"

  combo_retenu:
    techno: "Fill–Spill–Merge finite-volume fill"
    cible: "nouveau module engine.fill_spill_merge (Wave 67) — read-only sur world.elevation_m + flow_dir + climat"
    gain: "lacs partiels/full-spill, playas, salinité concentrée (capacité/eau), spectre monotone selon la fenêtre d'apport — tous émergents"
    adr_requis: false   # observateur additif pur, non-mutant, pas de nouvelle frontière PY_TO_RUST
```

## Décision COMBO (étape 1)

| Question | Réponse |
|---|---|
| REMPLACE ou ÉTEND ? | **ÉTEND** — nouveau module additif ; réutilise `priority_flood_fill`/`_label_components` (Wave 66) + `route_runoff`/`runoff_field_m3s` (Wave 64) en **lecture seule**. Ne modifie **aucun** module testé (garde-fou P5 respecté). |
| Combinaison multiplicatrice ? | Oui : Wave 66 donnait les *cuvettes à extension max* (indiscernables — un playa désertique et un lac alpin plein se ressemblent pour Priority-Flood). Wave 64 route l'apport réel mais le traite comme « quittant le domaine » aux puits. Wave 67 **verse l'un dans l'autre** → le monde décide enfin *combien* d'eau chaque cuvette retient. |
| Gain physique mesurable ? | Réalisme +2 (lacs vivants + playas) ; +1 type de forme émergente (playa/salt-pan) ; invariants testables : volume-fini ne déborde **jamais** la capacité ; surface partielle **plane** ; spectre **monotone** selon la fenêtre d'apport ; salinité ∝ 1/remplissage ; 0 violation causale (read-only). |
| Coût honnête ? | ~4 h · complexité 3/5 · risque régression **1/5** (module additif, aucun code testé modifié — vérifié par la suite pytest complète) · ADR **non requis**. |

**COMBO_RETENU** : Fill–Spill–Merge → `engine.fill_spill_merge` (Wave 67),
observateur read-only, déterministe, émergent, cargo-less. Livré ce jour avec
18 tests + smoke `p177` 8/8 + doc veille FR. **Reste Wave 68** : la cascade
inter-bassins (router l'`overflow_m3` d'une cuvette pleine vers la cuvette
avale → séquence spill→merge dynamique le long de la hiérarchie de dépressions).
