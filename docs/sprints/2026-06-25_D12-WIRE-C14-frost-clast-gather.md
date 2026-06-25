# Sprint 2026-06-25 — D12 wire #3 : la boucle agent RAMASSE le gélifract (consomme C14)

> **Type :** `fix(cognition)` / câblage d'arc (pas une nouvelle capacité « Cap. CN »).
> **Exécute :** R-J14-1 (P0) de `SCHEDULED-TASK-2026-06-24-delta.md`. **Acte :** ADR-0009.
> **Suite de :** DRINK / C3 (`2d0ebd0`) et KNAP / C2 (`7d4c748`) — les 2 1ʳᵉˢ bouchées de D12.

## Veille (obligatoire, avant code)

5 axes. Découvertes retenues :
- **ALIFE 2026** (« Living and Lifelike Complex Adaptive Systems ») + **Project SID**
  (économies émergentes à 1000 agents, spécialisation par utilité, **sans planification
  centrale**) — confirment *frontalement* la voie ADR-0009 : sélection d'action **par
  utilité déterministe**, l'émergence comme processus, pas comme script. **Apport :
  validation de la direction, pas de pivot.**
- **JaxLife / Emergence World** — utility-based action selection sans LLM : compatible
  cargo-less + invariant sandboxing (ADR-0002). Le « cerveau LLM décisionnel » reste écarté.
- Bevy / WGPU / ML-KEM (Rust gelé ADR-0008, aucun endpoint réseau) → backlog / N/A.
- **CVE actives : aucune critique** (numpy / PCG64 clean ; pas de surface réseau créée).

**COMBO_RETENU :** `utility-based action selection (SID/JaxLife)` × `C14 cryoclasty` →
3ᵉ tranche verticale de consommation d'arc. **0 LLM, 0 dépendance nouvelle.** Couche
**Agentic**. Pas de nouvel ADR (ADR-0009 a déjà ratifié le patron ; ceci en est la 3ᵉ
application).

## Le problème (D12 / R0)

L'arc de 20 capacités n'a (encore) que **2/20** consommateurs agent (C3, C2). R-J14-1
réclamait une 3ᵉ capacité branchée par le patron canonique — de préférence **non-feu**
(alternance) et un **opérateur orthogonal** plutôt qu'un énième empilement.

## La tranche livrée

Dans `cognition.decide()`, sous les drives de survie, au-dessus de l'exploration
aléatoire : un agent **rassasié et curieux** qui **perçoit** (`cryoclasty.
best_frost_clast_near`, C14) un éboulis gélifracté de clasts taillables y marche et
**ramasse** (`ActionKind.GATHER`) — **sans percussion**, le gel a déjà détaché la
pierre. `apply_decision` ramasse les clasts de surface → `inv_stone` + un **tranchant**
(`inv_tools`) ∝ `clast_quality` *réelle* (= base C2 × réponse de gel du fabric) ; la
position entre en `EpisodicMemory.known_frost_clast_locations`.

**Ordre dans `decide()` :** `_seek_frost_clast` est essayé **avant** `_seek_toolstone`.
Là où le gel a fait le travail (clasts sains à ses pieds), **ramasser prime sur tailler**
(moindre effort) — voir `test_gather_preferred_over_knap_when_both_installed`.

### L'orthogonalité (GATHER ≠ KNAP)

- **KNAP / C2** = *casser* un affleurement (`collect_depth_m > 0`, percussion).
- **GATHER / C14** = *ramasser* un gélifract de surface (`collect_depth_m == 0`).
  7ᵉ verbe primitif. Les deux lisent la **même** géologie ; le gel les sépare.

### Le mensonge rendu visible #5 (l'éboulis trompeur)

« Un éboulis froid spectaculaire fait toujours de bons outils » → **FAUX** : sur
obsidienne / silex le gel trie des éclats-rasoir ; sur **granite** le même gel produit
de l'**arène stérile** (gruss, sable). L'agent ne l'apprend **qu'en ramassant**
(`workable == False` → tranchant ≈ 0). (« le monde ne ment jamais », étendu au comportement.)

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (pas de nouveau tell) | ✅ lit C14 (qui compose C2), `PY_TO_RUST` reste **15** |
| **D10** (mutation gelée à `geo.mine_at`) | ✅ GATHER = ramassage de surface, **0 mutation géologie** |
| **D9** (alternance feu/non-feu) | ✅ `fix(cognition)`, **non-feu** (D9 reste à 0) |
| **Hot-loop** | ✅ gate sur C14 déjà installé ; **jamais** d'`install_*` en tick |
| **Zéro-régression par construction** | ✅ `bootstrap_genesis_sim` n'installe **pas** C14 → wire **inerte** partout sauf si `install_cryoclasty` explicite (p153 / tous les autres smokes intacts) |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, **0 RNG nouveau** |
| **Émergence absolue** | ✅ aucun arbre tech ; le monde décide le rendement |

## Vérif

- `runtime/tests/test_frost_clast_gather_loop.py` — **10 tests** (gate, choix GATHER/WALK_TO,
  fall-back EXPLORE, rendement obsidienne>arène granite, site sans indice inerte,
  survie>ramassage, back-compat, **coexistence GATHER>KNAP**).
- `runtime/scripts/p155_frost_clast_gather_smoke.py` — **8/8** (boucle live perceive→decide→
  act→remember sur monde réel périglaciaire ancré argmax-FCI seed `0xB0` ; `sim.step()`
  propre ; gate + déterminisme ; discipline D8/D10).
- `pytest` complet **vert** (835 → **845** passed, 1 skipped) ; `ruff` clean (set de l'arc :
  +`test_frost_clast_gather_loop.py`) ; portail smoke CI étendu p154 → **p155**
  (`Makefile` + `ci.yml`).
- **Non-régression vérifiée live :** p153 (KNAP) **8/8**, p146 (cryoclasty) **8/8**,
  p154 (orographic) **8/8**, p86 (autonomous world) **PASS**.

> **Note d'implémentation :** comme pour KNAP, de nombreuses capacités réassignent
> globalement `cognition.decide`/`apply_decision` (wrappers sans teardown). Le wire vit
> dans les fonctions **originales** ; tests + smoke capturent les originaux à l'import
> pour rester déterministes (dette notée ADR-0009 §Conséquences → futur dispatch ordonné).

## Reste

17 capacités (C1, C4–C13, C15–C20) + piliers **langage**/**bâtiments** à brancher, même
patron, une tranche verticale à la fois. Registre de capacités à introduire au-delà de
quelques branchements. Moitié **hydro** de D11 (rivières peintes, `cross_chunk_*` stubs)
toujours ouverte (R-J14-3).
