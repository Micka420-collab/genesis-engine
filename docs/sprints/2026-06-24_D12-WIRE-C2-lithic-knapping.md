# Sprint 2026-06-24 — D12 wire #2 : la boucle agent TAILLE la pierre (consomme C2)

> **Type :** `fix(cognition)` / câblage d'arc (pas une nouvelle capacité « Cap. CN »).
> **Exécute :** R-J13-1 (P0) de `AUDIT-DELTA-2026-06-23.md`. **Acte :** ADR-0009.
> **Suite de :** DRINK / C3 (R-J13-4, `2d0ebd0`) — la 1ʳᵉ bouchée de D12.

## Veille (obligatoire, avant code)

5 axes. Découvertes retenues :
- **Generative Agents (Stanford) + Project SID** — la boucle `perceive→memory→retrieve→
  choose→act` est *exactement* le chaînon manquant de D12. **Apport direct.**
- **JaxLife / Emergence World** — *utility-based action selection* déterministe (sans
  LLM) : compatible cargo-less + invariant sandboxing (ADR-0002) + émergence absolue.
- Bevy 0.16/0.19 (Rust gelé ADR-0008 → backlog), ML-KEM-768 (aucun endpoint créé → N/A).
- **CVE actives : aucune critique** (numpy/PCG64 clean).

**COMBO_RETENU :** `squelette perceive→act→memory (SID)` × `arc C1→C20` → boucle agent
déterministe dirigée par besoins. **0 LLM, 0 dépendance.** Couche **Agentic**. ADR-0009.

## Le problème (D12 / R0)

L'arc de 20 capacités ne se composait que lui-même ; **aucun agent ne l'invoquait**.
La découverte était *prouvée* (tests + smokes) mais jamais *vécue* dans une boucle.

## La tranche livrée

Dans `cognition.decide()`, sous les drives de survie, au-dessus de l'exploration
aléatoire : un agent **rassasié et curieux** qui **perçoit** (`lithic_outcrop.
best_toolstone_near`, C2) un affleurement taillable y marche et le **taille**
(`ActionKind.KNAP`). `apply_decision` débite l'affleurement → `inv_stone` + un
**tranchant** (`inv_tools`) ∝ `knap_quality` *réelle* du cue ; la position entre en
`EpisodicMemory.known_toolstone_locations`. **1ᵉʳ remplisseur de `inv_tools` de l'arc.**

### Le mensonge rendu visible #12 (le caillou trompeur)
« Une pierre dure d'aspect tranchant fait toujours un bon outil » → **FAUX** :
obsidienne (verre conchoïdal) → rasoir ; bloc à meule (granite) → tranchant médiocre ;
site stérile (carbonate tendre, **pas d'indice**) → **rien**, non mémorisé. L'agent ne
l'apprend **qu'en agissant**. (« le monde ne ment jamais », étendu au comportement.)

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (pas de nouveau tell) | ✅ lit C2, `PY_TO_RUST` reste **15** (composition) |
| **D10** (mutation gelée à `geo.mine_at`) | ✅ KNAP = ramassage de surface, **0 mutation géologie** |
| **D9** (alternance feu/non-feu) | ✅ `fix(cognition)`, pas une Cap. — non-feu |
| **Hot-loop** | ✅ gate sur C2 déjà installé ; **jamais** d'`install_*` en tick |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, **0 RNG nouveau** |
| **Émergence absolue** | ✅ aucun arbre tech ; le monde décide le rendement |

## Vérif

- `runtime/tests/test_lithic_knapping_loop.py` — 9 tests (gate, choix KNAP/WALK_TO,
  rendement ∝ qualité obsidienne>granite, site stérile inerte, survie>taille, back-compat).
- `runtime/scripts/p153_lithic_knapping_smoke.py` — **8/8** (boucle live perceive→decide→
  act→remember sur monde réel ; `sim.step()` propre ; gate + déterminisme ; discipline D8/D10).
- `pytest` complet **vert** ; `ruff` clean (modules/tests/smoke de l'arc) ; portail smoke
  CI étendu p152 → **p153** (`Makefile` + `ci.yml`).

> **Note d'implémentation :** de nombreuses capacités réassignent globalement
> `cognition.decide`/`apply_decision` (wrappers sans teardown). Le wire vit dans les
> fonctions **originales** ; tests + smoke capturent les originaux à l'import pour rester
> déterministes (dette notée ADR-0009 §Conséquences → futur dispatch ordonné).

## Reste

18 capacités (C1, C4–C20) + piliers **langage**/**bâtiments** à brancher, même patron,
une tranche verticale à la fois. Registre de capacités à introduire au-delà de quelques
branchements.
