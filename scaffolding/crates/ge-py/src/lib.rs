//! Module Python ``genesis_world`` — bindings PyO3 pour ge-world.
//!
//! Exposé comme ``genesis_world.PyWorld`` côté Python.  L'interface est
//! **identique** à celle de ``engine.rust_bridge.MockPyWorld`` pour
//! permettre un remplacement transparent (Phase 2 du roadmap).
//!
//! Conventions :
//! - Biomes encodés `u8`, ordinal Python (`OCEAN=0 … TROPICAL_RAINFOREST=11`).
//! - `seed` accepte tout entier positif; tronqué `u64 → u128` pour ge-core.
//! - Le constructeur accepte `**kwargs` pour la compat MockPyWorld (ignorés Phase 1).

#![forbid(unsafe_code)]

use ge_core::WorldSeed;
use ge_world::{
    biome::{classify, Biome},
    chunk::{CHUNK_SIZE, VOXEL_SIZE_M},
    terrain::{sample, TerrainParams, TerrainSample},
};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

const CHUNK_N: usize = CHUNK_SIZE * CHUNK_SIZE;
const CHUNK_SIDE_M: f32 = CHUNK_SIZE as f32 * VOXEL_SIZE_M;

// ---------------------------------------------------------------------------
// Biome Rust → ordinal Python  (synchronisé avec engine.world.Biome)
// ---------------------------------------------------------------------------

/// Mapping constant — l'index dans le tableau == biome_to_py(variant).
/// Plus rapide qu'un match en release (une indirection vs un jump-table).
const BIOME_PY_ORD: [u8; 12] = [
    // Rust enum declaration order → Python int
    1,  // Ice                → 1
    2,  // Tundra             → 2
    3,  // BorealForest       → 3
    4,  // TemperateForest    → 4
    5,  // TemperateRainforest→ 5
    6,  // Grassland          → 6
    7,  // HotDesert          → 7
    8,  // ColdDesert         → 8
    9,  // Savanna            → 9
    10, // TropicalDryForest  → 10
    11, // TropicalRainforest → 11
    0,  // Ocean              → 0
];

#[inline]
fn biome_to_py(b: Biome) -> u8 {
    // SAFETY: Biome a 12 variants, l'index est toujours < 12.
    BIOME_PY_ORD[b as usize]
}

// ---------------------------------------------------------------------------
// Terrain helpers — code partagé entre observe_chunk & sample_terrain_chunk
// ---------------------------------------------------------------------------

/// Données brutes d'un chunk : terrain samples + biomes classifiés.
struct ChunkSamples {
    elev:   Vec<f32>,
    temp:   Vec<f32>,
    precip: Vec<f32>,
    biome:  Vec<u8>,
}

/// Échantillonne CHUNK_N points (row-major, `indexing="xy"` comme numpy).
fn sample_chunk_terrain(seed: WorldSeed, params: &TerrainParams, cx: i32, cy: i32) -> ChunkSamples {
    let ox = cx as f32 * CHUNK_SIDE_M;
    let oy = cy as f32 * CHUNK_SIDE_M;

    let mut elev   = Vec::with_capacity(CHUNK_N);
    let mut temp   = Vec::with_capacity(CHUNK_N);
    let mut precip = Vec::with_capacity(CHUNK_N);
    let mut biome  = Vec::with_capacity(CHUNK_N);

    for row in 0..CHUNK_SIZE {
        for col in 0..CHUNK_SIZE {
            let wx = ox + (col as f32 + 0.5) * VOXEL_SIZE_M;
            let wy = oy + (row as f32 + 0.5) * VOXEL_SIZE_M;
            let TerrainSample { elev_m, temp_c, precip_mm } = sample(seed, params, wx, wy);
            elev.push(elev_m);
            temp.push(temp_c);
            precip.push(precip_mm);
            biome.push(biome_to_py(classify(temp_c, precip_mm, elev_m)));
        }
    }
    ChunkSamples { elev, temp, precip, biome }
}

// ---------------------------------------------------------------------------
// PyWorld
// ---------------------------------------------------------------------------

/// Handle Rust vers un monde procédural.
///
/// Interface compatible ``MockPyWorld`` :
/// `observe_chunk`, `biome_at`, `sample_terrain_chunk`,
/// `cached_chunk_count`, `submit_intent` (no-op), `extract_mesh` (no-op).
#[pyclass]
#[derive(Debug)]
pub struct PyWorld {
    seed:   WorldSeed,
    params: TerrainParams,
}

#[pymethods]
impl PyWorld {
    // ----- construction -----------------------------------------------------

    /// Crée un PyWorld.  ``**kwargs`` ignorés Phase 1 (compat MockPyWorld).
    #[new]
    #[pyo3(signature = (seed = 42, **_kwargs))]
    fn new(seed: u64, _kwargs: Option<&Bound<'_, PyDict>>) -> Self {
        PyWorld {
            seed: seed as WorldSeed,
            params: TerrainParams::default(),
        }
    }

    // ----- observation ------------------------------------------------------

    /// Observe un chunk — retourne le dict attendu par ``rust_worldgraph_tick``.
    ///
    /// Clés : ``elevation`` (list[float]), ``biome`` (list[int]),
    /// ``mock`` (False), ``genesis`` (False), ``coord`` ([cx,cy,cz]).
    fn observe_chunk(
        &self,
        py: Python<'_>,
        cx: i32,
        cy: i32,
        cz: i32,
    ) -> PyResult<PyObject> {
        let s = sample_chunk_terrain(self.seed, &self.params, cx, cy);

        let d = PyDict::new(py);
        d.set_item("elevation", PyList::new(py, s.elev.iter())?)?;
        d.set_item("biome",     PyList::new(py, s.biome.iter())?)?;
        d.set_item("mock",      false)?;
        d.set_item("genesis",   false)?;
        d.set_item("coord",     vec![cx, cy, cz])?;
        Ok(d.into())
    }

    // ----- Phase 2 : terrain délégué depuis world.py ------------------------

    /// Échantillonne heightmap/temp/precip pour un chunk entier.
    ///
    /// Retourne ``{"elev": [...], "temp": [...], "precip": [...]}``
    /// — 3 listes de CHUNK_SIZE² floats, row-major (identique à numpy xy).
    fn sample_terrain_chunk(
        &self,
        py: Python<'_>,
        cx: i32,
        cy: i32,
    ) -> PyResult<PyObject> {
        let s = sample_chunk_terrain(self.seed, &self.params, cx, cy);

        let d = PyDict::new(py);
        d.set_item("elev",   PyList::new(py, s.elev.iter())?)?;
        d.set_item("temp",   PyList::new(py, s.temp.iter())?)?;
        d.set_item("precip", PyList::new(py, s.precip.iter())?)?;
        Ok(d.into())
    }

    // ----- point queries ----------------------------------------------------

    /// Biome Python (int 0-11) au point (x_m, y_m).
    #[pyo3(signature = (x, y, z = 0.0))]
    fn biome_at(&self, x: f64, y: f64, z: f64) -> u8 {
        let _ = z;
        let s = sample(self.seed, &self.params, x as f32, y as f32);
        biome_to_py(classify(s.temp_c, s.precip_mm, s.elev_m))
    }

    // ----- stubs pour compat rust_worldgraph_tick.py ------------------------

    /// No-op Phase 1 — préfetch intent (Phase 3 : vrai scheduler async).
    #[pyo3(signature = (_agent_id, _action, _coords, priority=64, horizon_ticks=120, radius_m=48.0))]
    fn submit_intent(
        &self,
        _agent_id: u32,
        _action: &str,
        _coords: Vec<(i32, i32, i32)>,
        priority: u32,
        horizon_ticks: u32,
        radius_m: f32,
    ) {
        let _ = (priority, horizon_ticks, radius_m);
    }

    /// No-op Phase 1 — extraction de mesh (Phase 3 : vrai Marching Cubes).
    #[pyo3(signature = (_cx, _cy, _lod))]
    fn extract_mesh(&self, _cx: i32, _cy: i32, _lod: i32) -> PyResult<PyObject> {
        Python::with_gil(|py| {
            let d = PyDict::new(py);
            d.set_item("triangle_count", 0)?;
            d.set_item("stub", true)?;
            Ok(d.into())
        })
    }

    // ----- cache info -------------------------------------------------------

    /// Chunks en cache côté Rust.  Phase 1 = 0 (LRU Rust Phase 3).
    fn cached_chunk_count(&self) -> usize {
        0
    }

    // ----- dunder -----------------------------------------------------------

    fn __repr__(&self) -> String {
        format!("genesis_world.PyWorld(seed={}, native=true)", self.seed)
    }
}

// ---------------------------------------------------------------------------
// Module Python
// ---------------------------------------------------------------------------

/// Module racine ``genesis_world``.
#[pymodule]
fn genesis_world(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyWorld>()?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("CHUNK_SIZE", CHUNK_SIZE)?;
    m.add("VOXEL_SIZE_M", VOXEL_SIZE_M)?;
    m.add("CHUNK_SIDE_M", CHUNK_SIDE_M)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests unitaires (cargo test, pas besoin de Python)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn biome_mapping_covers_all_variants() {
        // Vérifie que chaque variant Rust mappe vers un ordinal 0-11 unique.
        let all = [
            Biome::Ice, Biome::Tundra, Biome::BorealForest,
            Biome::TemperateForest, Biome::TemperateRainforest, Biome::Grassland,
            Biome::HotDesert, Biome::ColdDesert, Biome::Savanna,
            Biome::TropicalDryForest, Biome::TropicalRainforest, Biome::Ocean,
        ];
        let mut seen = [false; 12];
        for b in &all {
            let py = biome_to_py(*b) as usize;
            assert!(py < 12, "ordinal out of range: {py}");
            assert!(!seen[py], "duplicate ordinal: {py}");
            seen[py] = true;
        }
        assert!(seen.iter().all(|&s| s), "not all ordinals covered");
    }

    #[test]
    fn sample_chunk_returns_correct_size() {
        let s = sample_chunk_terrain(42, &TerrainParams::default(), 0, 0);
        assert_eq!(s.elev.len(), CHUNK_N);
        assert_eq!(s.temp.len(), CHUNK_N);
        assert_eq!(s.precip.len(), CHUNK_N);
        assert_eq!(s.biome.len(), CHUNK_N);
    }

    #[test]
    fn sample_chunk_deterministic() {
        let p = TerrainParams::default();
        let a = sample_chunk_terrain(0xDEAD, &p, 5, 7);
        let b = sample_chunk_terrain(0xDEAD, &p, 5, 7);
        assert_eq!(a.elev, b.elev);
        assert_eq!(a.biome, b.biome);
    }
}
