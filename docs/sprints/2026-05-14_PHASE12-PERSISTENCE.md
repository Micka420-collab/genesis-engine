# SPRINT 2026-05-14 — P1 persistence (world-generator roadmap)

**Priorité attaquée**: P1 du roadmap "real virtual world generator" —
persistance disque complète. Le `world_library.py` existant ne sauvait
qu'une fraction de l'état (agents + chunks), perdant silencieusement
physio/photo/aging/material_registry sur save→load.

**Statut**: ✅ livré
**Cible**: round-trip bit-identique pour Wave 1-4, vérifiable par smoke.

---

## Ce qui manquait avant ce sprint

`save_world(world)` écrivait :
- `manifest.json` (builder config + sim.tick + atmosphere co2)
- `agents.npz` (subset de 30 champs)
- `chunks/*.npz` (height, biome, stone, wood, metal, water, food, capacity)

`save_world(world)` ne sauvait **pas** :
- ❌ physiology — bladder/bowel/hygiene/disease loads/melanin/...
- ❌ photosynthesis — global GPP + per-biome
- ❌ material_aging — instance integrity + culture practices
- ❌ material_synthesis registry — matériaux Wave 1/2 découverts
- ❌ agent fields ajoutés post-Phase 4 (injuries, pathogen_load,
  intent_expires, target_x/y, lexicon, death_cause, death_tick,
  inv_tools, inv_capacity_kg)
- ❌ contrôle d'intégrité (silent corruption invisible)

Conséquence : un load_world cassait silencieusement chaque sprint après
Phase 4. Tout le travail d'aujourd'hui (Wave 3/4) aurait été perdu au
prochain restart.

---

## Architecture livrée

### Module savers (un par module Wave 3/4)

| Module | Fonctions | Format |
|---|---|---|
| `engine/physiology.py` | `save_physio_state` / `load_physio_state` | `physiology.npz` |
| `engine/photosynthesis.py` | `save_photo_state` / `load_photo_state` | `photosynthesis.json` |
| `engine/material_aging.py` | `save_aging_state` / `load_aging_state` | `material_aging.json` |
| `engine/material_synthesis.py` | `save_material_registry` / `load_material_registry` | `material_registry.json` |

Chaque saver retourne `True` si l'état a été écrit, `False` si le module
n'était pas installé sur la sim — silencieusement skipable.

### Wiring dans `world_library.py`

```python
_PERSISTENT_MODULES = (
    ("engine.physiology",     "save_physio_state",   "load_physio_state"),
    ("engine.photosynthesis", "save_photo_state",    "load_photo_state"),
    ("engine.material_aging", "save_aging_state",    "load_aging_state"),
)
```

`save_world` itère sur cette table, import-best-effort, appelle le
saver. `load_world` fait le miroir, re-installant le module sur la sim
fraîche si nécessaire. Cette table est l'**unique point d'extension** —
ajouter un Wave 5 module = ajouter une ligne.

### Liste des champs agents — extension

Avant : 30 champs subset. Après : 47 champs incluant:
- `injuries`, `pathogen_load` (santé)
- `inv_tools`, `inv_capacity_kg` (Phase 5cd inventory)
- `intent_expires`, `target_x`, `target_y` (action state)
- `death_cause`, `death_tick` (timeline post-mortem)
- `lexicon` (proto-langue Phase 4)
- `mass_kg`, `walk_max_ms`, `run_max_ms` (kinematics)

### Intégrité SHA-256

Nouveau fichier `integrity.json` dans chaque world :

```json
{
  "agents.npz":              "abc123...",
  "manifest.json":           "def456...",
  "physiology.npz":          "789abc...",
  "photosynthesis.json":     "012def...",
  "material_aging.json":     "345678...",
  "chunks_count":            "191",
  "modules_saved":           "engine.physiology,engine.photosynthesis,..."
}
```

Nouvelle fonction `verify_world_integrity(name)` retourne
`(ok, problems)` — détecte les corruptions silencieuses (disque fail,
partial writes, accidental edit).

---

## Smoke `p23_persistence_roundtrip.py` — 7/7 PASS

```
[OK] step 1 — save_world wrote files               C:\Users\...\p23_roundtrip_test
[OK] step 2 — required files present               all present
[OK] step 3 — SHA integrity self-consistent        all hashes match
[OK] step 4 — agent snapshot bit-identical         0199ddf8 vs 0199ddf8
[OK] step 4 — physiology snapshot bit-identical    738a5e74 vs 738a5e74
[OK] step 4 — sim.tick preserved                   80 vs 80
[OK] step 4 — material aging counts restored       src=3/0 dst=3/0
```

Recette : build Léman 1.5km × 15 founders × Wave 1-4 installé, run 80
ticks, save, load, vérifier que :
1. Tous les fichiers attendus sont écrits
2. SHA-256 intègre (verify_world_integrity)
3. Hash snapshot agents bit-identique
4. Hash snapshot physiology bit-identique
5. sim.tick préservé
6. Material aging counts (alive + destroyed) identiques

Le smoke use `GENESIS_LIBRARY_ROOT=<tmpdir>` pour ne pas polluer la
library réelle, et fait un `rmtree` à la fin.

---

## Limite connue — continuation determinism

**Pas dans le scope P1** : le contrat livré est *équivalence au moment
du save*. Le smoke ne teste **pas** que `tick(post-save) + N ticks`
produit le même hash que `tick(pre-save) + N ticks` parce que les
chunks restaurés ont un `content_root` différent (généré par
`prf_bytes(seed, ["chunk_root_restored", ...])` au lieu du root
original).

Ça touche les `prf_rng` qui dépendent de `content_root`. Fix dans
**P1.b** : sauver le `content_root` original avec chaque chunk.npz.
Pas bloquant pour P1 ; le sim chargé continue à tourner
déterministiquement à partir d'un nouveau seed effectif.

---

## Régression — Wave 1 → 4 inchangées

- `p18_capabilities_lint` → 6/6 modules requis OK
- `p20_physiology_smoke` → 7/7 PASS (cholera émergente toujours)
- `p22_material_aging_smoke` → 6/6 PASS

---

## Fichiers touchés

```
runtime/engine/world_library.py             (+90 LOC : module savers + SHA + verify)
runtime/engine/physiology.py                (+70 LOC : save/load_physio_state)
runtime/engine/photosynthesis.py            (+55 LOC : save/load_photo_state)
runtime/engine/material_aging.py            (+75 LOC : save/load_aging_state)
runtime/engine/material_synthesis.py        (+75 LOC : save/load_material_registry)
runtime/scripts/p23_persistence_roundtrip.py (nouveau, 195 LOC, 7/7 PASS)
docs/sprints/2026-05-14_PHASE12-PERSISTENCE.md (ce fichier)
NEXT-SPRINT.md                              (P1 archivé)
```

---

## Suite — sous-agents lancés en parallèle

Avec P1 livré, je délègue les 3 priorités suivantes à des sous-agents
indépendants (worktrees Git séparés, pas de collision de fichiers) :

- **P10 long-run stability** → mesurer la sim à 100 000 ticks, vérifier
  mémoire stable, déterminisme intact. Cheap (pas de R&D).
- **P5 océans / Saint-Venant** → câbler le crate `substrate/water` déjà
  commit dans `fc3d472`, ajouter biologie marine simple.
- **P3 inter-region coherence** → `GlobalAtmosphere` partagée + horloge
  globale + migration d'agents entre régions.

Voir le commit suivant pour la délégation.
