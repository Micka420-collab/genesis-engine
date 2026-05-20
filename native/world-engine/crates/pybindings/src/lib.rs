//! Python bindings — exposes a small surface so the existing Python runtime
//! can call into the Rust world engine without giving up its current Python
//! `World` class.
//!
//! Usage from Python:
//!
//! ```python
//! import genesis_world as gw
//! w = gw.PyWorld(seed=42)
//! obs = w.observe_chunk(0, 0)
//! print(obs["biome"][0], obs["elevation"][0])
//! ```

use dashmap::DashMap;
use genesis_agent_api::{EntityId, Mutation, WorldClient};
use genesis_biome::Biome;
use genesis_core::{ChunkCoord, Voxel, WorldCoord, WorldSeed, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use genesis_intent::{AgentId, Intent, IntentBus, Plan};
use genesis_mesh::extract_surface_nets;
use genesis_macro_bridge::{read_binary, MacroGrid};
use genesis_streaming::manager::ChunkManagerConfig;
use genesis_streaming::ChunkManager;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::fs::File;
use std::io::Cursor;
use std::path::Path;
use std::hash::{Hash, Hasher};
use std::sync::Arc;

/// L2 mesh cache key — invalidated when `mutation_version` bumps.
#[derive(Clone, Copy, Debug, Eq)]
struct MeshCacheKey {
    cx: i32,
    cy: i32,
    step: u32,
    version: u64,
}

impl PartialEq for MeshCacheKey {
    fn eq(&self, other: &Self) -> bool {
        self.cx == other.cx
            && self.cy == other.cy
            && self.step == other.step
            && self.version == other.version
    }
}

impl Hash for MeshCacheKey {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.cx.hash(state);
        self.cy.hash(state);
        self.step.hash(state);
        self.version.hash(state);
    }
}

struct CachedMesh {
    flat_vertices: Vec<f32>,
    indices: Vec<u32>,
    vertex_count: usize,
    triangle_count: usize,
}

/// World handle exposed to Python.
#[pyclass(name = "PyWorld", module = "genesis_world")]
pub struct PyWorld {
    client: WorldClient,
    manager: ChunkManager,
    intent_bus: IntentBus,
    runtime: tokio::runtime::Runtime,
    /// Mesh L2 keyed by chunk + LOD step + mutation version.
    mesh_l2: Arc<DashMap<MeshCacheKey, CachedMesh>>,
}

#[pymethods]
impl PyWorld {
    /// Build a new world with the given 64-bit seed.
    ///
    /// Optional kwargs:
    ///  - sea_level (float)
    ///  - erosion_droplets (int)
    ///  - erosion_passes (int)
    ///  - cache_capacity (int)
    #[new]
    #[pyo3(signature = (seed, **kwargs))]
    fn new(seed: u64, kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        let mut cfg = ChunkManagerConfig::default();
        if let Some(kw) = kwargs {
            if let Some(v) = kw.get_item("sea_level")? {
                cfg.sea_level = v.extract::<f32>()?;
            }
            if let Some(v) = kw.get_item("erosion_droplets")? {
                cfg.erosion_droplets = v.extract::<u32>()?;
            }
            if let Some(v) = kw.get_item("erosion_passes")? {
                cfg.erosion_passes = v.extract::<u32>()?;
            }
            if let Some(v) = kw.get_item("cache_capacity")? {
                cfg.cache_capacity = v.extract::<usize>()?;
            }
            if let Some(v) = kw.get_item("macro_grid_path")? {
                let path: String = v.extract()?;
                let grid = load_macro_grid_path(&path).map_err(|e| {
                    PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("macro grid: {e}"))
                })?;
                cfg.macro_grid = Some(Arc::new(grid));
            }
            if let Some(v) = kw.get_item("macro_grid_bytes")? {
                let data: Vec<u8> = v.extract()?;
                let grid = read_binary(Cursor::new(data)).map_err(|e| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("macro grid: {e}"))
                })?;
                cfg.macro_grid = Some(Arc::new(grid));
            }
            if let Some(v) = kw.get_item("chunk_side_m")? {
                cfg.chunk_side_m = v.extract::<f32>()?;
            }
            if let Some(v) = kw.get_item("macro_interior_weight")? {
                cfg.macro_interior_weight = v.extract::<f32>()?;
            }
        }
        let mgr = ChunkManager::new(WorldSeed::from_u64(seed), cfg);
        let client = WorldClient::new(mgr.clone());
        let intent_bus = IntentBus::new();
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        // Start the prefetch background task on this world's runtime.
        let bus_clone = intent_bus.clone();
        let mgr_clone = mgr.clone();
        let _guard = runtime.enter();
        let _handle = genesis_intent::spawn_prefetcher(bus_clone, mgr_clone, 30);
        drop(_guard);
        Ok(Self {
            client,
            manager: mgr,
            intent_bus,
            runtime,
            mesh_l2: Arc::new(DashMap::new()),
        })
    }

    /// Apply queued agent mutations (call after `set_voxel`).
    fn apply_pending(&self) -> usize {
        self.client.apply_pending()
    }

    /// Set one voxel (queued; call `apply_pending` or rely on next tick hook).
    fn set_voxel(&self, x: i32, y: i32, z: i32, material: u16) -> PyResult<()> {
        self.client
            .submit(Mutation::SetVoxel {
                pos: WorldCoord::new(x, y, z),
                value: Voxel(material),
                actor: EntityId(0),
            })
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
    }

    /// Zstd snapshot blob (tick + cached chunks).
    fn save_snapshot(&self) -> PyResult<Vec<u8>> {
        self.client
            .snapshot_bytes()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
    }

    /// Restore from `save_snapshot` bytes.
    fn restore_snapshot(&self, data: Vec<u8>) -> PyResult<()> {
        self.client
            .restore_snapshot_bytes(&data)
            .map(|_| ())
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        self.mesh_l2.clear();
        Ok(())
    }

    /// Clear L2 mesh cache (e.g. after bulk edits).
    fn invalidate_mesh_cache(&self) {
        self.mesh_l2.clear();
    }

    /// Number of chunks currently in the in-memory cache.
    fn cached_chunk_count(&self) -> usize {
        self.manager.cached_count()
    }

    /// Submit an intent. `plan_kind` is "idle", "walk", or "teleport".
    /// `points` is a list of `(x, y, z)` voxel coordinates.
    #[pyo3(signature = (agent_id, plan_kind, points, priority=128, horizon_ticks=300, radius_m=64.0))]
    fn submit_intent(
        &self,
        agent_id: u64,
        plan_kind: &str,
        points: Vec<(i32, i32, i32)>,
        priority: u8,
        horizon_ticks: u32,
        radius_m: f32,
    ) -> PyResult<()> {
        let plan = match plan_kind {
            "idle" => {
                let (x, y, z) = *points.first().ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "`idle` requires at least one point",
                    )
                })?;
                Plan::Idle {
                    center: WorldCoord::new(x, y, z),
                    radius_m,
                }
            }
            "walk" => {
                if points.is_empty() {
                    return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "`walk` requires at least one waypoint",
                    ));
                }
                Plan::WalkAlong(
                    points
                        .into_iter()
                        .map(|(x, y, z)| WorldCoord::new(x, y, z))
                        .collect(),
                )
            }
            "teleport" => {
                let (x, y, z) = *points.first().ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "`teleport` requires one target point",
                    )
                })?;
                Plan::TeleportTo(WorldCoord::new(x, y, z))
            }
            _ => {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "unknown plan_kind: {plan_kind}"
                )));
            }
        };
        self.intent_bus.submit(Intent {
            agent: AgentId(agent_id),
            plan,
            horizon_ticks,
            priority,
        });
        Ok(())
    }

    /// Extract a mesh for a chunk at the given LOD step (1 = full, 2 = half...).
    /// Returns a dict with `vertices` (Nx9 floats: pos[3] + normal[3] + pad[3])
    /// and `indices` (list of u32 triangle indices).
    fn extract_mesh(&self, py: Python<'_>, cx: i32, cy: i32, step: u32) -> PyResult<PyObject> {
        let step = step.max(1);
        let chunk = self
            .runtime
            .block_on(async { self.manager.get_or_generate(ChunkCoord { cx, cy }).await });
        let version = chunk.read().meta.mutation_version;
        let key = MeshCacheKey {
            cx,
            cy,
            step,
            version,
        };
        if let Some(cached) = self.mesh_l2.get(&key) {
            let d = PyDict::new_bound(py);
            d.set_item("vertices", PyList::new_bound(py, &cached.flat_vertices))?;
            d.set_item("indices", PyList::new_bound(py, &cached.indices))?;
            d.set_item("vertex_count", cached.vertex_count)?;
            d.set_item("triangle_count", cached.triangle_count)?;
            d.set_item("cached", true)?;
            return Ok(d.unbind().into());
        }
        let mesh = extract_surface_nets(&*chunk.read(), step).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("mesh: {e}"))
        })?;
        let mut flat = Vec::with_capacity(mesh.vertices.len() * 7);
        for v in &mesh.vertices {
            flat.extend_from_slice(&v.pos);
            flat.extend_from_slice(&v.normal);
            flat.push(v.material as f32);
        }
        let entry = CachedMesh {
            flat_vertices: flat.clone(),
            indices: mesh.indices.clone(),
            vertex_count: mesh.vertices.len(),
            triangle_count: mesh.tri_count(),
        };
        self.mesh_l2.insert(key, entry);
        let d = PyDict::new_bound(py);
        d.set_item("vertices", PyList::new_bound(py, &flat))?;
        d.set_item("indices", PyList::new_bound(py, &mesh.indices))?;
        d.set_item("vertex_count", mesh.vertices.len())?;
        d.set_item("triangle_count", mesh.tri_count())?;
        d.set_item("cached", false)?;
        Ok(d.unbind().into())
    }

    /// Biome id at world coordinates (macro grid sample).
    fn biome_at(&self, x: f32, y: f32, _z: f32) -> PyResult<u8> {
        let coord = ChunkCoord {
            cx: (x.floor() as i32).div_euclid(CHUNK_SIZE_X as i32),
            cy: (y.floor() as i32).div_euclid(CHUNK_SIZE_Y as i32),
        };
        let chunk = self
            .runtime
            .block_on(async { self.manager.get_or_generate(coord).await });
        let guard = chunk.read();
        let lx = (x as i32).rem_euclid(CHUNK_SIZE_X as i32) as u32;
        let ly = (y as i32).rem_euclid(CHUNK_SIZE_Y as i32) as u32;
        Ok(guard.biome_at(lx, ly) as u8)
    }

    /// Generate or fetch a chunk's surface observation as a Python dict.
    fn observe_chunk(&self, py: Python<'_>, cx: i32, cy: i32) -> PyResult<PyObject> {
        let coord = ChunkCoord { cx, cy };
        let obs = self
            .runtime
            .block_on(async { self.client.observe_area(coord).await });

        let d = PyDict::new_bound(py);
        d.set_item("chunk", (obs.chunk.cx, obs.chunk.cy))?;

        let elev = PyList::new_bound(py, &obs.elevation);
        d.set_item("elevation", elev)?;

        let biome_u8: Vec<u8> = obs.biome.iter().map(|b| *b as u8).collect();
        let biomes = PyList::new_bound(py, &biome_u8);
        d.set_item("biome", biomes)?;

        let rivers = PyList::new_bound(py, &obs.river_mask);
        d.set_item("river_mask", rivers)?;

        Ok(d.unbind().into())
    }

    /// Return the biome name table — `name_for(biome_u8)`.
    #[staticmethod]
    fn biome_names() -> Vec<(&'static str, u8)> {
        vec![
            ("Ocean", Biome::Ocean as u8),
            ("CoastalSea", Biome::CoastalSea as u8),
            ("Ice", Biome::Ice as u8),
            ("Tundra", Biome::Tundra as u8),
            ("BorealForest", Biome::BorealForest as u8),
            ("TemperateForest", Biome::TemperateForest as u8),
            ("TemperateRainforest", Biome::TemperateRainforest as u8),
            ("Grassland", Biome::Grassland as u8),
            ("HotDesert", Biome::HotDesert as u8),
            ("ColdDesert", Biome::ColdDesert as u8),
            ("Savanna", Biome::Savanna as u8),
            ("TropicalDryForest", Biome::TropicalDryForest as u8),
            ("TropicalRainforest", Biome::TropicalRainforest as u8),
            ("Shrubland", Biome::Shrubland as u8),
            ("Wetland", Biome::Wetland as u8),
            ("AlpineRock", Biome::AlpineRock as u8),
        ]
    }
}

fn load_macro_grid_path(path: &str) -> std::io::Result<MacroGrid> {
    let f = File::open(Path::new(path))?;
    read_binary(f).map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))
}

/// Module entry point.
#[pymodule]
fn genesis_world(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyWorld>()?;
    Ok(())
}
