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

use genesis_agent_api::WorldClient;
use genesis_biome::Biome;
use genesis_core::{ChunkCoord, WorldCoord, WorldSeed, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use genesis_intent::{AgentId, Intent, IntentBus, Plan};
use genesis_mesh::extract_surface_nets;
use genesis_streaming::manager::ChunkManagerConfig;
use genesis_streaming::ChunkManager;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

/// World handle exposed to Python.
#[pyclass(name = "PyWorld", module = "genesis_world")]
pub struct PyWorld {
    client: WorldClient,
    manager: ChunkManager,
    intent_bus: IntentBus,
    runtime: tokio::runtime::Runtime,
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
        })
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
        let chunk = self
            .runtime
            .block_on(async { self.manager.get_or_generate(ChunkCoord { cx, cy }).await });
        let mesh = extract_surface_nets(&chunk, step.max(1)).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("mesh: {e}"))
        })?;
        let d = PyDict::new_bound(py);
        let mut flat = Vec::with_capacity(mesh.vertices.len() * 7);
        for v in &mesh.vertices {
            flat.extend_from_slice(&v.pos);
            flat.extend_from_slice(&v.normal);
            flat.push(v.material as f32);
        }
        d.set_item("vertices", PyList::new_bound(py, &flat))?;
        d.set_item("indices", PyList::new_bound(py, &mesh.indices))?;
        d.set_item("vertex_count", mesh.vertices.len())?;
        d.set_item("triangle_count", mesh.tri_count())?;
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
        let lx = (x as i32).rem_euclid(CHUNK_SIZE_X as i32) as u32;
        let ly = (y as i32).rem_euclid(CHUNK_SIZE_Y as i32) as u32;
        Ok(chunk.biome_at(lx, ly) as u8)
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

/// Module entry point.
#[pymodule]
fn genesis_world(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyWorld>()?;
    Ok(())
}
