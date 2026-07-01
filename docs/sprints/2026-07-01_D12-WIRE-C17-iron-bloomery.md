# Sprint 2026-07-01 — D12 wire #19 : la boucle agent RÉDUIT le fer (consomme C17)

> **Type :** `feat(agentic/cognition)` / câblage d'arc via le registre `_ARC_SEEKS`.
> **Acte :** [ADR-0010](../../adr/0010-agent-driven-mutation.md) (**2ᵉ franchissement de D10**, borné au
> sous-arc métallurgique — **pas de nouvel ADR**, on étend celui que C13 a posé). **Suite de :** C13
> SMELT (wire #18, la 1ʳᵉ mutation) et C1 PROSPECT (wire #17, la fondation cognitive).
> **19ᵉ bouchée → 19/20.** **LE SEUIL DE L'ÂGE DU FER, VÉCU.** Après le cuivre (C13), un agent produit
> ici le **2ᵉ métal** — mais le fer ne **coule jamais** : il est réduit à l'**état solide** en une
> **loupe** (bloom) spongieuse qu'il faudra **marteler** (C19). Le seuil sidérurgique **vécu**.

## Veille du jour (étape 0) → 0 combo externe intégrable, 1 combo interne majeur

Veille libre (axes IA/agents · ALife multi-agents · action-selection sans LLM · CVE stack Python). Le
substrat reste *cargo-less* / *no-LLM-brain* / *no-endpoint-nouveau* ([ADR-0008](../../adr/0008-python-rust-frontier.md)) →
les axes Rust/GPU sont gelés ; la veille utile se concentre sur artificial-life / world-models / la
capacité visée (archéométrie du bas-fourneau).

- **DÉCOUVERTE_1** — *Emergence World* (arXiv 2606.08367) & *AIvilization v0* (2602.10429), bancs
  long-horizon multi-agents. **Confirmés en COMBO_BACKLOG P5** (conditionnés à l'activation Phase 5 LLM
  tier-2). Aucune brique cargo-less intégrable en 7 j → aucune action code aujourd'hui.
- **DÉCOUVERTE_2** — *utility-based / rule-based action selection sans LLM* (WMAC 2026, AAAI bridge ;
  revue 2026). L'état de l'art confirme que la **sélection déterministe par règles/utilité** est la voie
  viable no-LLM — exactement le registre `_ARC_SEEKS` *first-actionable-wins* sous budget de perception
  ([ADR-0002](../../adr/0002-no-llm-brain.md)). **Conforte le patron, 0 code.**
- **DÉCOUVERTE_3 (capacité visée)** — archéométrie du bas-fourneau : réduction **solide-solide** du CO
  (Fe₂O₃ → Fe₃O₄ → FeO → Fe) à **1100–1300 °C** ; le fer **ne fond pas** (1538 °C), la scorie de
  **fayalite** s'écoule et laisse une **éponge**. Le chapeau **oxyde** (hématite) réduit sain ; le
  chapeau **pyriteux** doit être grillé et reste *red-short* ; le chapeau **plomb/zinc** ne rend aucun
  fer. **Exactement** la SSOT que `iron_bloomery` a déjà gravée (`iron_bloom_yield`). Sert de vérité-sol
  du « mensonge rendu visible ».
- **CVE_ACTIVES** — **CVE-2026-48710** (Starlette/FastAPI host-header bypass, correctif ≥ 1.0.1) : touche
  **la surface réseau** (extras `network`), **pas ce wire** (cognition pure, 0 endpoint). Noté pour
  l'extra `network`. **CVE-2026-25580** (SSRF Pydantic-AI) : **pydantic-ai non utilisé** (ADR-0002). Aucune
  action sur une surface Genesis touchée par ce wire.
- **PAPER_DU_JOUR** — 2606.08367 : applicable *conceptuellement*, **rien à intégrer sans LLM tier-2**.

**Combo retenu = INTERNE** : C17 `iron_bloomery` (substrat métallurgique testé, `bloom_at` mutant) × la
fondation cognitive de PROSPECT (le tell gossan) × l'appareil de FORCE_DRAUGHT (le four ≥ 1200 °C). C'est
**le** combo du jour : `known gossan == iron` (cognition) × `bloom_at` (mutation) = la **sidérurgie
vécue**. **ADR requis : NON** — on **étend** [ADR-0010](../../adr/0010-agent-driven-mutation.md) (le
sous-arc métallurgique que C13 a dégelé prévoyait déjà C17/C19).

| | |
|---|---|
| **COMBO_RETENU** | C17 `iron_bloomery` × la boucle cognitive (PROSPECT→FORCE_DRAUGHT→BLOOM) |
| **Gain** | +1 comportement agent mutant (le 2ᵉ) ; `inv_metal` réellement rempli d'une loupe de fer solide ; D12 19/20 |
| **Coût** | ~4 h · complexité 3 · risque régression 2 (D10 isolé au sous-arc métallurgique ; p173/p172 verts) |
| **Couche** | Agentic (cognition) × Substrate (C17) |
| **Intégration** | `_seek_bloom` + branche `BLOOM` d'`apply_decision` lisant `iron_bloomery.bloom_at` |
| **ADR** | [ADR-0010](../../adr/0010-agent-driven-mutation.md) — étendu (C13 cuivre → C17 fer, même sous-arc borné) |

## La tranche livrée — la première réduction du fer

Append d'une ligne au registre (`("bloom", _seek_bloom)` **après `smelt`** — la chaîne métallurgique se lit
`SMELT (cuivre) → BLOOM (fer)`). Contrairement à C13 (qui réutilisait le legacy `SMELT = 18`), ce wire
**crée un verbe neuf**, `ActionKind.BLOOM = 35` : la réduction du fer **n'est pas** la fonte du cuivre. Un
agent **survie-satisfait, curieux** qui :

1. a **découvert le tirage forcé** (`mem.has_forced_draught`, C12 — seul régime ≥ 1200 °C derrière une
   paroi réfractaire kaolin),
2. a **appris que le chapeau de fer rouille signifie fer** (`"gossan" in mem.prospected_ore_groups`,
   C1/PROSPECT — la **fondation cognitive de nouveau dépensée**, cette fois pour le fer),
3. **porte du charbon** (`inv_fuel ≥ BLOOM_FUEL_COST_KG = 1.0`, C4/GLEAN),

et qui **voit** un chapeau oxyde **directement réductible** (`iron_bloomery.best_bloomery_site_near`,
**`require_direct=True`**, rayon `BLOOM_PERCEPT_M = 96 m`) y va et **RÉDUIT** (`ActionKind.BLOOM`). Le
**monde** décide de la loupe (`iron_bloom_yield`) : le **chapeau oxyde** (hématite/magnétite) rend une
**éponge de fer saine** (~0,097 kg pour une charge de 5 kg d'hématite à 5 % dans un four à 1295 °C) ; **le
même chapeau** sur de la **pyrite** (sulfure) est **consommé** mais ne rend **que de la scorie** tant qu'il
n'est pas grillé — **le mensonge #8 vécu** ; le chapeau sur **galène/sphalérite** (plomb/zinc) ne rend
**aucun fer** (l'oracle refuse : pas de cue). **Auto-limité** : `mem.has_bloomed_iron` (l'âge du fer est un
**seuil** — on réduit **une fois** que du vrai fer est gagné, puis on s'arrête).

### Le MENSONGE PHYSIQUE — le fer ne coule jamais (vs le cuivre)

La différence métallurgique fondatrice : le **cuivre** FOND à 1085 °C et **coule** en un bouton qu'on
verse (C13) ; le **fer** fond à **1538 °C**, **hors d'atteinte** de tout bas-fourneau. Le fer est donc
réduit **à l'état SOLIDE** — l'événement `bloom` porte invariablement `is_solid_bloom = True`,
`required_roasting`/`red_short` selon le minerai, et **jamais** de bouton coulé. La **forge** (C19, le
martelage de consolidation) devient nécessaire et **émerge** de là. La fonte (fer liquide → haut-fourneau)
reste différée **honnêtement**.

### Le 2ᵉ franchissement de D10 — et l'honnêteté de l'inventaire

`bloom_at` appelle `geo.mine_at` : la charge de minerai **disparaît** de la colonne (`extracted_kg`
`0 → 5.0`). **C'est la 2ᵉ fois qu'un agent mute le monde**, dans le **même** sous-arc métallurgique borné
qu'ADR-0010 a ouvert. Comme pour SMELT, `geo.mine_at` porte le **pont Wave-1 legacy**
(`_credit_agent_inventory`) qui crédite la masse **brute** à `inv_metal` — faux pour une réduction. La
branche `BLOOM` **corrige** ce crédit : seule la **loupe récupérée** (`bloom_iron_kg`) entre en
`inv_metal`, la gangue + fayalite part en scorie ; `inv_stone` est restauré. La mutation géologique
(`extracted_kg`) n'est **pas** annulée — c'est l'acte D10. *(Verrue legacy notée en dette ADR-0010 §b,
identique à SMELT.)*

### Choix d'auto-limite — `has_bloomed_iron`, pas `inv_metal`-saturé (noté)

SMELT s'auto-limite sur `inv_metal ≥ SMELT_METAL_SATED_KG`. Réutiliser ce seuil pour le fer **mêlerait**
cuivre et fer dans le **même** `inv_metal` (un agent rassasié de cuivre ne réduirait jamais de fer). Choix
**délibéré** : BLOOM s'auto-limite sur le **drapeau de découverte** `has_bloomed_iron` (comme
FORCE_DRAUGHT/RAISE_KILN s'auto-limitent sur leur découverte d'appareil), **positionné uniquement quand du
vrai fer est gagné** (`bloom_iron_kg > 0`). Conséquences : (a) `inv_metal` reste **orthogonal** entre les
deux wires métallurgiques ; (b) un **échec honnête** (pyrite crue → scorie, ou galène → rien) ne
**verrouille pas** l'agent, qui peut réessayer un meilleur site. Décision asservie par les tests #8/#10.

## Nouveaux champs

**`AgentRegistry` :** aucun (réutilise `inv_metal`, `inv_fuel`, `inv_stone`). **`EpisodicMemory` :** quatre
champs — `known_bloom_locations: List[Tuple[float, float]]`, `has_bloomed_iron: bool`,
`last_bloom_mineral: Optional[str]`, `last_bloom_iron_kg: float`. **`ActionKind` :** un neuf,
`BLOOM = 35` (la réduction du fer ≠ la fonte du cuivre).

## Garde-fous tenus

- **D8 (cross-langage)** — compose C17 (qui compose C12 + C1), **0 nouveau tell** ; `iron_bloomery` n'a
  pas de `_PROFILE` ; `PY_TO_RUST` reste **15**. Asservi (wire test + p175 check 8).
- **D9 (alternance feu/non-feu)** — SMELT **et** BLOOM sont **feu** : la **queue métallurgique** de l'arc
  (C13→C17→C19) est **structurellement liée au feu** ; **aucune capacité non-feu ne reste** à intercaler
  (le « Reste » est C17 puis C19, tous deux feu). L'alternance **cède honnêtement** à la réalité de l'arc
  — noté, pas masqué.
- **D10 (mutation)** — **2ᵉ franchissement par design** ([ADR-0010](../../adr/0010-agent-driven-mutation.md)),
  **borné au même sous-arc métallurgique** ; une précondition gatée ne mute **aucune** géologie (test #4).
  Tous les autres wires restent non-mutants.
- **Déterminisme** — oracle pur/mémoïsé + `bloom_at` mute déterministiquement (même seed + colonne ⇒ loupe
  bit-identique : `0.097475` kg reproduit). Asservi (wire test + p175 check 7).
- **Zéro-régression par construction** — `genesis_bootstrap` **n'installe pas** `iron_bloomery` (vérifié) ;
  le wire est **inerte** partout sauf `install_iron_bloomery` explicite (gate sur `_iron_bloom_cue_cache`).
- **Hot-loop / ADR-0002** — lit un C17 **déjà installé** ; jamais d'`install_*` en tick ; try/except → None ;
  aucun cerveau LLM. Auto-limité.

## Couverture

- `runtime/engine/agent.py` — `ActionKind.BLOOM = 35` + 4 champs `EpisodicMemory`.
- `runtime/engine/cognition.py` — `_seek_bloom` + branche `BLOOM` d'`apply_decision` (correction du crédit
  Wave-1) + constantes `BLOOM_PERCEPT_M`/`BLOOM_FUEL_COST_KG` + entrée `_ARC_SEEKS`.
- `runtime/tests/test_iron_bloom_wire.py` — **16 tests** (gates C12/C1/C4, décision, WALK_TO, **le 2ᵉ
  franchissement D10**, la loupe **solide**, mensonge #8 sulfure + **non-verrouillage**, mensonge le plus
  profond plomb/zinc, auto-limite, monde-ne-ment-jamais, survie, back-compat, déterminisme, D8 + orthogonalité).
- `runtime/tests/test_arc_seek_registry.py` — registre à **18 entrées** (`bloom` inséré après `smelt`).
- `runtime/scripts/p175_iron_bloom_loop_smoke.py` — **8/8** sur seed `0x1201`.
- `Makefile` — lint-gate étendu à `test_iron_bloom_wire` ; smoke-gate étendu à `p175`.
- `.github/workflows/ci.yml` — liste de smokes **remise en miroir du Makefile** : ajout de `p172`, `p173`
  (oubliés par les runs précédents) **et** `p175`.

## Vérification (locale)

- `python -m pytest tests/test_iron_bloom_wire.py -q` → **16 passed**.
- `python -m pytest tests/test_arc_seek_registry.py -q` → **6 passed** (registre re-synchronisé).
- `python -m ruff check tests/test_iron_bloom_wire.py scripts/p175_iron_bloom_loop_smoke.py` → **clean**.
- `python scripts/p175_iron_bloom_loop_smoke.py` → **PASS 8/8** (BLOOM live ; `extracted 0→5` ; loupe
  solide 0,0975 kg ; déterministe).
- Non-régression : `p173_copper_smelt_loop_smoke.py` → **8/8** ; `p172_prospect_ore_loop_smoke.py` → **8/8**.
- La suite complète + tous les smokes seront rejoués par la CI GitHub au push (source de vérité).

## Recommandations / Reste

**1 capacité** reste : **C19 `bloom_forging`** — le **martelage** de la loupe (`bloom_forging` lit la
sortie de C17 : `inv_metal` fer + `red_short`) → fer forgé consolidé, la scorie chassée. Suivra le **même
patron ADR-0010** (SSOT audité + préconditions vécues : `has_bloomed_iron` + une enclume/percussion), et
**clôturera l'arc C1→C20 à 20/20**. Puis : les piliers **langage / bâtiments** (hors arc matériel).
Note dette : la verrue Wave-1 `_credit_agent_inventory` (corrigée en branche pour SMELT **et** BLOOM)
mériterait une correction à la source (`geo.mine_at`), tracée en ADR-0010 §b.
