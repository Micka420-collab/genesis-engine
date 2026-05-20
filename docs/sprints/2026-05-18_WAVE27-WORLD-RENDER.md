# Wave 27 — World Hillshade Renderer (Visualisation)

**Date :** 2026-05-18 (session 34k)
**Module livré :** `engine.world_render`
**Smoke :** `scripts/p57_world_render_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Après 13 waves d'améliorations invisibles (16 → 26), il était temps que
l'utilisateur puisse **VOIR** ce qu'on a construit. Wave 27 livre le
renderer qui transforme les arrays numpy de `GenesisWorld` et `Chunk`
en PNGs lisibles.

Pas de matplotlib, pas de scipy — pure numpy pour les maths (hillshade,
blending) + PIL/Pillow pour l'I/O PNG uniquement (import lazy).

---

## Trois entry points

### 1. `render_macro_world(world, *, path, options)`

Carte continentale 128×128 (ou résolution du world) :

- Biome colour map (12 classes Whittaker, palette atlas hypsométrique)
- × Hillshade (sun azimuth/altitude, illumination Lambert)
- + River overlay (cellules `river_mask` en bleu vif)
- + Plate boundaries (optionnel, en rouge — Voronoï visible)

### 2. `render_chunk(chunk, *, path, options)`

Vue chunk 64×64 upsampled (×4 default → 256×256) :

- Biome colour × hillshade local
- Overlay water (cellules `water > 100 L` en bleu)
- Overlay wood (canopée assombrie proportionnellement à `chunk.wood`)

### 3. `render_pipeline_demo(world, chunk_coord, *, path)`

Grille 2×2 comparant le chunk à travers les stages du pipeline IA :

```
┌────────────────────────┬────────────────────────┐
│  TL: Anchored only     │  TR: + Wave 23 NCA     │
│      (raw FBM)         │      (mono-channel)    │
├────────────────────────┼────────────────────────┤
│  BL: + Wave 24 NCA     │  BR: + Wave 26 WFC     │
│      (multi-channel)   │      (vegetation)      │
└────────────────────────┴────────────────────────┘
```

Le panneau BR est visiblement texturé (patches de WFC vegetation
distincts) là où les autres sont uniformes ou faiblement carved. C'est
le seul moyen visuel de juger l'impact des waves IA.

---

## Mathématique du hillshade

Standard remote-sensing illumination :

```
illum = cos(slope) · cos(zenith)
      + sin(slope) · sin(zenith) · cos(azimuth - aspect)
```

Avec :
- `slope = atan(|∇H|)` : magnitude du gradient
- `aspect = atan2(dh/dy, -dh/dx)` : direction face de la pente
- `azimuth` : position du soleil 0=N / 90=E / 180=S / 270=W
- `zenith = π/2 - altitude_soleil`

Implémentation pure numpy (8 lignes utiles, ~50 LOC avec docs).
Toutes les conv 3×3 par np.roll, déterministes.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique | OK |
| 2 | Hillshade shape (64,64) + range [0, 1] | OK |
| 3 | Palette couvre les 12 biomes Whittaker | OK |
| 4 | `render_macro_world` → (R, R, 3) uint8 + PNG écrit (3.1 kB) | OK |
| 5 | River overlay paint cells `river_mask` exactement en RGB cible | OK |
| 6 | `render_chunk` upsample 2× → (128, 128, 3) + PNG (839 B) | OK |
| 7 | `render_pipeline_demo` 2×2 → (512, 512, 3) + PNG (6.0 kB) | OK |
| 8 | Déterminisme : 2 renders du même world → SHA-256 identique | OK |
| 9 | PNG round-trip via PIL byte-identique | OK |

---

## Renders d'exemple générés

Tous dans `docs/renders/` :

| Fichier | Taille PNG | Contenu |
|---|---|---|
| `wave27_macro_default.png` | 9.4 kB | Carte 128×128 : continent + biomes + rivières |
| `wave27_macro_plates.png` | 8.4 kB | Idem + frontières de plaques en rouge (Voronoï visible) |
| `wave27_chunk_tropical_rainforest.png` | 1.5 kB | Chunk 256×256 forêt tropicale (canopée + springs) |
| `wave27_chunk_temperate_forest.png` | 8.0 kB | Chunk forêt tempérée |
| `wave27_chunk_tundra.png` | 2.8 kB | Chunk toundra |
| `wave27_pipeline_demo.png` | 7.3 kB | **Demo 4-panel : raw → NCA mono → NCA multi → +WFC** |

---

## API publique

```python
from engine.world_render import (
    # Colour utilities
    BIOME_COLOURS,           # dict[int, np.ndarray(3,) uint8]
    biome_color_map,         # (H,W) uint8 → (H,W,3) uint8

    # Lighting
    hillshade,               # elev → float32 [0,1] illumination
    hypsometric_tint,        # elev → uint8 RGB colour ramp

    # Entry points
    render_macro_world,      # GenesisWorld → (R,R,3) uint8 + PNG
    render_chunk,            # Chunk → upsampled uint8 + PNG
    render_pipeline_demo,    # 2×2 panel comparing AI passes

    # Options dataclasses
    MacroRenderOptions,
    ChunkRenderOptions,

    # Diagnostic
    signature,               # SHA-256 of (H,W,3) array
)
```

### Usage minimal

```python
from engine.world_genesis import generate_world, GenesisParams
from engine.world_render import render_macro_world, render_pipeline_demo

world = generate_world(GenesisParams(seed=0xC0FFEE_42, resolution=128))

# Single line → PNG on disk
render_macro_world(world, path="macro.png")

# 4-panel comparing the AI pipeline stages
render_pipeline_demo(world, chunk_coord=(-1500, 1500, 0),
                       path="pipeline_demo.png")
```

### Hillshade customisation

```python
from engine.world_render import MacroRenderOptions, render_macro_world

opts = MacroRenderOptions(
    sun_azimuth_deg=225.0,    # SW sun (drama)
    sun_altitude_deg=30.0,    # low sun = long shadows
    hillshade_strength=0.8,   # punchier shading
    draw_plate_boundaries=True,
)
render_macro_world(world, path="dramatic.png", options=opts)
```

---

## Limitations connues

- **Pas de matplotlib** : volontairement, pour garder le module léger.
  Si tu veux des axes/légendes/colorbars, sauve l'array et plot
  séparément.
- **PIL est optionnel** : sans PIL, le PNG n'est pas écrit mais
  l'array RGB est toujours retourné. Bon pour pipeline headless.
- **Pas d'animations** : un seul snapshot par appel. Pour timelapse,
  appeler en boucle et concaténer côté caller (ffmpeg, imageio, ...).
- **Couleurs hand-picked** : la palette `BIOME_COLOURS` est plausible
  mais non scientifique. Pour publication, utiliser des palettes
  validées (ColorBrewer, viridis).
- **Pipeline demo recouple chaque pass à zéro** : le demo régénère
  le chunk 4 fois pour montrer chaque stage isolément. Coûteux mais
  visuellement nécessaire.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| `dashboard.py` | Inclure les renders dans le HTML dashboard live. |
| **Wave 28** | Animation timelapse de Wave 20 climate-biome shift. |
| **Wave 29** | Render 3D voxelisé via Plotly ou PyVista. |
| `genesis_bootstrap` | Helper `bootstrap_with_render(sim, ...)` qui sauve un macro.png au démarrage. |
| Tests visuels | Add baseline PNG hash en CI pour catch unintended visual regressions. |
