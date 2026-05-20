"""Genesis Engine — Wave 37 animation timelapse.

Capture frame-by-frame une évolution sim et exporte en GIF animé via
PIL ImageSequence. Réutilise :

  - Wave 36 ``world_render_isometric`` pour la projection Age of
    Empires (par défaut) ou Wave 27 ``world_render`` top-down.
  - Wave 33 ``stone_age_evolution`` observer pour les snapshots
    read-only (positions agents, wounds, polities, inventions...).

Aucun script ne décide ce que les agents font à chaque frame. Le
moteur cognition + tous les modules émergents tournent normalement ;
le timelapse ne fait que **capturer périodiquement** l'état pour la
visualisation.

Architecture
------------

```
1. sim configuré (bootstrap_genesis_sim + install_* modules)
2. for tick in range(N):
       sim.step()                                  # cognition full
       if tick % capture_every == 0:
           render = render_fn(sim, **render_options)
           frame = TimelapseFrame(tick, render, snapshot)
3. frames_to_gif(frames, path, duration_ms)        # PIL animation
```

GIF par défaut, PNG fallback toujours dispo.

Determinism
-----------

Frames sont déterministes via prf_rng. GIF compression peut varier
selon version PIL ; on stocke aussi un manifest JSON avec frame
signatures SHA-256 pour audit.
"""
from __future__ import annotations

import io
import os
import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np


PIPELINE_LAYER = "Genesis-L5 Observer"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Optional PIL handling
# ---------------------------------------------------------------------------

def _try_import_pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Configuration + data types
# ---------------------------------------------------------------------------

@dataclass
class TimelapseConfig:
    """Hyper-parameters of the capture loop."""
    n_ticks: int = 200                # total ticks to run
    capture_every: int = 10           # ticks between frames
    use_isometric: bool = True        # True → Wave 36 iso renderer, False → Wave 27 top-down
    gif_duration_ms_per_frame: int = 250
    gif_loop: int = 0                 # 0 = loop forever
    snapshot_clusters_radius_m: float = 80.0
    snapshot_clusters_min_pts: int = 2
    custom_renderer: Optional[Callable] = None  # signature : sim → np.ndarray (H, W, 3) uint8


@dataclass
class TimelapseFrame:
    """One captured frame + its read-only snapshot."""
    tick: int
    rgb: np.ndarray = field(default=None)         # (H, W, 3) uint8
    n_alive: int = 0
    n_clusters: int = 0
    n_polities: int = 0
    n_inventions: int = 0
    n_buildings: int = 0
    n_machines: int = 0
    n_inscriptions: int = 0
    blood_min_l: float = 5.0
    signature_hex: str = ""


@dataclass
class TimelapseHistory:
    """Output of capture_timelapse."""
    config: TimelapseConfig
    frames: List[TimelapseFrame] = field(default_factory=list)
    seed: int = 0
    canvas_shape: Tuple[int, int, int] = (0, 0, 3)


# ---------------------------------------------------------------------------
# Capture loop
# ---------------------------------------------------------------------------

def _default_render(sim, use_isometric: bool) -> np.ndarray:
    """Default frame renderer. Tries iso (Wave 36) then top-down (Wave 27)."""
    if use_isometric:
        try:
            from engine.world_render_isometric import (
                render_sim_isometric, IsometricRenderOptions)
            return render_sim_isometric(
                sim, options=IsometricRenderOptions(z_compress=0.15))
        except Exception:
            pass
    # Fallback : top-down render of one chunk if anything available.
    try:
        from engine.world_render import render_chunk, ChunkRenderOptions
        if sim.streamer.cache:
            coord, chunk = next(iter(sim.streamer.cache.items()))
            return render_chunk(chunk,
                                  options=ChunkRenderOptions(upsample=2))
    except Exception:
        pass
    # Last resort : blank 256x256 dark background.
    return np.zeros((256, 256, 3), dtype=np.uint8)


def _frame_signature(rgb: np.ndarray) -> str:
    return hashlib.sha256(rgb.tobytes()).hexdigest()


def _safe_count(getter, default=0):
    try:
        v = getter()
        return int(v) if v is not None else int(default)
    except Exception:
        return int(default)


def _snapshot_counts(sim) -> Dict[str, int]:
    """Read-only counts of emergent things at current sim tick."""
    counts: Dict[str, int] = {}
    counts["n_alive"] = _safe_count(
        lambda: int(sim.agents.alive[:sim.agents.n_active].sum()))

    polity_state = getattr(sim, "_polity_state", None)
    counts["n_polities"] = _safe_count(
        lambda: len(getattr(polity_state, "polities", [])) if polity_state else 0)

    inv_state = getattr(sim, "_invention_state", None) or getattr(sim, "invention", None)
    if inv_state is not None:
        reg = getattr(inv_state, "registry", inv_state)
        counts["n_inventions"] = _safe_count(
            lambda: len(getattr(reg, "artifacts", {}) or {}))
    else:
        counts["n_inventions"] = 0

    build_state = getattr(sim, "_building_discovery_state", None)
    counts["n_buildings"] = _safe_count(
        lambda: int(getattr(build_state, "n_structures_total", 0)))

    machine_state = getattr(sim, "_machine_state", None)
    if machine_state is not None:
        reg = getattr(machine_state, "registry", machine_state)
        counts["n_machines"] = _safe_count(
            lambda: len(getattr(reg, "machines", {}) or {}))
    else:
        counts["n_machines"] = 0

    write_state = getattr(sim, "_writing_state", None)
    if write_state is not None:
        counts["n_inscriptions"] = _safe_count(
            lambda: len(getattr(write_state, "inscriptions", []) or []))
    else:
        counts["n_inscriptions"] = 0

    anatomy_fields = getattr(sim, "_anatomy_fields", None)
    if anatomy_fields is not None:
        try:
            n = sim.agents.n_active
            alive = sim.agents.alive[:n].astype(bool)
            if alive.any():
                counts["blood_min_l"] = float(
                    anatomy_fields.blood_volume_l[:n][alive].min())
            else:
                counts["blood_min_l"] = 5.0
        except Exception:
            counts["blood_min_l"] = 5.0
    else:
        counts["blood_min_l"] = 5.0
    return counts


def _count_clusters(sim, radius_m: float, min_pts: int) -> int:
    """Read-only DBSCAN-like cluster count."""
    try:
        from engine.stone_age_evolution import observe_agents, observe_clusters
        agents_snap = observe_agents(sim)
        clusters = observe_clusters(agents_snap, radius_m, min_pts)
        return len(clusters)
    except Exception:
        return 0


def capture_timelapse(sim,
                        cfg: Optional[TimelapseConfig] = None
                        ) -> TimelapseHistory:
    """Run ``sim.step()`` ``cfg.n_ticks`` times, capture a frame every
    ``cfg.capture_every`` ticks.

    Returns a :class:`TimelapseHistory` with frames + per-frame snapshot
    counts.

    Read-only — does NOT install any modules. The caller must have
    done ``bootstrap_genesis_sim(sim)`` + ``install_*`` for whatever
    modules they want active before invoking the timelapse.

    Pure function in the sense that the renderer is read-only and the
    snapshot counts are read-only. ``sim.step()`` itself is the
    simulation's normal step.
    """
    cfg = cfg or TimelapseConfig()
    if not getattr(sim, "_bootstrapped", False):
        sim.bootstrap()

    history = TimelapseHistory(config=cfg, seed=int(sim.cfg.seed))
    render_fn = cfg.custom_renderer or (
        lambda s: _default_render(s, cfg.use_isometric))

    # Frame 0 (post-bootstrap, pre-evolution).
    rgb0 = render_fn(sim)
    snap0 = _snapshot_counts(sim)
    n_clusters_0 = _count_clusters(sim, cfg.snapshot_clusters_radius_m,
                                       cfg.snapshot_clusters_min_pts)
    history.frames.append(TimelapseFrame(
        tick=int(sim.tick), rgb=rgb0,
        n_alive=int(snap0.get("n_alive", 0)),
        n_clusters=n_clusters_0,
        n_polities=int(snap0.get("n_polities", 0)),
        n_inventions=int(snap0.get("n_inventions", 0)),
        n_buildings=int(snap0.get("n_buildings", 0)),
        n_machines=int(snap0.get("n_machines", 0)),
        n_inscriptions=int(snap0.get("n_inscriptions", 0)),
        blood_min_l=float(snap0.get("blood_min_l", 5.0)),
        signature_hex=_frame_signature(rgb0),
    ))
    if history.canvas_shape == (0, 0, 3):
        history.canvas_shape = tuple(rgb0.shape)

    for tick_idx in range(cfg.n_ticks):
        sim.step()
        if (tick_idx + 1) % cfg.capture_every == 0:
            rgb = render_fn(sim)
            snap = _snapshot_counts(sim)
            n_cl = _count_clusters(sim, cfg.snapshot_clusters_radius_m,
                                       cfg.snapshot_clusters_min_pts)
            history.frames.append(TimelapseFrame(
                tick=int(sim.tick), rgb=rgb,
                n_alive=int(snap.get("n_alive", 0)),
                n_clusters=n_cl,
                n_polities=int(snap.get("n_polities", 0)),
                n_inventions=int(snap.get("n_inventions", 0)),
                n_buildings=int(snap.get("n_buildings", 0)),
                n_machines=int(snap.get("n_machines", 0)),
                n_inscriptions=int(snap.get("n_inscriptions", 0)),
                blood_min_l=float(snap.get("blood_min_l", 5.0)),
                signature_hex=_frame_signature(rgb),
            ))
    return history


# ---------------------------------------------------------------------------
# Export : GIF + PNG + manifest
# ---------------------------------------------------------------------------

def _pad_to_uniform_size(frames: List[np.ndarray]) -> List[np.ndarray]:
    """Pad all frames to the maximum (H, W) so GIF stitching works.

    Each frame keeps its original colours ; extra pixels are filled
    with the background (assumed black). Returns a NEW list ; does not
    mutate inputs.
    """
    if not frames:
        return frames
    max_h = max(f.shape[0] for f in frames)
    max_w = max(f.shape[1] for f in frames)
    out = []
    for f in frames:
        h, w = f.shape[:2]
        if h == max_h and w == max_w:
            out.append(f)
            continue
        padded = np.zeros((max_h, max_w, 3), dtype=np.uint8)
        padded[:h, :w] = f
        out.append(padded)
    return out


def frames_to_gif(history: TimelapseHistory,
                    path: str,
                    *,
                    duration_ms: Optional[int] = None,
                    loop: Optional[int] = None
                    ) -> bool:
    """Save the frames as an animated GIF. Returns True on success.

    Requires PIL. If PIL is unavailable, returns False silently. Frames
    of differing size are padded to the largest (H, W).
    """
    Image = _try_import_pil()
    if Image is None or not history.frames:
        return False
    cfg = history.config
    dur = int(duration_ms or cfg.gif_duration_ms_per_frame)
    lp = int(loop if loop is not None else cfg.gif_loop)

    rgb_frames = _pad_to_uniform_size([f.rgb for f in history.frames])
    pil_frames = [Image.fromarray(f, mode="RGB") for f in rgb_frames]
    pil_frames[0].save(
        path,
        save_all=True,
        append_images=pil_frames[1:],
        duration=dur,
        loop=lp,
        optimize=False,
        disposal=2,
    )
    return True


def frames_to_pngs(history: TimelapseHistory,
                     output_dir: str,
                     *,
                     filename_prefix: str = "frame"
                     ) -> int:
    """Write each frame to a separate PNG file. Returns count written."""
    Image = _try_import_pil()
    if Image is None or not history.frames:
        return 0
    os.makedirs(output_dir, exist_ok=True)
    n = 0
    width_digits = max(3, len(str(len(history.frames))))
    for i, frame in enumerate(history.frames):
        fname = f"{filename_prefix}_{i:0{width_digits}d}.png"
        Image.fromarray(frame.rgb, mode="RGB").save(
            os.path.join(output_dir, fname), format="PNG")
        n += 1
    return n


def history_to_manifest(history: TimelapseHistory,
                          path: Optional[str] = None
                          ) -> Dict[str, object]:
    """Build a JSON-serializable manifest of the history. If ``path``
    is provided, write it to disk."""
    cfg = history.config
    manifest = {
        "seed": history.seed,
        "n_frames": len(history.frames),
        "canvas_shape": list(history.canvas_shape),
        "config": {
            "n_ticks": cfg.n_ticks,
            "capture_every": cfg.capture_every,
            "use_isometric": cfg.use_isometric,
            "gif_duration_ms_per_frame": cfg.gif_duration_ms_per_frame,
            "gif_loop": cfg.gif_loop,
        },
        "frames": [
            {
                "tick": f.tick,
                "signature": f.signature_hex,
                "n_alive": f.n_alive,
                "n_clusters": f.n_clusters,
                "n_polities": f.n_polities,
                "n_inventions": f.n_inventions,
                "n_buildings": f.n_buildings,
                "n_machines": f.n_machines,
                "n_inscriptions": f.n_inscriptions,
                "blood_min_l": round(f.blood_min_l, 3),
            }
            for f in history.frames
        ],
    }
    if path is not None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
    return manifest


def timelapse_summary(history: TimelapseHistory) -> Dict[str, object]:
    """Brief one-line summary of the trajectory."""
    if not history.frames:
        return {"n_frames": 0}
    first = history.frames[0]
    last = history.frames[-1]
    return {
        "n_frames": len(history.frames),
        "tick_range": (first.tick, last.tick),
        "alive_track": [f.n_alive for f in history.frames],
        "clusters_track": [f.n_clusters for f in history.frames],
        "polities_first_last": (first.n_polities, last.n_polities),
        "inventions_first_last": (first.n_inventions, last.n_inventions),
        "machines_first_last": (first.n_machines, last.n_machines),
        "buildings_first_last": (first.n_buildings, last.n_buildings),
        "blood_min_track": [round(f.blood_min_l, 2) for f in history.frames],
        "first_signature": first.signature_hex[:16],
        "last_signature": last.signature_hex[:16],
    }


__all__ = [
    "TimelapseConfig",
    "TimelapseFrame",
    "TimelapseHistory",
    "capture_timelapse",
    "frames_to_gif",
    "frames_to_pngs",
    "history_to_manifest",
    "timelapse_summary",
]
