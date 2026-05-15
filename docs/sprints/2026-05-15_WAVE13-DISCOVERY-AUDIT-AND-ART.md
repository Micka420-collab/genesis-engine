# SPRINT 2026-05-15 — Wave 13 audit invariance + art discovery

**Règle invariante revisitée** : *"rien n'est scripté — ils doivent
découvrir par eux-mêmes : les outils, les matériaux, le langage, les
dessins, tout."*

**Statut** : ✅ livré
**Cible** : auditer la codebase, supprimer les scripts résiduels,
combler le pilier manquant (dessins/art).

---

## 1. Audit ligne-à-ligne sur 5 piliers

| Pilier | Verdict | Module pilote | Preuve d'émergence |
|---|---|---|---|
| **Outils** (axe, hache, contenant) | ✅ Émergent | `engine/invention.py` | `try_invent` = curiosité × intelligence × matériau_physique. Nom auto = `{material}_{function}` (`flint_cut`, `wood_bind`). Aucune table de recettes. |
| **Matériaux** | ✅ Émergent | `engine/geology.py` + `engine/metallurgy.py` | Minéraux réels extraits par `MINE`. Smelt = fourneau × combustible × pratique. Aucun "agent sait que silex = couper". |
| **Bâtiments** | ✅ Émergent (Wave 10e) | `engine/building_discovery.py` | Blocs + statics + fingerprint. Auto-nommage par culture. Aucune recette nommée. |
| **Langage** | ✅ Émergent | `engine/communication.py` + `agent.lexicon` | `lex_vector` 16-D dérive sur SPEAK, hérité à la naissance. `lexicon_to_phonemes` = renderer humain seul. `KIND_LABELS` = traductions FR pour affichage de `UtteranceKind` (intent, pas vocabulaire). |
| **Dessins / Art** | ❌ **Manquant** | (rien) | Aucune chaîne de découverte pour la création artistique. |

## 2. Violation résiduelle détectée et corrigée

**`engine/sim_5cd_integration.py::_seed_initial_project`** plantait
automatiquement un projet HEARTH par culture au démarrage de sim,
avec **matériaux pré-livrés**. C'est de la scénarisation.

Correction :
* Ajout du flag `SimConfig.scripted_hearth_seed: bool = False` (par
  défaut **OFF**).
* Le seeding scripté n'est exécuté que si la config l'active
  explicitement.
* `scripts/p0_smoke.py` (legacy regression de P-NEW.7) opt-in
  explicitement à ce flag, avec un commentaire indiquant que les
  nouveaux tests ne doivent **pas** s'en servir.

Tous les autres smokes restent verts sans ce flag — confirmation
empirique qu'ils ne dépendaient pas du hearth scripté.

## 3. `engine/art_discovery.py` (~330 LOC) — Wave 13

### Principe

L'engine décrit la **physique du pigment**, jamais un alphabet ou un
motif. L'agent fournit :
1. Un **pigment** (minéral marqueur : `hematite`, `graphite`,
   `manganese`, `kaolin`, `ochre`, `limonite`).
2. Une **surface** (`bedrock_calcite`, `bedrock_granite`,
   `bedrock_sandstone`, `ceramic`, `leather`, `wood`).
3. **N strokes** (≥ 3) — pure géométrie : `(x0, y0) → (x1, y1)`.

L'engine calcule un **fingerprint** :

```
(pigment, surface, n_strokes_class, dominant_orientation, closed?)
```

- `n_strokes_class` : bin par puissance de 2 (3-4, 5-8, 9-16, 17-32, 33-64).
- `dominant_orientation` : 8 classes cardinales (E, NE, N, …).
- `closed` : ≥ 30 % des strokes forment une boucle.

### Auto-nommage déterministe

```python
name = f"{pigment}_{ring|line}_{orientation}_{CVCV-suffix}"
```

CVCV-suffix dérivé de `prf_rng(seed, culture, fingerprint)`. Deux
cultures qui découvrent le même ring rouge en orientation W :
- Culture 0 → `hematite_ring_W_kune`
- Culture 1 → `hematite_ring_W_peki`

— exactement le pattern Lascaux vs Altamira : mêmes pigments
biologiques, motifs reconnaissables aux deux endroits, mais
**dénomination culturelle distincte**.

### Durabilité = pigment × surface

Calibration historique :
- hematite × bedrock_calcite = 0.85 × 0.95 = 0.81 (~Lascaux qui tient
  17 000 ans).
- charbon × bois = 0.75 × 0.40 = 0.30 (très éphémère).

### API

```python
install_art_discovery(sim) -> ArtDiscoveryState     # idempotent
begin_drawing(sim, row, pigment, surface)           # commit substrat
add_stroke(sim, row, x0, y0, x1, y1)                # accumule géom
complete_drawing(sim, row) -> (ok, art_id, name)    # fingerprint + name
abandon_drawing(sim, row) -> n_strokes              # discard
```

### Persistance

`save_art_state` / `load_art_state` ajoutés à `_PERSISTENT_MODULES`
dans `world_library.py`. SHA-256 du manifest reste intègre.

### Smoke `p40_art_discovery_smoke` **8/8 PASS**

```
[OK] step 1 — install idempotent
[OK] step 2 — unknown pigment rejected (moonstone)
[OK] step 3 — unknown surface rejected (glass)
[OK] step 4 — too few strokes rejected (2 < 3)
[OK] step 5 — closed ring archetype emerges (hematite_ring_W_kune)
[OK] step 6 — same culture, same fingerprint → same name (recognized)
[OK] step 7 — different culture → different name (hematite_ring_W_peki)
[OK] step 8 — ADR-0005 lists art_discovery OK
```

## 4. ADR-0005 → 19 modules requis taggés

```
engine.earth_loader / sim_lift / realism / physiology /
photosynthesis / material_aging / marine / global_world /
plant_evolution / meteorology / animal_evolution / agriculture /
writing / polity / geology / metallurgy / realistic_construction /
building_discovery / art_discovery (NEW)
```

`engine.art_discovery` : Genesis-L4 Feedback / paper-L2 Simulator.

## 5. Pré-requis Phase 5 — état

| Pré-req | État |
|---|---|
| 19 modules ADR-0005 taggés | ✅ (+1 art_discovery) |
| P-NEW.22 + .24 | ✅ |
| Wave 9d cognition wiring | ✅ |
| Wave 10b/c/d (mine/smelt/build) | ✅ |
| Wave 10e discovery-driven building | ✅ |
| Wave 11 elite metrics | ✅ |
| Wave 11 personality → polity | ✅ |
| **Wave 13 art discovery** | ✅ |
| Wave 12 10K sim-yr long-run | ⏳ |

**9/10** pré-requis Phase 5 livrés (long-run reste).

## 6. Non-régression

17 smokes (p23–p40) verts. `p0_smoke` vert après opt-in explicite au
flag legacy. `p24_long_run_stability` non exécuté (Wave 12 séparée).

## 7. Fichiers touchés

```
runtime/engine/art_discovery.py                                  (nouveau, ~330 LOC)
runtime/engine/sim.py                                            (+5 LOC : flag cfg)
runtime/engine/sim_5cd_integration.py                            (+6 LOC : gate hearth)
runtime/engine/world_library.py                                  (+1 LOC : persistent module)
runtime/engine/world_model_capabilities.py                       (+1 LOC : required module)
runtime/scripts/p0_smoke.py                                      (+7 LOC : opt-in legacy)
runtime/scripts/p40_art_discovery_smoke.py                       (nouveau, ~190 LOC, 8/8 PASS)
docs/sprints/2026-05-15_WAVE13-DISCOVERY-AUDIT-AND-ART.md        (ce fichier)
NEXT-SPRINT.md                                                   (Wave 13 archivé)
README.md                                                        (table modules + pré-requis)
```
