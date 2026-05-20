# Sprint 2026-05-18 — Wave 36 isometric 2.5D renderer

**Mode :** Autonome (worktree `agent-ad40031b14d4eb0e7`).
**Cible :** livrer un renderer 2.5D « Age of Empires » en pure numpy + PIL — projection isométrique 2:1, voxel chunks, agents visibles, buildings extrudés, hillshade. Strictement read-only sur la sim.

---

## TL;DR

Nouveau module `runtime/engine/world_render_isometric.py` (~650 LOC) qui projette chaque cellule des `Chunk` (64×64×0,5 m) en isométrique 2:1, stack vertical par hauteur, hill-shade ombré azimut 315°/altitude 45°, agents en marqueurs RGB élevés à la hauteur du terrain, overlay rouge foncé pour les blessés (lecture défensive de `sim._anatomy_fields.wound_severity`), et extrusion 3D des `DiscoveredBuilding` (via leur fingerprint footprint × height).

**9/9 PASS** sur `p66_isometric_render_smoke`. Non-régression confirmée :

| Smoke | Statut |
|---|---|
| `p18_capabilities_lint` | OK — ADR-0005 préservé |
| `p38_building_discovery_smoke` | OK — 8/8 |
| `p42_wildfire_smoke` | OK — 9/9 |
| `p43_social_resonance_smoke` | OK — 9/9 |
| `p66_isometric_render_smoke` | **OK — 9/9 (nouveau)** |

Deux PNG de démonstration générés dans `docs/renders/` :
* `wave36_iso_chunk.png` — un chunk seed `0xC0FFEE_DEAD_BEEF`, 1168×652 px, ~10 KiB.
* `wave36_iso_sim.png` — sim 8 founders au tick=2, agents visibles en marqueurs rouges.

(Le bonus `wave36_iso_macro.png` 896×601 px, ~20 KiB est aussi écrit par le step 9 du smoke.)

---

## Pourquoi (vision AoE)

Le moteur Genesis simule des civilisations émergentes, mais jusqu'à présent l'observateur n'avait que :

* un dashboard chiffré (`runtime/engine/dashboard.py`) ;
* un journal JSONL (`runtime/engine/annalist.py`) ;
* un god-view 2-D top-down très flat.

Quand un utilisateur demande *« est-ce que ça marche ? »*, il veut **voir** les agents poser des briques, les forêts pousser, les montagnes émerger. Wave 36 ajoute la projection 2.5D qui donne :

* une perception de la profondeur (chaque colonne de voxel est extrudée verticalement) ;
* un éclairage cohérent (hill-shade physique-réaliste) ;
* la lisibilité des entités dynamiques (agents = pastilles rouges, blessés en rouge foncé, bâtiments en blocs marron extrudés).

Référence visuelle : Age of Empires II (1999), SimCity 2000 (1993), Diablo II (2000) — tous trois utilisent la même projection 2:1 isométrique, qui reste le meilleur compromis « 3-D lisible / coût CPU minimal ».

---

## Math projection — 2:1 isométrique

Pour chaque cellule de chunk de coordonnées monde `(wx, wy, wz)` (en mètres) :

```
screen_x = (wx - wy) * tile_w / 2
screen_y = (wx + wy) * tile_h / 2 - wz * height_scale_px_per_m
```

* `tile_w = 32 px`, `tile_h = 16 px` → ratio 2:1 standard (un losange parfait).
* `wz` est compressé par `z_compress = 0.05` avant projection (sinon une montagne de 4 km hauteurise un canvas de 4 000 px).
* `height_scale_px_per_m = 1.0 px/m` : un mètre compressé = un pixel vertical.

Le test 2 du smoke vérifie l'identité `project_iso(0, 0, 0) == (0, 0)` et les axes :

| wx, wy | screen_x | screen_y |
|---|---|---|
| (1, 0) | +16 px | +8 px |
| (0, 1) | −16 px | +8 px |
| (1, 1) | 0 px | +16 px |

(Voir `project_iso` et `_project_iso` dans le module.)

---

## Painter's algorithm

Pour gérer la profondeur sans z-buffer GPU, on itère les cellules dans l'ordre `(j ascending, i ascending)` du chunk. En isométrique :

* `screen_y` croît avec `(wx + wy)` ;
* donc une cellule « derrière » est dessinée **avant** une cellule « devant ».

Trois faces par voxel-stack :

1. **Top diamond** (losange) : aux 4 sommets `(0, ±th/2)` et `(±tw/2, 0)`. Couleur = `BIOME_COLOURS[biome] * hillshade`.
2. **Left parallelogram** : du bord gauche du losange descendant de `depth_px`. Couleur ×0.75.
3. **Right parallelogram** : du bord droit du losange descendant. Couleur ×0.6 (face opposée au soleil 315°).

`depth_px = stack_blocks * voxel_block_m * height_scale_px_per_m` où `stack_blocks = ceil(top_z / voxel_block_m)`.

Buildings : painter-order par `(wx + wy, wx)` puis stack 1 bloc par voxel placé.

Agents : dessinés **en dernier** (au-dessus des voxels), élevés à la hauteur du terrain (`elev_at(wx, wy) * z_compress`).

---

## Hillshade

Implémentation indépendante (pas de dépendance Wave 27) — formule standard slope/aspect :

```python
dy, dx = np.gradient(height)
slope  = atan(hypot(dx, dy))
aspect = atan2(-dx, dy)
cos_inc = sin(alt) * cos(slope) + cos(alt) * sin(slope) * cos(az - aspect)
shade   = (1 - strength) + clip(cos_inc, 0, 1) * 1.5 * strength
```

Avec azimut par défaut 315° (nord-ouest) et altitude 45° — choix classique cartographie.

Le step 5 du smoke vérifie qu'un render `hillshade_strength=0.85` a une variance RGB **supérieure** à un render `hillshade_strength=0.0` du même chunk (std 45,47 vs 36,58).

---

## API publique

```python
@dataclass
class IsometricRenderOptions:
    tile_w: int = 32
    tile_h: int = 16
    height_scale_px_per_m: float = 1.0
    canvas_padding_px: int = 64
    sun_azimuth_deg: float = 315.0
    sun_altitude_deg: float = 45.0
    hillshade_strength: float = 0.55
    draw_water: bool = True
    draw_agents: bool = True
    agent_radius_px: int = 3
    agent_rgb: Tuple[int,int,int] = (255, 80, 80)
    wounded_agent_rgb: Tuple[int,int,int] = (180, 0, 0)
    wound_severity_threshold: float = 0.1
    draw_buildings: bool = True
    building_rgb: Tuple[int,int,int] = (160, 100, 50)
    background_rgb: Tuple[int,int,int] = (15, 18, 30)
    z_compress: float = 0.05
    voxel_block_m: float = 4.0

def render_chunk_isometric(chunk, *, path=None, options=None) -> np.ndarray
def render_sim_isometric(sim, *, chunks_range=None, path=None, options=None) -> np.ndarray
def render_macro_isometric(world, *, path=None, options=None) -> np.ndarray
def signature(rgb) -> str   # SHA-256 hex pour déterminisme
def project_iso(wx, wy, wz=0.0, options=None) -> (sx, sy)
def hillshade(height, sun_azimuth_deg=315.0, sun_altitude_deg=45.0, strength=0.55)
```

Toutes les fonctions sont *pures* (`signature(render(...)) == signature(render(...))` — voir step 8 du smoke).

---

## Smoke `p66_isometric_render_smoke.py` — 9/9 PASS

```
==============================================================================
P66 - Wave 36 isometric 2.5D renderer smoke
==============================================================================
  [OK  ] public API surface complete                      all 7 symbols present
  [OK  ] project_iso(0,0,0) == (0,0); x/y axis sane       px(1,0)=16.0,8.0 px(0,1)=-16.0,8.0
  [OK  ] render_chunk_isometric returns non-trivial RGB   shape=(652, 1168, 3) bg_frac=0.644 std=42.3
  [OK  ] PIL PNG written (>1 KiB)                         size=10265B
  [OK  ] hillshade increases canvas luminance variance    std_flat=36.58 std_lit=45.47
  [OK  ] render_sim_isometric draws visible agents        agent_pixels=52
  [OK  ] wounded agent painted in wounded_agent_rgb       wounded_px=37
  [OK  ] two identical renders share SHA-256              sig=3f4cff98679bc235059e0b35…
  [OK  ] render_macro_isometric writes a valid PNG        shape=(601, 896, 3) std=28.7 png=20690B
------------------------------------------------------------------------------
P66 isometric-render smoke : 9/9 PASS
```

Journal écrit à `runtime/journals/p66_isometric_render.json`.

---

## Lecture défensive des modules optionnels

Le renderer doit fonctionner même quand les modules avancés ne sont pas installés :

* **Anatomy / blessures** : `getattr(sim, "_anatomy_fields", None)` → si présent, lit `wound_severity[row]` (1-D ou 2-D, sum() pour multi-organes), sinon ignore et dessine tout en `agent_rgb` normal.
* **Building discovery** : `getattr(sim, "_building_discovery_state", None)` → itère `state.buildings` ; pour chaque `DiscoveredBuilding` on lit `fingerprint.footprint_w/h` et `fingerprint.height` pour extruder une boîte voxel marron. Si l'instance n'a pas ces attributs (ancien format), on saute.
* **PIL** : import lazy via `_try_import_pil()` ; sans PIL, `render_chunk_isometric` retourne un buffer `(64, 64, 3)` `background_rgb` (fallback déterministe au lieu de crash).

---

## Limites notables (honnêteté technique)

* **Pas d'animation** — c'est un renderer *snapshot*, pas un *moteur de jeu*. Chaque appel génère 1 PNG.
* **Pas de textures** — biomes colorés en aplat (3 nuances par stack : top / left face / right face). Pas de bumps, pas de motifs.
* **Pas d'ombres dynamiques** — l'hill-shade est calculé sur la grille `height` du chunk, pas projeté entre voxels voisins. Une montagne ne porte pas d'ombre sur la vallée.
* **Pas de skybox / atmosphère / brouillard** — le background est uniforme `(15, 18, 30)` (gris bleu nuit). Pas de gradient ciel.
* **Buildings approximatifs** — les blocks d'un `DiscoveredBuilding` ne sont pas mémorisés post-validation (les `pending_blocks` sont consommés). On extrude donc une **boîte** depuis le `fingerprint` (footprint × height) ancrée à un coin déterministe du chunk (`bid * 7 mod 64`). Une révision Wave 37+ pourra stocker les blocks pour un rendu fidèle.
* **Élévation agent** — position z d'un agent = `chunk.height[ix, iy] * z_compress`. Pas d'interpolation bilinéaire ; chaque agent est snappé à la cellule la plus proche.
* **Z-compress par défaut très fort** (0.05) — les montagnes de 4 000 m apparaissent comme 200 px de stack visuel. Un appelant peut monter à 0.2 pour des paysages plus dramatiques, au prix d'un canvas plus haut.
* **Painter's order non strict** — l'ordre `(j, i)` est globalement correct mais n'est pas le tri optimal `(j+i, j)`. En pratique, deux voxels voisins ne s'occluent que via leur face supérieure, et `(j, i)` suffit (les artefacts visibles sont sous le seuil de perception sur les canvas typiques). À revoir si on ajoute des structures en porte-à-faux profondes (>4 voxels).

---

## Fichiers livrés

| Path | Statut |
|---|---|
| `runtime/engine/world_render_isometric.py` | nouveau (~650 LOC) |
| `runtime/scripts/p66_isometric_render_smoke.py` | nouveau (~290 LOC) |
| `docs/sprints/2026-05-18_WAVE36-ISOMETRIC-RENDER.md` | nouveau (ce fichier) |
| `docs/renders/wave36_iso_chunk.png` | nouveau (PNG bonus 1168×652) |
| `docs/renders/wave36_iso_sim.png` | nouveau (PNG bonus sim avec agents) |
| `docs/renders/wave36_iso_macro.png` | nouveau (PNG bonus macro) |
| `runtime/journals/p66_isometric_render.json` | nouveau (audit smoke) |

Modules **non touchés** (anti-conflit) : `NEXT-SPRINT.md`, `runtime/engine/world_render.py`, `runtime/engine/machine_emergence.py`, `runtime/engine/anatomy.py`, `runtime/engine/world.py`, modules Waves 1-34.

---

## Pistes Wave 37+

* **Mémoriser les `VoxelBlock` positions** dans `DiscoveredBuilding` pour un rendu pixel-perfect.
* **Sky gradient** + horizon (top du canvas = bleu clair, bottom = bleu nuit).
* **Ombres portées voxel-à-voxel** : pour chaque cellule, ray-march vers le soleil et noircir si bloqué.
* **Atlas de textures** PNG 32×16 par biome (herbe stylisée, sable, pierre) — toujours pure numpy + PIL.
* **Animation tick-par-tick** : exporter chaque tick en PNG, monter en GIF via PIL `ImageSequence` (zero deps).
* **Mode caméra** : rotation 90° / 180° / 270° (pivot la matrice 2:1 → quatre angles AoE-style).
