# Sprint 2026-07-01 — D12 wire #18 : la boucle agent FOND le cuivre (consomme C13)

> **Type :** `feat(agentic/cognition)` / câblage d'arc via le registre `_ARC_SEEKS`.
> **Acte :** [ADR-0010](../../adr/0010-agent-driven-mutation.md) (**franchit D10**). **Suite de :** C1
> PROSPECT (wire #17, qui posait la fondation cognitive) et C12 FORCE_DRAUGHT (wire #16, l'appareil).
> **18ᵉ bouchée → 18/20.** **LA PREMIÈRE MUTATION DU MONDE PAR UN AGENT.** À travers 17 wires la boucle
> n'avait jamais touché la colonne géologique (D10 gelé, asservi par `g_before == g_after`). Ici un
> agent produit le **premier métal** : le seuil chalcolithique **vécu**.

## Veille du jour (étape 0, 5 axes) → 0 combo externe intégrable, 1 combo interne majeur

Veille libre (axes IA/agents · Rust/ECS · crypto/CVE · infra/data · arXiv). L'environnement reste
*cargo-less* / *no-LLM-brain* / *no-endpoint-nouveau* → les axes Rust/PQC/infra sont **gelés par
[ADR-0008](../../adr/0008-python-rust-frontier.md)** ; la veille utile se concentre sur artificial-life /
multi-agent / world-models.

- **DÉCOUVERTE_1** — *« Current Agents Fail to Leverage World Model as Tool for Foresight »*
  (arXiv 2601.03905) · couche **Agentic** · les agents échouent à *utiliser* un world-model comme outil
  de prévision. **Écho direct** au design Genesis : les *cues* véridiques de l'arc (`*_cue_for_chunk`,
  `best_*_near`) SONT un world-model interrogeable, et la boucle `perceive→decide` les consomme déjà.
  Gain : conforte le patron ADR-0009/0010, **pas de code** (déjà tagué `paper-L1 Predictor`).
- **DÉCOUVERTE_2** — *Emergence World* (arXiv 2606.08367) + *AIvilization v0* (2602.10429) · couche
  **Social** · bancs long-horizon multi-agents. Déjà en **COMBO_BACKLOG P5** (conditionnés à
  l'activation Phase 5 LLM tier-2). Aucune action aujourd'hui.
- **DÉCOUVERTE_3** — *« General agents contain world models »* (arXiv 2506.01622) · théorique ·
  soutient l'hypothèse H0 (un agent compétent contient implicitement un modèle du monde). Note de veille,
  pas de code.
- **CVE_ACTIVES** — aucune critique impactant une surface Genesis (runtime Python déterministe,
  mono-process, aucun endpoint réseau nouveau ce jour). Aucune action.
- **PAPER_DU_JOUR** — 2601.03905 (world-model-as-tool) : applicable *conceptuellement* mais **rien à
  intégrer dans les 7 jours** sans LLM tier-2.

**Combo retenu = INTERNE** : C13 `copper_smelting` (substrat métallurgique testé, `smelt_at` mutant)
× la fondation cognitive de PROSPECT (wire #17). C'est **le** combo du jour : `known green == copper`
(cognition) × `smelt_at` (mutation) = la **première métallurgie vécue**. **ADR requis : OUI** →
[ADR-0010](../../adr/0010-agent-driven-mutation.md) (franchir D10).

| | |
|---|---|
| **COMBO_RETENU** | C13 `copper_smelting` × la boucle cognitive (PROSPECT→FORCE_DRAUGHT→SMELT) |
| **Gain** | +1 comportement agent mutant (le 1ᵉʳ) ; `inv_metal` réellement rempli d'un bouton de cuivre ; D12 18/20 |
| **Coût** | ~4 h · complexité 3 · risque régression 2 (suite complète verte, D10 isolé au sous-arc métallurgique) |
| **Couche** | Agentic (cognition) × Substrate (C13) |
| **Intégration** | `_seek_smelt` + branche `SMELT` d'`apply_decision` lisant `copper_smelting.smelt_at` |
| **ADR** | [ADR-0010](../../adr/0010-agent-driven-mutation.md) — franchir D10 (la mutation pilotée-agent) |

## Décision — un ADR, parce qu'on franchit D10

Contrairement aux 17 wires précédents (tous non-mutants, `fix(cognition)` sans ADR), celui-ci **mute la
géologie** via `geo.mine_at` (dans `smelt_at`). C'est une décision architecturale : dégeler la frontière
D10 qu'[ADR-0009](../../adr/0009-agent-consumer-loop.md) posait explicitement. D'où
[ADR-0010](../../adr/0010-agent-driven-mutation.md), qui borne le dégel au **sous-arc métallurgique**
(C13 aujourd'hui ; C17 `bloom_at` / C19 suivront) et **préserve tous les autres garde-fous**.

## La tranche livrée — la première fonte

Append d'une ligne au registre (`("smelt", _seek_smelt)` **après `forcedraught`** — la chaîne des
appareils se lit `raise → force → SMELT`). Le wire **ne crée pas de verbe** : il rend **honnête** le
`ActionKind.SMELT = 18` legacy (comme C3 l'a fait pour DRINK). Un agent **survie-satisfait, curieux**
qui :

1. a **découvert le tirage forcé** (`mem.has_forced_draught`, C12 — seul régime ≥ 1085 °C),
2. a **appris que le vert signifie cuivre** (`"copper" in mem.prospected_ore_groups`, C1/PROSPECT — la
   **fondation cognitive du wire #17 est ici dépensée**),
3. **porte du charbon** (`inv_fuel ≥ SMELT_FUEL_COST_KG = 1.0`, C4/GLEAN),

et qui **voit** un site cuivre fondable (`copper_smelting.best_smelt_site_near`, rayon
`SMELT_PERCEPT_M = 96 m`) y va et **FOND** (`ActionKind.SMELT`). Le **monde** décide du bouton
(`copper_smelt_yield`) : le **cuivre natif** coule en métal (rendement ~0.95 à 1200 °C, bouton de
`0.2375 kg` sur une charge de `5 kg` à 5 % de teneur) ; **la même chalcopyrite** (sulfure réfractaire)
est **consommée** mais ne rend **que de la scorie** tant qu'elle n'est pas grillée — **le mensonge #4
vécu**. **Auto-limité** : `inv_metal ≥ SMELT_METAL_SATED_KG = 2.0` → l'agent ne re-fond plus.

### Le franchissement de D10 — et l'honnêteté de l'inventaire

`smelt_at` appelle `geo.mine_at` : la charge de minerai **disparaît** de la colonne
(`layer.extracted_kg` monte de `0 → 5.0`). **C'est la première fois qu'un agent mute le monde.**

`geo.mine_at` porte un **pont Wave-1 legacy** (`_credit_agent_inventory`) qui crédite la masse **brute**
(minerai + gangue) à `inv_metal`. C'est faux pour une fonte : le minerai est **réduit**, pas empoché
tel quel. La branche `SMELT` **corrige** ce crédit — seul le **bouton récupéré** (`recovered_cu_kg`)
entre en `inv_metal`, la gangue part en scorie ; `inv_stone` est restauré. La mutation géologique
(`extracted_kg`) n'est **pas** annulée — c'est l'acte D10. *(Verrue legacy notée en dette ADR-0010 §b.)*

## Nouveaux champs

**`AgentRegistry` :** aucun (réutilise `inv_metal`, `inv_fuel`). **`EpisodicMemory` :** quatre champs —
`known_smelt_locations: List[Tuple[float, float]]`, `has_smelted_copper: bool`,
`last_smelt_mineral: Optional[str]`, `last_smelt_cu_kg: float`. **`ActionKind` :** aucun nouveau
(réutilise `SMELT = 18`).

## Garde-fous tenus

- **D8 (cross-langage)** — compose C13 (qui compose C12 + C1), **0 nouveau tell** ; `PY_TO_RUST` reste
  **15**. Asservi (wire test + p173 check 8).
- **D9 (alternance feu/non-feu)** — SMELT est **feu** (le four) → **0→1** après le PROSPECT non-feu.
- **D10 (mutation)** — **FRANCHI par design** ([ADR-0010](../../adr/0010-agent-driven-mutation.md)),
  borné au sous-arc métallurgique. Tous les autres wires restent non-mutants (`g_before == g_after`).
- **Déterminisme** — oracle pur/mémoïsé + `smelt_at` mute déterministiquement (même seed + colonne ⇒
  bouton bit-identique). Asservi (wire test + p173 check 7).
- **Hot-loop** — lit un C13 **déjà installé** (gate sur `_copper_smelt_cue_cache`) ; jamais
  d'`install_*` en tick ; auto-limité.

## Couverture

- `runtime/engine/agent.py` — commentaire `SMELT`/D10 + 4 champs `EpisodicMemory`.
- `runtime/engine/cognition.py` — `_seek_smelt` + branche `SMELT` d'`apply_decision` (avec correction
  du crédit Wave-1) + constantes `SMELT_PERCEPT_M`/`SMELT_FUEL_COST_KG`/`SMELT_METAL_SATED_KG` + entrée
  `_ARC_SEEKS`.
- `runtime/tests/test_copper_smelt_wire.py` — **13 tests** (gates C12/C1/C4, décision, **le
  franchissement D10**, mensonge #4 sulfure, auto-limite, monde-ne-ment-jamais, survie, back-compat,
  déterminisme, D8).
- `runtime/tests/test_arc_seek_registry.py` — registre à **17 entrées** (`smelt` inséré après
  `forcedraught`).
- `runtime/scripts/p173_copper_smelt_loop_smoke.py` — **8/8** sur seed `0xC13`.
- `Makefile` — lint-gate + smoke-gate étendus à `p173` / `test_copper_smelt_wire`.
- `adr/0010-agent-driven-mutation.md` — l'ADR du franchissement.

## Reste

**2 capacités** (C17 `iron_bloomery` → `bloom_at`, C19 `bloom_forging`) + les piliers langage /
bâtiments. C17/C19 suivront le **même patron ADR-0010** (SSOT mutant audité + préconditions vécues).
