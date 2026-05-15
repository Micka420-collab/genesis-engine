"""World save / load / branch — Genesis worlds become persistent assets.

A saved world is a directory containing:
  * ``manifest.json`` — builder config + sim metadata
  * ``agents.npz``    — agent arrays (compact numpy zip)
  * ``chunks/``       — one ``.npz`` per cached chunk (only if save_chunks=True)
  * ``annalist.jsonl``— optional full event log

Load reconstructs a :class:`World` (via the builder) and re-injects the
saved state. Branching creates an independent copy under a new name —
useful for "what if" experiments.

This is **NOT** a generic checkpointing system. It targets the common case:
"build a world today, keep iterating tomorrow". Some live state (sim_lift
fields, audio buffers) is recomputed on first tick rather than restored
verbatim — sim_lift's vegetation field will regenerate from biome data and
then evolve identically going forward.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
from dataclasses import asdict
from typing import Iterable, List, Optional, Tuple

import numpy as np

from engine.world_builder import WorldBuilder, World, _BuilderState


# Modules that can persist their own state outside the basic save_world
# loop. Each entry is (dotted_module, save_fn_name, load_fn_name). Modules
# absent at import time are skipped silently — keeps the persistence
# system loosely coupled.
_PERSISTENT_MODULES: Tuple[Tuple[str, str, str], ...] = (
    ("engine.physiology",       "save_physio_state",   "load_physio_state"),
    ("engine.photosynthesis",   "save_photo_state",    "load_photo_state"),
    ("engine.material_aging",   "save_aging_state",    "load_aging_state"),
    ("engine.marine",           "save_marine_state",   "load_marine_state"),
    ("engine.plant_evolution",  "save_plant_state",    "load_plant_state"),
    ("engine.meteorology",      "save_meteo_state",    "load_meteo_state"),
    ("engine.animal_evolution", "save_animal_state",   "load_animal_state"),
    ("engine.agriculture",      "save_agriculture_state", "load_agriculture_state"),
    ("engine.writing",          "save_writing_state",  "load_writing_state"),
    ("engine.polity",           "save_polity_state",   "load_polity_state"),
    ("engine.geology",          "save_geology_state",  "load_geology_state"),
    ("engine.metallurgy",       "save_metallurgy_state", "load_metallurgy_state"),
    ("engine.realistic_construction",
                                 "save_realistic_construction_state",
                                 "load_realistic_construction_state"),
    ("engine.building_discovery",
                                 "save_building_discovery_state",
                                 "load_building_discovery_state"),
    ("engine.art_discovery",     "save_art_state",      "load_art_state"),
)


def _file_sha256(path: str) -> str:
    """Return the lowercase hex SHA-256 of a file. ``""`` if absent."""
    if not os.path.isfile(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


_LIBRARY_ROOT_ENV = "GENESIS_LIBRARY_ROOT"


def _library_root() -> str:
    root = os.environ.get(_LIBRARY_ROOT_ENV)
    if root:
        return os.path.abspath(root)
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(here, "..", ".."))
    return os.path.join(project_root, "worlds")


def world_path(name: str) -> str:
    """Return the absolute path of a named world in the library."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(_library_root(), safe)


def list_worlds() -> List[str]:
    """Return the names of all worlds in the library."""
    root = _library_root()
    if not os.path.isdir(root):
        return []
    out = []
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if os.path.isdir(full) and os.path.isfile(os.path.join(full, "manifest.json")):
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

_AGENT_FIELDS_TO_SAVE = (
    # Identity / lineage
    "uuid", "generation", "born_tick",
    # Kinematics
    "pos", "vel", "heading", "mass_kg", "walk_max_ms", "run_max_ms",
    "lifespan_ticks",
    # Drives
    "hunger", "thirst", "sleep", "fatigue", "thermal",
    "pain", "stress", "loneliness",
    # Health
    "vitality", "injuries", "pathogen_load",
    # Personality / traits
    "openness", "conscientiousness", "extraversion", "agreeableness",
    "neuroticism", "ambition", "risk_tolerance",
    "aggression", "curiosity", "empathy", "intelligence",
    # Inventory
    "inv_water", "inv_food", "inv_wood", "inv_stone", "inv_metal",
    "inv_tools", "inv_capacity_kg",
    # Action state
    "last_mating_tick", "offspring_count", "action",
    "target_x", "target_y", "intent_expires",
    # Death
    "alive", "death_cause", "death_tick",
    # Language (Phase 4)
    "lexicon",
)


def save_world(world: World, name: Optional[str] = None,
               *, save_chunks: bool = True,
               save_events: bool = False) -> str:
    """Persist a world under the library. Returns the path.

    Defaults : save agent arrays + cached chunks. Events are skipped by
    default (they can be huge); the journal file on disk is the canonical
    log if you need replay.
    """
    if name is None:
        name = world.name
    target = world_path(name)
    os.makedirs(target, exist_ok=True)
    os.makedirs(os.path.join(target, "chunks"), exist_ok=True)

    # 1. Manifest — builder state + sim runtime info
    state = world.builder_state
    manifest = {
        "name": name,
        "schema_version": 1,
        "builder": asdict(state),
        "sim": {
            "sim_id": getattr(world.sim, "sim_id", ""),
            "tick": int(world.sim.tick),
            "n_active": int(world.sim.agents.n_active),
            "_bootstrapped": True,
        },
        "atmosphere": (
            {"co2_kg": float(world.sim.atmosphere.co2_kg),
             "co2_ppm": float(world.sim.atmosphere.co2_ppm),
             "temp_anomaly_k": float(world.sim.atmosphere.temp_anomaly_k)}
            if hasattr(world.sim, "atmosphere") else None
        ),
    }
    # extra_install callables can't be serialised — drop them
    manifest["builder"].pop("extra_install", None)
    with open(os.path.join(target, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # 2. Agents — pack the registry's arrays compactly
    agents = world.sim.agents
    n = agents.n_active
    arrays = {"n_active": np.array([n], dtype=np.int64)}
    for fld in _AGENT_FIELDS_TO_SAVE:
        arr = getattr(agents, fld, None)
        if arr is None:
            continue
        try:
            slab = np.asarray(arr[:n])
            # Object dtypes (UUIDs, dicts) can't be loaded back with
            # allow_pickle=False; flatten to unicode for serialisation safety.
            if slab.dtype == object:
                slab = np.array([str(x) if x is not None else ""
                                 for x in slab.tolist()], dtype="U64")
            arrays[fld] = slab
        except Exception:
            continue
    np.savez_compressed(os.path.join(target, "agents.npz"), **arrays)

    # 3. Chunks
    chunk_index: List[str] = []
    if save_chunks:
        for coord, chunk in world.sim.streamer.cache.items():
            cx, cy, cz = coord
            chunk_path = os.path.join(target, "chunks", f"{cx}_{cy}_{cz}.npz")
            np.savez_compressed(
                chunk_path,
                height=chunk.height, biome=chunk.biome,
                stone=chunk.stone, wood=chunk.wood, metal=chunk.metal,
                water=chunk.water,
                food_kcal=chunk.food_kcal, food_capacity=chunk.food_capacity,
            )
            chunk_index.append(f"{cx}_{cy}_{cz}")
        with open(os.path.join(target, "chunks", "_index.json"), "w") as f:
            json.dump(chunk_index, f)

    # 4. Optional side-tables (Wave 3 physiology, Wave 4 photo / aging).
    saved_modules: List[str] = []
    for dotted, save_name, _ in _PERSISTENT_MODULES:
        try:
            mod = importlib.import_module(dotted)
        except Exception:
            continue
        save_fn = getattr(mod, save_name, None)
        if save_fn is None:
            continue
        try:
            ok = bool(save_fn(world.sim, target))
            if ok:
                saved_modules.append(dotted)
        except Exception:
            pass

    # 5. Optional material registry — caller may have attached one.
    reg = getattr(world.sim, "_material_registry", None)
    if reg is None:
        # Builder may store it on the world.
        reg = getattr(world, "material_registry", None)
    if reg is not None:
        try:
            from engine.material_synthesis import save_material_registry
            save_material_registry(reg, target)
            saved_modules.append("engine.material_synthesis")
        except Exception:
            pass

    # 6. Integrity manifest — SHA-256 of the artefacts the loader will
    # read. Detects silent corruption (disk errors, partial writes).
    integrity = {
        "agents.npz": _file_sha256(os.path.join(target, "agents.npz")),
        "manifest.json": _file_sha256(os.path.join(target, "manifest.json")),
    }
    for f in ("physiology.npz", "photosynthesis.json",
              "material_aging.json", "material_registry.json",
              "marine.json", "marine.npz"):
        p = os.path.join(target, f)
        if os.path.isfile(p):
            integrity[f] = _file_sha256(p)
    # Index chunks but don't hash each (would explode for big worlds).
    integrity["chunks_count"] = str(len(chunk_index))
    integrity["modules_saved"] = ",".join(saved_modules)
    with open(os.path.join(target, "integrity.json"),
              "w", encoding="utf-8") as f:
        json.dump(integrity, f, indent=2)

    return target


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_world(name: str) -> World:
    """Reconstruct a saved world. Builds a fresh sim from the manifest
    config, then re-injects agents + chunks.
    """
    target = world_path(name)
    manifest_path = os.path.join(target, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"world {name!r} not found at {target}")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    b = manifest["builder"]

    # Rebuild the builder
    bw = WorldBuilder(name=b.get("name", name))
    if b.get("lat") is not None and b.get("lon") is not None:
        bw.anchor(b["lat"], b["lon"])
    bw.size_km(b.get("size_km", 2.0))
    bw.founders(b.get("n_founders", 20))
    bw.cultures(b.get("n_cultures", 2))
    bw.max_agents(b.get("max_agents", 1000))
    bw.spawn_radius_m(b.get("spawn_radius_m", 200.0))
    bw.drive_accel(b.get("drive_accel", 1500.0))
    bw.seed(b.get("seed", 0))
    bw.with_l1_earth(b.get("enable_l1", True))
    bw.with_l2_lift(b.get("enable_l2", True))
    bw.with_5cd(b.get("enable_5cd", True))
    if b.get("cache_dir"):
        bw.cache_dir(b["cache_dir"])
    world = bw.build()

    # Restore agents
    agents = world.sim.agents
    agents_npz = os.path.join(target, "agents.npz")
    if os.path.isfile(agents_npz):
        loaded = np.load(agents_npz, allow_pickle=False)
        n = int(loaded["n_active"][0])
        agents.n_active = max(agents.n_active, n)
        for fld in _AGENT_FIELDS_TO_SAVE:
            if fld in loaded.files:
                target_arr = getattr(agents, fld, None)
                if target_arr is None:
                    continue
                src = loaded[fld]
                try:
                    if target_arr.dtype == object:
                        # Restore string-flattened object fields one by one.
                        for i in range(min(src.shape[0], target_arr.shape[0])):
                            target_arr[i] = str(src[i])
                    else:
                        target_arr[:src.shape[0]] = src
                except Exception:
                    pass

    # Restore chunks
    chunks_dir = os.path.join(target, "chunks")
    if os.path.isdir(chunks_dir):
        for fname in os.listdir(chunks_dir):
            if not fname.endswith(".npz"):
                continue
            parts = fname[:-4].split("_")
            if len(parts) != 3:
                continue
            try:
                cx, cy, cz = (int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                continue
            data = np.load(os.path.join(chunks_dir, fname), allow_pickle=False)
            from engine.world import Chunk
            from engine.core import prf_bytes
            content_root = prf_bytes(
                world.builder_state.seed,
                ["chunk_root_restored", str(cx), str(cy), str(cz)], [], 32)
            chunk = Chunk(
                coord=(cx, cy, cz),
                height=data["height"], biome=data["biome"],
                stone=data["stone"], wood=data["wood"], metal=data["metal"],
                water=data["water"],
                food_kcal=data["food_kcal"], food_capacity=data["food_capacity"],
                content_root=content_root,
            )
            world.sim.streamer.cache[(cx, cy, cz)] = chunk
            world.sim.streamer.last_touch[(cx, cy, cz)] = world.sim.tick

    # Restore sim metadata
    world.sim.tick = int(manifest.get("sim", {}).get("tick", 0))
    atm = manifest.get("atmosphere")
    if atm and hasattr(world.sim, "atmosphere"):
        try:
            world.sim.atmosphere.co2_kg = float(atm["co2_kg"])
            world.sim.atmosphere.temp_anomaly_k = float(atm["temp_anomaly_k"])
        except Exception:
            pass

    # 4. Optional side-tables (Wave 3 physiology, Wave 4 photo / aging).
    # Loaders install the module on the sim if it wasn't installed yet, so
    # a restored world is *immediately* equivalent to a freshly-installed
    # one from a caller's POV.
    for dotted, _, load_name in _PERSISTENT_MODULES:
        try:
            mod = importlib.import_module(dotted)
        except Exception:
            continue
        load_fn = getattr(mod, load_name, None)
        if load_fn is None:
            continue
        try:
            load_fn(world.sim, target)
        except Exception:
            pass

    # 5. Optional material registry. Attach onto sim AND world for both
    # access patterns to work.
    try:
        from engine.material_synthesis import load_material_registry
        reg = load_material_registry(target)
        if reg is not None:
            world.sim._material_registry = reg
            try:
                world.material_registry = reg
            except Exception:
                pass
    except Exception:
        pass

    return world


def verify_world_integrity(name: str) -> Tuple[bool, List[str]]:
    """Compare the on-disk artefacts of a saved world against the SHA
    digests recorded in ``integrity.json``.

    Returns ``(ok, problems)``. ``ok`` is ``True`` if every file the
    manifest expected to find is present and hash-matches. ``problems``
    lists human-readable issues (missing file, hash mismatch).
    """
    target = world_path(name)
    integ_path = os.path.join(target, "integrity.json")
    problems: List[str] = []
    if not os.path.isfile(integ_path):
        return False, [f"integrity.json missing under {target}"]
    with open(integ_path, "r", encoding="utf-8") as f:
        integrity = json.load(f)
    for fname, expected in integrity.items():
        if fname in ("chunks_count", "modules_saved"):
            continue
        if not expected:
            continue
        actual = _file_sha256(os.path.join(target, fname))
        if not actual:
            problems.append(f"missing file {fname}")
        elif actual != expected:
            problems.append(
                f"hash mismatch on {fname}: expected {expected[:8]}…"
                f" got {actual[:8]}…")
    return (not problems), problems


# ---------------------------------------------------------------------------
# Branch
# ---------------------------------------------------------------------------

def branch_world(src_name: str, new_name: str) -> str:
    """Copy a saved world to a new name. Useful for 'what if' experiments."""
    src = world_path(src_name)
    dst = world_path(new_name)
    if not os.path.isdir(src):
        raise FileNotFoundError(f"source world {src_name!r} not found")
    if os.path.exists(dst):
        raise FileExistsError(f"target {new_name!r} already exists")
    shutil.copytree(src, dst)
    # Rewrite the manifest to reflect the new name.
    manifest_path = os.path.join(dst, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["name"] = new_name
    manifest["branched_from"] = src_name
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return dst


def delete_world(name: str) -> bool:
    """Remove a saved world from the library. Returns True if deleted."""
    target = world_path(name)
    if not os.path.isdir(target):
        return False
    shutil.rmtree(target)
    return True


__all__ = [
    "save_world", "load_world", "branch_world", "delete_world",
    "list_worlds", "world_path", "verify_world_integrity",
]
