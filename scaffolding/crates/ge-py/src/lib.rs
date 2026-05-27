//! Module Python ``genesis_world`` — bindings PyO3 pour ge-world.
//!
//! Phase 3b : numpy arrays + SplitMix64 fast noise → 5× faster than Python.
//! Phase 3c : BLAKE2b salt → bit-for-bit match avec Python terrain.
//! Phase 3d : LRU chunk cache → repeated chunk access is O(1) copy.
//! Phase 3e : GENM v2 macro grid → genesis-anchor blend in Rust.
//! Phase 3f : rayon parallel batch sampling + Python façade wrappers.
//! Wave 43 : resource computation (stone/wood/metal/water/food) in Rust.
//! Wave 44 : biome passthrough + content_root (full Chunk from Rust).

// Wave 61: relaxed to `warn` — we need limited `unsafe` for Send wrappers
// used in rayon parallelism (read-only numpy slices shared across threads).
#![warn(unsafe_code)]

mod fast_noise;

use std::collections::{HashMap, VecDeque};
use rayon::prelude::*;

use ge_core::WorldSeed;
use ge_world::{
    biome::{classify, Biome},
    chunk::{CHUNK_SIZE, VOXEL_SIZE_M},
    terrain::TerrainParams,
};
use numpy::{IntoPyArray, PyReadonlyArray1, PyReadonlyArray2, PyReadwriteArray1};
use pyo3::prelude::*;
use pyo3::types::PyDict;

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

const CHUNK_N: usize = CHUNK_SIZE * CHUNK_SIZE;
const CHUNK_SIDE_M: f32 = CHUNK_SIZE as f32 * VOXEL_SIZE_M;

/// Max chunks in LRU cache.  Each chunk = 4 × 4096 values ≈ 52 KB.
/// 256 chunks ≈ 13 MB — small enough for any machine.
const LRU_MAX_CHUNKS: usize = 256;

// ---------------------------------------------------------------------------
// Macro grid (GENM v2) — continental-scale terrain anchor
// ---------------------------------------------------------------------------

/// Parsed GENM v2 macro grid from Python GenesisWorld.
///
/// Contains bilinearly-interpolable elevation, temperature and precipitation
/// at continental scale (~31 km per cell for 128×128 / 4000 km).
#[derive(Debug, Clone)]
struct MacroGrid {
    w:       usize,
    h:       usize,
    cell_km: f32,
    /// Macro-grid origin in km (usually 0,0). Stored for diagnostics.
    #[allow(dead_code)]
    origin_x_km: f32,
    #[allow(dead_code)]
    origin_y_km: f32,
    /// Row-major [h * w] arrays.
    elev:    Vec<f32>,
    temp:    Vec<f32>,
    precip:  Vec<f32>,
}

/// Genesis anchor parameters — mirrors Python `GenesisAnchor`.
#[derive(Debug, Clone)]
struct AnchorParams {
    /// Macro km that sim coord (0,0) maps to.
    sim_origin_x_km: f32,
    sim_origin_y_km: f32,
    /// Blend factor: 1.0 = pure macro + micro residual, 0.0 = pure FBM.
    blend: f32,
    micro_amp_m:          f32,
    micro_amp_temp_c:     f32,
    micro_amp_precip_mm:  f32,
}

impl Default for AnchorParams {
    fn default() -> Self {
        Self {
            sim_origin_x_km: 2000.0,
            sim_origin_y_km: 2000.0,
            blend: 1.0,
            micro_amp_m: 80.0,
            micro_amp_temp_c: 1.5,
            micro_amp_precip_mm: 150.0,
        }
    }
}

impl MacroGrid {
    /// Parse GENM v2 binary from Python `export_macro_grid_bytes()`.
    ///
    /// Layout: GENM | ver u32 | W u32 | H u32 | cell_km f32
    ///       | ox f32 | oy f32 | elev [f32;W*H] | temp [f32;W*H]
    ///       | precip [f32;W*H] | biome [u8;W*H]   ← biome ignored by Rust
    fn parse(data: &[u8]) -> Option<Self> {
        if data.len() < 24 {
            return None;
        }
        if &data[0..4] != b"GENM" {
            return None;
        }
        let version = u32::from_le_bytes([data[4], data[5], data[6], data[7]]);
        if version != 2 {
            return None;  // Only v2 supported (need temp + precip)
        }
        let w = u32::from_le_bytes([data[8], data[9], data[10], data[11]]) as usize;
        let h = u32::from_le_bytes([data[12], data[13], data[14], data[15]]) as usize;
        let cell_km = f32::from_le_bytes([data[16], data[17], data[18], data[19]]);
        let ox = f32::from_le_bytes([data[20], data[21], data[22], data[23]]);
        let oy = f32::from_le_bytes([data[24], data[25], data[26], data[27]]);

        let n = w * h;
        let header = 28;
        let f32_bytes = n * 4;
        // 3 float arrays + 1 u8 array
        let expected = header + f32_bytes * 3 + n;
        if data.len() < expected {
            return None;
        }

        let mut off = header;
        let elev = read_f32_slice(data, off, n);
        off += f32_bytes;
        let temp = read_f32_slice(data, off, n);
        off += f32_bytes;
        let precip = read_f32_slice(data, off, n);
        // biome array follows but we don't need it — Rust re-classifies.

        Some(MacroGrid {
            w, h, cell_km,
            origin_x_km: ox,
            origin_y_km: oy,
            elev, temp, precip,
        })
    }

    /// Bilinear interpolation at (x_km, y_km) in macro-grid space.
    ///
    /// Returns (elevation_m, temp_c, precip_mm).
    /// Mirrors Python `sample_macro_grid()` exactly.
    #[inline]
    fn sample(&self, x_km: f32, y_km: f32) -> (f32, f32, f32) {
        let w = self.w;
        let h = self.h;
        let ck = self.cell_km;

        let fx = ((x_km / ck) - 0.5).clamp(0.0, (w as f32) - 1.001);
        let fy = ((y_km / ck) - 0.5).clamp(0.0, (h as f32) - 1.001);
        let ix = fx.floor() as usize;
        let iy = fy.floor() as usize;
        let tx = fx - ix as f32;
        let ty = fy - iy as f32;
        let ix1 = (ix + 1).min(w - 1);
        let iy1 = (iy + 1).min(h - 1);

        #[inline]
        fn bil(arr: &[f32], w: usize, iy: usize, ix: usize,
               iy1: usize, ix1: usize, tx: f32, ty: f32) -> f32 {
            let a = arr[iy * w + ix];
            let b = arr[iy * w + ix1];
            let c = arr[iy1 * w + ix];
            let d = arr[iy1 * w + ix1];
            a * (1.0 - tx) * (1.0 - ty) + b * tx * (1.0 - ty)
                + c * (1.0 - tx) * ty + d * tx * ty
        }

        let e = bil(&self.elev, w, iy, ix, iy1, ix1, tx, ty);
        let t = bil(&self.temp, w, iy, ix, iy1, ix1, tx, ty);
        let p = bil(&self.precip, w, iy, ix, iy1, ix1, tx, ty);
        (e, t, p)
    }
}

/// Read `n` little-endian f32 values from `data` starting at `offset`.
fn read_f32_slice(data: &[u8], offset: usize, n: usize) -> Vec<f32> {
    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        let o = offset + i * 4;
        out.push(f32::from_le_bytes([
            data[o], data[o + 1], data[o + 2], data[o + 3],
        ]));
    }
    out
}

// ---------------------------------------------------------------------------
// Biome Rust → ordinal Python
// ---------------------------------------------------------------------------

const BIOME_PY_ORD: [u8; 12] = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0,
];

#[inline]
fn biome_to_py(b: Biome) -> u8 {
    BIOME_PY_ORD[b as usize]
}

// ---------------------------------------------------------------------------
// ChunkSamples + terrain sampling
// ---------------------------------------------------------------------------

/// Données brutes d'un chunk terrain + resources.
#[derive(Clone)]
struct ChunkSamples {
    elev:   Vec<f32>,
    temp:   Vec<f32>,
    precip: Vec<f32>,
    biome:  Vec<u8>,
    // Wave 43: resources computed in Rust
    stone:  Vec<f32>,
    wood:   Vec<f32>,
    metal:  Vec<f32>,
    water:  Vec<f32>,
    food_kcal:     Vec<f32>,
    food_capacity: Vec<f32>,
}

// ---------------------------------------------------------------------------
// Resource constants (mirrors Python engine.world._BIOME_NPP etc.)
// ---------------------------------------------------------------------------

/// NPP (net primary productivity) per biome — indexed by Python ordinal 0-11.
const BIOME_NPP: [f32; 12] = [
    0.30, // 0  Ocean
    0.05, // 1  Ice
    0.15, // 2  Tundra
    0.55, // 3  BorealForest
    0.80, // 4  TemperateForest
    0.80, // 5  TemperateRainforest
    0.45, // 6  Grassland
    0.05, // 7  HotDesert
    0.05, // 8  ColdDesert
    0.45, // 9  Savanna
    0.55, // 10 TropicalDryForest
    1.00, // 11 TropicalRainforest
];

/// Base wood kg/m² per biome.
const BIOME_WOOD: [f32; 12] = [
    0.0,  // Ocean
    0.0,  // Ice
    0.0,  // Tundra
    30.0, // BorealForest
    50.0, // TemperateForest
    50.0, // TemperateRainforest
    0.0,  // Grassland
    0.0,  // HotDesert
    0.0,  // ColdDesert
    5.0,  // Savanna
    30.0, // TropicalDryForest
    80.0, // TropicalRainforest
];

/// Base stone kg/m² — higher in deserts, lower in forests.
#[inline]
fn base_stone(biome_py: u8) -> f32 {
    match biome_py {
        7 | 8 => 30.0,  // HotDesert | ColdDesert
        1 | 2 => 20.0,  // Ice | Tundra
        _ => 10.0,
    }
}

/// Spring probability per biome (for water).
#[inline]
fn spring_prob(biome_py: u8) -> f32 {
    match biome_py {
        3 | 4 | 5 | 6 | 9 | 10 | 11 | 2 => 0.02,  // Wet biomes + Tundra
        _ => 0.0,
    }
}

/// Compute resources for one cell given terrain + noise values.
///
/// 4 noise values in [0, 1) drive stone/wood/metal/water variation.
#[inline]
fn compute_cell_resources(
    elev_m: f32,
    biome_py: u8,
    noise_a: f32,
    noise_b: f32,
    noise_c: f32,
    noise_d: f32,
) -> (f32, f32, f32, f32, f32, f32) {
    let b = biome_py as usize;

    // Stone
    let stone = (base_stone(biome_py) + elev_m.max(0.0) * 0.02 + noise_a * 5.0).max(0.0);

    // Wood
    let base_w = if b < 12 { BIOME_WOOD[b] } else { 0.0 };
    let wood = if base_w > 0.0 { base_w + noise_b * 15.0 } else { 0.0 };

    // Metal
    let metal_thresh = 0.01 + elev_m.max(0.0).min(3000.0) / 60_000.0;
    let metal = if noise_c < metal_thresh { noise_d * 50.0 } else { 0.0 };

    // Water
    let mut water = 0.0_f32;
    if biome_py == 0 || elev_m < 1.5 {
        water = 1000.0;
    }
    if noise_a < spring_prob(biome_py) {
        water = water.max(200.0);
    }

    // Food
    let npp = if b < 12 { BIOME_NPP[b] } else { 0.0 };
    let food_capacity = npp * 500.0;
    let food_kcal = food_capacity;

    (stone, wood, metal, water, food_kcal, food_capacity)
}

/// Échantillonne CHUNK_N points avec bruit SplitMix64 + BLAKE2b salt.
/// Pure-FBM path (no genesis macro grid).
/// Wave 43: computes resources in the same pass.
fn sample_chunk_terrain(seed: WorldSeed, params: &TerrainParams, cx: i32, cy: i32) -> ChunkSamples {
    let ox = cx as f32 * CHUNK_SIDE_M;
    let oy = cy as f32 * CHUNK_SIDE_M;

    let salt_elev = fast_noise::layer_salt(seed, "elev");
    let salt_temp = fast_noise::layer_salt(seed, "temp");
    let salt_precip = fast_noise::layer_salt(seed, "precip");
    // Resource noise salts (deterministic per-chunk)
    let salt_res_a = fast_noise::layer_salt(seed, "res_a");
    let salt_res_b = fast_noise::layer_salt(seed, "res_b");
    let salt_res_c = fast_noise::layer_salt(seed, "res_c");
    let salt_res_d = fast_noise::layer_salt(seed, "res_d");
    let chunk_salt = (cx as u64).wrapping_mul(73856093) ^ (cy as u64).wrapping_mul(19349663);

    let mut elev   = Vec::with_capacity(CHUNK_N);
    let mut temp   = Vec::with_capacity(CHUNK_N);
    let mut precip = Vec::with_capacity(CHUNK_N);
    let mut biome  = Vec::with_capacity(CHUNK_N);
    let mut stone  = Vec::with_capacity(CHUNK_N);
    let mut wood   = Vec::with_capacity(CHUNK_N);
    let mut metal  = Vec::with_capacity(CHUNK_N);
    let mut water  = Vec::with_capacity(CHUNK_N);
    let mut food_kcal = Vec::with_capacity(CHUNK_N);
    let mut food_cap  = Vec::with_capacity(CHUNK_N);

    let scale_inv = 1.0 / params.scale_m;

    for row in 0..CHUNK_SIZE {
        for col in 0..CHUNK_SIZE {
            let wx = ox + (col as f32 + 0.5) * VOXEL_SIZE_M;
            let wy = oy + (row as f32 + 0.5) * VOXEL_SIZE_M;
            let x = wx * scale_inv;
            let y = wy * scale_inv;

            let e_raw = fast_noise::fbm_2d_with_salt(x, y, params.elev_octaves, 2.0, 0.5, salt_elev);
            let elev_m = params.sea_level_m + e_raw * params.max_elev_m;

            let lat_factor = 1.0 - (wy.abs() / 10_000_000.0).min(1.0);
            let t_noise = fast_noise::fbm_2d_with_salt(x * 0.3, y * 0.3, params.temp_octaves, 2.0, 0.5, salt_temp);
            let temp_at_sea = 30.0 * lat_factor - 5.0 + t_noise * 8.0;
            let elev_drop = (elev_m.max(0.0) / 1000.0) * 6.5;
            let temp_c = temp_at_sea - elev_drop;

            let p_raw = fast_noise::fbm_2d_with_salt(x * 0.5, y * 0.5, params.precip_octaves, 2.0, 0.55, salt_precip);
            let precip_mm = ((p_raw + 1.0) * 0.5 * 4_000.0).max(0.0);

            let b = biome_to_py(classify(temp_c, precip_mm, elev_m));

            // Resource noise: 4 pseudo-uniform values in [0, 1)
            let cell_idx = (row * CHUNK_SIZE + col) as i64;
            let na = resource_noise(cell_idx, chunk_salt, salt_res_a);
            let nb = resource_noise(cell_idx, chunk_salt, salt_res_b);
            let nc = resource_noise(cell_idx, chunk_salt, salt_res_c);
            let nd = resource_noise(cell_idx, chunk_salt, salt_res_d);

            let (s, w_, m, wt, fk, fc) = compute_cell_resources(elev_m, b, na, nb, nc, nd);

            elev.push(elev_m);
            temp.push(temp_c);
            precip.push(precip_mm);
            biome.push(b);
            stone.push(s);
            wood.push(w_);
            metal.push(m);
            water.push(wt);
            food_kcal.push(fk);
            food_cap.push(fc);
        }
    }
    ChunkSamples { elev, temp, precip, biome, stone, wood, metal, water, food_kcal, food_capacity: food_cap }
}

/// Uniform noise in [0, 1) for resource generation.
/// Uses SplitMix64 with cell index + chunk salt + layer salt.
#[inline]
fn resource_noise(cell_idx: i64, chunk_salt: u64, layer_salt: u64) -> f32 {
    let mut a = (cell_idx as u64) ^ chunk_salt ^ layer_salt;
    a = (a ^ (a >> 33)).wrapping_mul(0xff51afd7ed558ccd);
    a = (a ^ (a >> 33)).wrapping_mul(0xc4ceb9fe1a85ec53);
    a ^= a >> 33;
    (a as f64 / u64::MAX as f64) as f32
}

/// Compute content_root — 32-byte BLAKE2b-keyed hash matching Python prf_bytes.
///
/// Python equivalent:
///   prf_bytes(seed, ["chunk_root", str(cx), str(cy), str(cz)], [], 32)
///
/// Which expands to:
///   key = _seed_key(seed)  # pack 128-bit → 32 bytes (LE lo|hi + BE hi|lo)
///   h = blake2b(key=key, digest_size=32)
///   h.update(b"|chunk_root|{cx}|{cy}|{cz}")
///   return h.digest()
fn compute_content_root(seed: WorldSeed, cx: i32, cy: i32, cz: i32) -> [u8; 32] {
    // Replicate _seed_key(seed): the WorldSeed is u128.
    // Python packs: struct.pack("<QQ", lo, hi) + struct.pack(">QQ", hi, lo)
    // where lo = seed & 0xFFFFFFFFFFFFFFFF, hi = seed >> 64
    let ws = seed;
    let lo = ws as u64;
    let hi = (ws >> 64) as u64;
    let mut key = [0u8; 32];
    key[0..8].copy_from_slice(&lo.to_le_bytes());
    key[8..16].copy_from_slice(&hi.to_le_bytes());
    key[16..24].copy_from_slice(&hi.to_be_bytes());
    key[24..32].copy_from_slice(&lo.to_be_bytes());

    let mut params = blake2b_simd::Params::new();
    params.hash_length(32);
    params.key(&key);
    let mut state = params.to_state();
    // Context tags: |chunk_root|{cx}|{cy}|{cz}
    state.update(b"|chunk_root");
    state.update(b"|");
    state.update(cx.to_string().as_bytes());
    state.update(b"|");
    state.update(cy.to_string().as_bytes());
    state.update(b"|");
    state.update(cz.to_string().as_bytes());
    let hash = state.finalize();
    let mut out = [0u8; 32];
    out.copy_from_slice(&hash.as_bytes()[..32]);
    out
}

/// Genesis-anchored terrain: macro grid + micro FBM residual.
///
/// Mirrors Python `sample_terrain_with_genesis()` exactly:
/// - Macro fields sampled via bilinear interpolation
/// - Micro FBM uses "genesis_micro_elev/t/p" layer names
/// - Blend between macro and pure-FBM for elevation
/// - Adiabatic lapse from micro elevation offset
/// Wave 43: computes resources in the same pass (identical to pure-FBM path).
fn sample_chunk_terrain_genesis(
    seed: WorldSeed,
    params: &TerrainParams,
    cx: i32,
    cy: i32,
    macro_grid: &MacroGrid,
    anchor: &AnchorParams,
) -> ChunkSamples {
    let ox = cx as f32 * CHUNK_SIDE_M;
    let oy = cy as f32 * CHUNK_SIDE_M;

    // Micro residual salts — same layer names as Python genesis path.
    let salt_micro_e = fast_noise::layer_salt(seed, "genesis_micro_elev");
    let salt_micro_t = fast_noise::layer_salt(seed, "genesis_micro_t");
    let salt_micro_p = fast_noise::layer_salt(seed, "genesis_micro_p");

    // Pure-FBM salts (used if blend < 1.0).
    let salt_elev = fast_noise::layer_salt(seed, "elev");

    // Resource noise salts (same as pure-FBM path)
    let salt_res_a = fast_noise::layer_salt(seed, "res_a");
    let salt_res_b = fast_noise::layer_salt(seed, "res_b");
    let salt_res_c = fast_noise::layer_salt(seed, "res_c");
    let salt_res_d = fast_noise::layer_salt(seed, "res_d");
    let chunk_salt = (cx as u64).wrapping_mul(73856093) ^ (cy as u64).wrapping_mul(19349663);

    let scale_inv = 1.0 / params.scale_m;
    let blend = anchor.blend.clamp(0.0, 1.0);

    let mut elev   = Vec::with_capacity(CHUNK_N);
    let mut temp   = Vec::with_capacity(CHUNK_N);
    let mut precip = Vec::with_capacity(CHUNK_N);
    let mut biome  = Vec::with_capacity(CHUNK_N);
    let mut stone  = Vec::with_capacity(CHUNK_N);
    let mut wood   = Vec::with_capacity(CHUNK_N);
    let mut metal  = Vec::with_capacity(CHUNK_N);
    let mut water  = Vec::with_capacity(CHUNK_N);
    let mut food_kcal = Vec::with_capacity(CHUNK_N);
    let mut food_cap  = Vec::with_capacity(CHUNK_N);

    for row in 0..CHUNK_SIZE {
        for col in 0..CHUNK_SIZE {
            let wx = ox + (col as f32 + 0.5) * VOXEL_SIZE_M;
            let wy = oy + (row as f32 + 0.5) * VOXEL_SIZE_M;
            let x = wx * scale_inv;
            let y = wy * scale_inv;

            // Sim coords → macro km.
            let x_km = wx * 0.001 + anchor.sim_origin_x_km;
            let y_km = wy * 0.001 + anchor.sim_origin_y_km;
            let (macro_e, macro_t, macro_p) = macro_grid.sample(x_km, y_km);

            // Micro FBM residuals (same lattice as Python).
            let micro_e = fast_noise::fbm_2d_with_salt(
                x, y, params.elev_octaves, 2.0, 0.5, salt_micro_e);
            let micro_t = fast_noise::fbm_2d_with_salt(
                x * 0.3, y * 0.3, params.temp_octaves, 2.0, 0.5, salt_micro_t);
            let micro_p = fast_noise::fbm_2d_with_salt(
                x * 0.5, y * 0.5, params.precip_octaves, 2.0, 0.5, salt_micro_p);

            // Elevation: blend macro with pure-FBM if blend < 1.0.
            let blended_macro_e = if blend < 1.0 {
                let fbm_full = params.sea_level_m
                    + fast_noise::fbm_2d_with_salt(
                        x, y, params.elev_octaves, 2.0, 0.5, salt_elev)
                    * params.max_elev_m;
                macro_e * blend + fbm_full * (1.0 - blend)
            } else {
                macro_e
            };

            let micro_offset_m = micro_e * anchor.micro_amp_m;
            let elev_m = blended_macro_e + micro_offset_m;

            // Temperature: macro + marginal lapse from micro offset + jitter.
            let macro_land = blended_macro_e.max(0.0);
            let final_land = elev_m.max(0.0);
            let micro_lapse = -(final_land - macro_land) / 1000.0 * 6.5;
            let temp_c = macro_t + micro_lapse
                + micro_t * anchor.micro_amp_temp_c;

            // Precipitation: macro + jitter, floor at 0.
            let precip_mm = (macro_p + micro_p * anchor.micro_amp_precip_mm).max(0.0);

            let b = biome_to_py(classify(temp_c, precip_mm, elev_m));

            // Resource noise (same pattern as pure-FBM path)
            let cell_idx = (row * CHUNK_SIZE + col) as i64;
            let na = resource_noise(cell_idx, chunk_salt, salt_res_a);
            let nb = resource_noise(cell_idx, chunk_salt, salt_res_b);
            let nc = resource_noise(cell_idx, chunk_salt, salt_res_c);
            let nd = resource_noise(cell_idx, chunk_salt, salt_res_d);

            let (s, w_, m, wt, fk, fc) = compute_cell_resources(elev_m, b, na, nb, nc, nd);

            elev.push(elev_m);
            temp.push(temp_c);
            precip.push(precip_mm);
            biome.push(b);
            stone.push(s);
            wood.push(w_);
            metal.push(m);
            water.push(wt);
            food_kcal.push(fk);
            food_cap.push(fc);
        }
    }
    ChunkSamples { elev, temp, precip, biome, stone, wood, metal, water, food_kcal, food_capacity: food_cap }
}

// ---------------------------------------------------------------------------
// LRU cache
// ---------------------------------------------------------------------------

/// Simple bounded LRU cache for chunk terrain data.
///
/// - HashMap for O(1) lookup
/// - VecDeque for access order (back = most recent)
/// - When full, evict from front (oldest)
struct ChunkCache {
    map:      HashMap<(i32, i32), ChunkSamples>,
    order:    VecDeque<(i32, i32)>,
    max_size: usize,
}

impl ChunkCache {
    fn new(max_size: usize) -> Self {
        Self {
            map: HashMap::with_capacity(max_size),
            order: VecDeque::with_capacity(max_size),
            max_size,
        }
    }

    /// Get cached samples, promoting to most-recent if found.
    fn get(&mut self, key: (i32, i32)) -> Option<&ChunkSamples> {
        if self.map.contains_key(&key) {
            // Promote: remove from current position, push to back
            if let Some(pos) = self.order.iter().position(|k| *k == key) {
                self.order.remove(pos);
            }
            self.order.push_back(key);
            self.map.get(&key)
        } else {
            None
        }
    }

    /// Insert (or update) a chunk, evicting oldest if at capacity.
    fn insert(&mut self, key: (i32, i32), value: ChunkSamples) {
        if self.map.contains_key(&key) {
            // Update existing — promote
            if let Some(pos) = self.order.iter().position(|k| *k == key) {
                self.order.remove(pos);
            }
        } else if self.map.len() >= self.max_size {
            // Evict oldest (front of deque)
            if let Some(oldest) = self.order.pop_front() {
                self.map.remove(&oldest);
            }
        }
        self.map.insert(key, value);
        self.order.push_back(key);
    }

    fn len(&self) -> usize {
        self.map.len()
    }

    fn clear(&mut self) {
        self.map.clear();
        self.order.clear();
    }
}

impl std::fmt::Debug for ChunkCache {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ChunkCache")
            .field("len", &self.map.len())
            .field("max_size", &self.max_size)
            .finish()
    }
}

// ---------------------------------------------------------------------------
// PyWorld
// ---------------------------------------------------------------------------

/// Handle Rust vers un monde procédural avec cache LRU.
///
/// Phase 3d : les chunks terrain sont mis en cache (256 max, ~13 MB).
/// Phase 3e : macro grid (GENM v2) + genesis-anchor blend.
///
/// When a macro grid is loaded (via `macro_grid_bytes` kwarg), terrain
/// sampling blends continental-scale data with micro FBM residuals,
/// matching Python's `sample_terrain_with_genesis()` exactly.
#[pyclass]
#[derive(Debug)]
pub struct PyWorld {
    seed:       WorldSeed,
    params:     TerrainParams,
    cache:      ChunkCache,
    /// Phase 3e: parsed GENM v2 macro grid (None = pure FBM mode).
    macro_grid: Option<MacroGrid>,
    /// Phase 3e: genesis anchor parameters.
    anchor:     Option<AnchorParams>,
}

impl PyWorld {
    /// Get or compute chunk samples, using the LRU cache.
    /// Automatically dispatches to genesis-blend or pure-FBM path.
    fn get_or_compute(&mut self, cx: i32, cy: i32) -> ChunkSamples {
        let key = (cx, cy);
        if let Some(cached) = self.cache.get(key) {
            return cached.clone();
        }
        let samples = match (&self.macro_grid, &self.anchor) {
            (Some(grid), Some(anchor)) => {
                sample_chunk_terrain_genesis(
                    self.seed, &self.params, cx, cy, grid, anchor)
            }
            _ => sample_chunk_terrain(self.seed, &self.params, cx, cy),
        };
        self.cache.insert(key, samples.clone());
        samples
    }

    /// Whether this world has a macro grid loaded (genesis mode).
    fn has_macro_grid(&self) -> bool {
        self.macro_grid.is_some()
    }
}

#[pymethods]
impl PyWorld {
    #[new]
    #[pyo3(signature = (seed = 42, **kwargs))]
    fn new(seed: u64, kwargs: Option<&Bound<'_, PyDict>>) -> Self {
        let mut macro_grid = None;
        let mut anchor = None;

        if let Some(kw) = kwargs {
            // Parse GENM v2 bytes if provided.
            if let Ok(Some(obj)) = kw.get_item("macro_grid_bytes") {
                if let Ok(bytes) = obj.extract::<Vec<u8>>() {
                    macro_grid = MacroGrid::parse(&bytes);
                }
            }
            // Parse anchor parameters if macro grid was loaded.
            if macro_grid.is_some() {
                let mut ap = AnchorParams::default();
                if let Ok(Some(v)) = kw.get_item("sim_origin_x_km") {
                    if let Ok(f) = v.extract::<f32>() { ap.sim_origin_x_km = f; }
                }
                if let Ok(Some(v)) = kw.get_item("sim_origin_y_km") {
                    if let Ok(f) = v.extract::<f32>() { ap.sim_origin_y_km = f; }
                }
                if let Ok(Some(v)) = kw.get_item("blend") {
                    if let Ok(f) = v.extract::<f32>() { ap.blend = f; }
                }
                if let Ok(Some(v)) = kw.get_item("micro_amp_m") {
                    if let Ok(f) = v.extract::<f32>() { ap.micro_amp_m = f; }
                }
                if let Ok(Some(v)) = kw.get_item("micro_amp_temp_c") {
                    if let Ok(f) = v.extract::<f32>() { ap.micro_amp_temp_c = f; }
                }
                if let Ok(Some(v)) = kw.get_item("micro_amp_precip_mm") {
                    if let Ok(f) = v.extract::<f32>() { ap.micro_amp_precip_mm = f; }
                }
                anchor = Some(ap);
            }
        }

        PyWorld {
            seed: seed as WorldSeed,
            params: TerrainParams::default(),
            cache: ChunkCache::new(LRU_MAX_CHUNKS),
            macro_grid,
            anchor,
        }
    }

    /// Observe un chunk — dict avec elevation/biome/resources numpy arrays.
    ///
    /// Cached: repeated calls for the same (cx, cy) return cached data.
    /// `genesis` is True when macro grid is loaded (Phase 3e).
    /// Wave 43: includes resource arrays (stone, wood, metal, water, food_kcal, food_capacity).
    fn observe_chunk(
        &mut self,
        py: Python<'_>,
        cx: i32,
        cy: i32,
        cz: i32,
    ) -> PyResult<PyObject> {
        let s = self.get_or_compute(cx, cy);
        let has_genesis = self.has_macro_grid();

        let d = PyDict::new(py);
        d.set_item("elevation", s.elev.into_pyarray(py))?;
        d.set_item("biome",     s.biome.into_pyarray(py))?;
        d.set_item("stone",     s.stone.into_pyarray(py))?;
        d.set_item("wood",      s.wood.into_pyarray(py))?;
        d.set_item("metal",     s.metal.into_pyarray(py))?;
        d.set_item("water",     s.water.into_pyarray(py))?;
        d.set_item("food_kcal", s.food_kcal.into_pyarray(py))?;
        d.set_item("food_capacity", s.food_capacity.into_pyarray(py))?;
        d.set_item("mock",      false)?;
        d.set_item("genesis",   has_genesis)?;
        d.set_item("coord",     vec![cx, cy, cz])?;
        Ok(d.into())
    }

    /// Échantillonne terrain + resources + biome + content_root.
    ///
    /// Cached: repeated calls for the same (cx, cy) return cached data.
    /// Wave 43: includes resource arrays.
    /// Wave 44: includes biome array + content_root bytes (full Chunk data).
    #[pyo3(signature = (cx, cy, cz = 0))]
    fn sample_terrain_chunk(
        &mut self,
        py: Python<'_>,
        cx: i32,
        cy: i32,
        cz: i32,
    ) -> PyResult<PyObject> {
        let s = self.get_or_compute(cx, cy);
        let cr = compute_content_root(self.seed, cx, cy, cz);

        let d = PyDict::new(py);
        d.set_item("elev",   s.elev.into_pyarray(py))?;
        d.set_item("temp",   s.temp.into_pyarray(py))?;
        d.set_item("precip", s.precip.into_pyarray(py))?;
        d.set_item("biome",  s.biome.into_pyarray(py))?;
        d.set_item("stone",  s.stone.into_pyarray(py))?;
        d.set_item("wood",   s.wood.into_pyarray(py))?;
        d.set_item("metal",  s.metal.into_pyarray(py))?;
        d.set_item("water",  s.water.into_pyarray(py))?;
        d.set_item("food_kcal",     s.food_kcal.into_pyarray(py))?;
        d.set_item("food_capacity", s.food_capacity.into_pyarray(py))?;
        d.set_item("content_root", pyo3::types::PyBytes::new(py, &cr))?;
        Ok(d.into())
    }

    /// Biome Python (int 0-11) au point (x_m, y_m).
    #[pyo3(signature = (x, y, z = 0.0))]
    fn biome_at(&self, x: f64, y: f64, z: f64) -> u8 {
        let _ = z;
        let xf = x as f32;
        let yf = y as f32;
        let scale_inv = 1.0 / self.params.scale_m;
        let xn = xf * scale_inv;
        let yn = yf * scale_inv;

        let salt_elev = fast_noise::layer_salt(self.seed, "elev");
        let salt_temp = fast_noise::layer_salt(self.seed, "temp");
        let salt_precip = fast_noise::layer_salt(self.seed, "precip");

        let e_raw = fast_noise::fbm_2d_with_salt(xn, yn, self.params.elev_octaves, 2.0, 0.5, salt_elev);
        let elev_m = self.params.sea_level_m + e_raw * self.params.max_elev_m;
        let lat_factor = 1.0 - (yf.abs() / 10_000_000.0).min(1.0);
        let t_noise = fast_noise::fbm_2d_with_salt(xn * 0.3, yn * 0.3, self.params.temp_octaves, 2.0, 0.5, salt_temp);
        let temp_c = 30.0 * lat_factor - 5.0 + t_noise * 8.0
            - (elev_m.max(0.0) / 1000.0) * 6.5;
        let p_raw = fast_noise::fbm_2d_with_salt(xn * 0.5, yn * 0.5, self.params.precip_octaves, 2.0, 0.55, salt_precip);
        let precip_mm = ((p_raw + 1.0) * 0.5 * 4_000.0).max(0.0);

        biome_to_py(classify(temp_c, precip_mm, elev_m))
    }

    // ----- batch parallel (Phase 3f) -----------------------------------------

    /// Sample multiple chunks in parallel via rayon.
    ///
    /// Accepts a list of ``(cx, cy)`` tuples. Chunks already in the LRU
    /// cache are served from cache; uncached chunks are computed in
    /// parallel using rayon's thread pool, then inserted into the cache.
    ///
    /// Returns a list of dicts ``[{elev, temp, precip}, ...]`` in the
    /// same order as the input coordinates.
    fn sample_terrain_batch(
        &mut self,
        py: Python<'_>,
        coords: Vec<(i32, i32)>,
    ) -> PyResult<PyObject> {
        // 1. Partition: cached vs uncached.
        let mut results: Vec<Option<ChunkSamples>> = vec![None; coords.len()];
        let mut to_compute: Vec<(usize, i32, i32)> = Vec::new();

        for (i, &(cx, cy)) in coords.iter().enumerate() {
            if let Some(cached) = self.cache.get((cx, cy)) {
                results[i] = Some(cached.clone());
            } else {
                to_compute.push((i, cx, cy));
            }
        }

        // 2. Compute uncached chunks in parallel.
        if !to_compute.is_empty() {
            let seed = self.seed;
            let params = self.params.clone();
            let macro_grid = self.macro_grid.clone();
            let anchor = self.anchor.clone();

            let computed: Vec<(usize, i32, i32, ChunkSamples)> = to_compute
                .par_iter()
                .map(|&(idx, cx, cy)| {
                    let s = match (&macro_grid, &anchor) {
                        (Some(grid), Some(anc)) => {
                            sample_chunk_terrain_genesis(seed, &params, cx, cy, grid, anc)
                        }
                        _ => sample_chunk_terrain(seed, &params, cx, cy),
                    };
                    (idx, cx, cy, s)
                })
                .collect();

            // 3. Insert into cache + results (sequential, cache is not Sync).
            for (idx, cx, cy, samples) in computed {
                self.cache.insert((cx, cy), samples.clone());
                results[idx] = Some(samples);
            }
        }

        // 4. Build Python list of dicts (terrain + resources + biome + content_root).
        let seed = self.seed;
        let list = pyo3::types::PyList::empty(py);
        for (i, s) in results.into_iter().enumerate() {
            let s = s.expect("all results should be filled");
            let (cx, cy) = coords[i];
            let cr = compute_content_root(seed, cx, cy, 0);
            let d = PyDict::new(py);
            d.set_item("elev",   s.elev.into_pyarray(py))?;
            d.set_item("temp",   s.temp.into_pyarray(py))?;
            d.set_item("precip", s.precip.into_pyarray(py))?;
            d.set_item("biome",  s.biome.into_pyarray(py))?;
            d.set_item("stone",  s.stone.into_pyarray(py))?;
            d.set_item("wood",   s.wood.into_pyarray(py))?;
            d.set_item("metal",  s.metal.into_pyarray(py))?;
            d.set_item("water",  s.water.into_pyarray(py))?;
            d.set_item("food_kcal",     s.food_kcal.into_pyarray(py))?;
            d.set_item("food_capacity", s.food_capacity.into_pyarray(py))?;
            d.set_item("content_root", pyo3::types::PyBytes::new(py, &cr))?;
            list.append(d)?;
        }
        Ok(list.into())
    }

    // ----- cache management -------------------------------------------------

    /// Number of chunks currently in the Rust-side LRU cache.
    fn cached_chunk_count(&self) -> usize {
        self.cache.len()
    }

    /// Clear the Rust-side chunk cache.
    fn clear_cache(&mut self) {
        self.cache.clear();
    }

    // ----- stubs ------------------------------------------------------------

    /// No-op Phase 1 — préfetch intent.
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

    /// No-op Phase 1 — extraction de mesh.
    #[pyo3(signature = (_cx, _cy, _lod))]
    fn extract_mesh(&self, _cx: i32, _cy: i32, _lod: i32) -> PyResult<PyObject> {
        Python::with_gil(|py| {
            let d = PyDict::new(py);
            d.set_item("triangle_count", 0)?;
            d.set_item("stub", true)?;
            Ok(d.into())
        })
    }

    /// Whether the Rust backend has a macro grid loaded (genesis mode).
    fn has_genesis(&self) -> bool {
        self.macro_grid.is_some()
    }

    fn __repr__(&self) -> String {
        let genesis = if self.macro_grid.is_some() { "true" } else { "false" };
        format!(
            "genesis_world.PyWorld(seed={}, native=true, genesis={}, cached={})",
            self.seed, genesis, self.cache.len()
        )
    }
}

// ---------------------------------------------------------------------------
// Python façade functions (Phase 3f)
// ---------------------------------------------------------------------------

/// Standalone FBM 2D noise — thin wrapper over fast_noise::fbm_2d.
///
/// ``genesis_world.fbm_2d(seed, layer, x, y, octaves=6, lacunarity=2.0, gain=0.5)``
///
/// Returns a single float in [-1, 1].
#[pyfunction]
#[pyo3(signature = (seed, layer, x, y, octaves = 6, lacunarity = 2.0, gain = 0.5))]
fn py_fbm_2d(seed: u64, layer: &str, x: f32, y: f32,
             octaves: u32, lacunarity: f32, gain: f32) -> f32 {
    fast_noise::fbm_2d(seed as u128, layer, x, y, octaves, lacunarity, gain)
}

/// Standalone terrain sampler — same logic as PyWorld but stateless.
///
/// ``genesis_world.sample_terrain(seed, x_m, y_m)``
///
/// Returns ``(elev_m, temp_c, precip_mm)`` as a tuple of floats.
/// Useful for quick single-point queries without constructing a PyWorld.
#[pyfunction]
#[pyo3(signature = (seed, x_m, y_m))]
fn py_sample_terrain(seed: u64, x_m: f32, y_m: f32) -> (f32, f32, f32) {
    let params = TerrainParams::default();
    let scale_inv = 1.0 / params.scale_m;
    let x = x_m * scale_inv;
    let y = y_m * scale_inv;

    let salt_elev = fast_noise::layer_salt(seed as u128, "elev");
    let salt_temp = fast_noise::layer_salt(seed as u128, "temp");
    let salt_precip = fast_noise::layer_salt(seed as u128, "precip");

    let e_raw = fast_noise::fbm_2d_with_salt(x, y, params.elev_octaves, 2.0, 0.5, salt_elev);
    let elev_m = params.sea_level_m + e_raw * params.max_elev_m;
    let lat_factor = 1.0 - (y_m.abs() / 10_000_000.0).min(1.0);
    let t_noise = fast_noise::fbm_2d_with_salt(
        x * 0.3, y * 0.3, params.temp_octaves, 2.0, 0.5, salt_temp);
    let temp_c = 30.0 * lat_factor - 5.0 + t_noise * 8.0
        - (elev_m.max(0.0) / 1000.0) * 6.5;
    let p_raw = fast_noise::fbm_2d_with_salt(
        x * 0.5, y * 0.5, params.precip_octaves, 2.0, 0.55, salt_precip);
    let precip_mm = ((p_raw + 1.0) * 0.5 * 4_000.0).max(0.0);

    (elev_m, temp_c, precip_mm)
}

/// Layer salt — expose BLAKE2b salt derivation for determinism tests.
///
/// ``genesis_world.layer_salt(seed, layer)`` → int (u64)
#[pyfunction]
fn py_layer_salt(seed: u64, layer: &str) -> u64 {
    fast_noise::layer_salt(seed as u128, layer)
}

// ---------------------------------------------------------------------------
// Wave 52 — Rust perception: scan chunk resources
// ---------------------------------------------------------------------------

/// Nearest-resource result for one resource type.
/// Fields: (x_world, y_world, distance, quantity).
type ScanHit = (f32, f32, f32, f32);

/// Scan a chunk for the nearest water/food/shelter cell to an agent.
///
/// Single-pass over all cells — computes d², checks resource thresholds,
/// and tracks the closest match per type.  Replaces the Python
/// ``_scan_chunk`` function which required 5-14 numpy temporary arrays.
///
/// ``genesis_world.scan_chunk(water, food_kcal, wood, stone, height,
///                            chunk_ox, chunk_oy, voxel_m,
///                            agent_x, agent_y, radius,
///                            need_water, need_food, need_shelter)``
///
/// Returns ``(water_hit, food_hit, shelter_hit)`` where each hit is
/// ``None`` or ``(x, y, distance, quantity)``.
#[pyfunction]
#[pyo3(signature = (water, food_kcal, wood, stone, height,
                    chunk_ox, chunk_oy, voxel_m,
                    agent_x, agent_y, radius,
                    need_water=true, need_food=true, need_shelter=true))]
fn py_scan_chunk(
    water:     PyReadonlyArray1<'_, f32>,
    food_kcal: PyReadonlyArray1<'_, f32>,
    wood:      PyReadonlyArray1<'_, f32>,
    stone:     PyReadonlyArray1<'_, f32>,
    height:    PyReadonlyArray1<'_, f32>,
    chunk_ox:  f32,
    chunk_oy:  f32,
    voxel_m:   f32,
    agent_x:   f32,
    agent_y:   f32,
    radius:    f32,
    need_water:   bool,
    need_food:    bool,
    need_shelter: bool,
) -> (Option<ScanHit>, Option<ScanHit>, Option<ScanHit>) {
    let r2 = radius * radius;
    let w = water.as_slice().expect("water not contiguous");
    let f = food_kcal.as_slice().expect("food not contiguous");
    let wd = wood.as_slice().expect("wood not contiguous");
    let st = stone.as_slice().expect("stone not contiguous");
    let ht = height.as_slice().expect("height not contiguous");
    let n = w.len();
    // Derive grid dimensions from total element count.
    let side = (n as f32).sqrt() as usize;
    debug_assert!(side * side == n, "expected square chunk array");

    // Resource thresholds (must match Python cognition._chunk_resource_masks).
    const WATER_THRESH: f32 = 5.0;
    const FOOD_THRESH: f32 = 5.0;
    const WOOD_THRESH: f32 = 30.0;
    const STONE_THRESH: f32 = 25.0;
    const HEIGHT_THRESH: f32 = 800.0;

    let mut best_w: Option<(f32, f32, f32, f32)> = None; // (d2, x, y, qty)
    let mut best_f: Option<(f32, f32, f32, f32)> = None;
    let mut best_s: Option<(f32, f32, f32, f32)> = None;

    for row in 0..side {
        let cy = chunk_oy + (row as f32 + 0.5) * voxel_m;
        let dy = cy - agent_y;
        let dy2 = dy * dy;
        // Early row skip: if dy² already exceeds r², no cell in this row qualifies.
        if dy2 > r2 { continue; }

        for col in 0..side {
            let cx = chunk_ox + (col as f32 + 0.5) * voxel_m;
            let dx = cx - agent_x;
            let d2 = dx * dx + dy2;
            if d2 > r2 { continue; }

            let idx = row * side + col;

            if need_water && w[idx] > WATER_THRESH {
                if best_w.map_or(true, |b| d2 < b.0) {
                    best_w = Some((d2, cx, cy, w[idx]));
                }
            }
            if need_food && f[idx] > FOOD_THRESH {
                if best_f.map_or(true, |b| d2 < b.0) {
                    best_f = Some((d2, cx, cy, f[idx]));
                }
            }
            if need_shelter {
                let is_shelter = wd[idx] > WOOD_THRESH
                    || (st[idx] > STONE_THRESH && ht[idx] > HEIGHT_THRESH);
                if is_shelter && best_s.map_or(true, |b| d2 < b.0) {
                    best_s = Some((d2, cx, cy, wd[idx] + st[idx]));
                }
            }
        }
    }

    // Convert d2 → distance in the output.
    let to_hit = |opt: Option<(f32, f32, f32, f32)>| -> Option<ScanHit> {
        opt.map(|(d2, x, y, q)| (x, y, d2.sqrt(), q))
    };

    (to_hit(best_w), to_hit(best_f), to_hit(best_s))
}

// ---------------------------------------------------------------------------
// Wave 54: chunk regen in Rust — single pass, no numpy ops
// ---------------------------------------------------------------------------

/// Regenerate food + water for a single chunk in-place.
///
/// ``food[i] = food[i] * retain + capacity[i] * factor``
/// ``water[i] += rain`` (scalar broadcast)
///
/// Replaces 2 numpy ops + temp array allocation per chunk.
#[pyfunction]
#[pyo3(signature = (food_kcal, food_capacity, water, food_retain, food_factor, water_rain))]
fn py_regen_chunk(
    mut food_kcal:    PyReadwriteArray1<'_, f32>,
    food_capacity:    PyReadonlyArray1<'_, f32>,
    mut water:        PyReadwriteArray1<'_, f32>,
    food_retain:      f32,
    food_factor:      f32,
    water_rain:       f32,
) {
    let food = food_kcal.as_slice_mut().expect("food_kcal not contiguous");
    let cap = food_capacity.as_slice().expect("food_capacity not contiguous");
    let wat = water.as_slice_mut().expect("water not contiguous");
    let n = food.len();
    debug_assert_eq!(n, cap.len(), "food/cap length mismatch");
    // Single fused pass: food = food * retain + cap * factor, water += rain
    for i in 0..n {
        food[i] = food[i] * food_retain + cap[i] * food_factor;
    }
    if water_rain > 0.0 {
        for i in 0..wat.len() {
            wat[i] += water_rain;
        }
    }
}

// ---------------------------------------------------------------------------
// Wave 60: batch resource scan — ALL agents × ALL chunks in one call
// ---------------------------------------------------------------------------

/// Batch resource scan: find nearest water/food/shelter for ALL alive agents
/// across ALL supplied chunks in a single Rust call.
///
/// Replaces the per-agent Python loop in ``perceive()`` that calls
/// ``scan_chunk`` 9× per agent (cache.get + d² pruning + FFI per chunk).
/// For 50 agents: 450 FFI calls → 1 call.
///
/// Returns ``Vec<(Option<ScanHit>, Option<ScanHit>, Option<ScanHit>)>``
/// one entry per agent row (dead agents get ``(None, None, None)``).
#[pyfunction]
#[pyo3(signature = (agent_pos, agent_alive,
                    chunk_cx, chunk_cy,
                    chunk_water, chunk_food, chunk_wood, chunk_stone, chunk_height,
                    radius, voxel_m, chunk_side_m, chunk_side))]
fn py_batch_scan_resources(
    agent_pos:    PyReadonlyArray2<'_, f32>,
    agent_alive:  PyReadonlyArray1<'_, u8>,
    chunk_cx:     Vec<i32>,
    chunk_cy:     Vec<i32>,
    chunk_water:  Vec<PyReadonlyArray1<'_, f32>>,
    chunk_food:   Vec<PyReadonlyArray1<'_, f32>>,
    chunk_wood:   Vec<PyReadonlyArray1<'_, f32>>,
    chunk_stone:  Vec<PyReadonlyArray1<'_, f32>>,
    chunk_height: Vec<PyReadonlyArray1<'_, f32>>,
    radius:       f32,
    voxel_m:      f32,
    chunk_side_m: f32,
    chunk_side:   usize,
) -> Vec<(Option<ScanHit>, Option<ScanHit>, Option<ScanHit>)> {
    // Pre-extract all chunk slices (one-time cost, ~30 chunks × 5 arrays).
    let w_s: Vec<&[f32]> = chunk_water.iter()
        .map(|a| a.as_slice().expect("water contiguous")).collect();
    let f_s: Vec<&[f32]> = chunk_food.iter()
        .map(|a| a.as_slice().expect("food contiguous")).collect();
    let wd_s: Vec<&[f32]> = chunk_wood.iter()
        .map(|a| a.as_slice().expect("wood contiguous")).collect();
    let st_s: Vec<&[f32]> = chunk_stone.iter()
        .map(|a| a.as_slice().expect("stone contiguous")).collect();
    let ht_s: Vec<&[f32]> = chunk_height.iter()
        .map(|a| a.as_slice().expect("height contiguous")).collect();

    let pos = agent_pos.as_array();
    let alive = agent_alive.as_slice().expect("alive contiguous");
    let n_agents = alive.len();
    let n_chunks = chunk_cx.len();
    let r2 = radius * radius;

    // Wave 61: pre-extract agent positions into an owned Vec (avoids
    // ndarray ArrayView2 which is !Send due to raw pointer internals).
    let agent_xy: Vec<(f32, f32)> = (0..n_agents)
        .map(|i| (pos[[i, 0]], pos[[i, 1]]))
        .collect();
    let alive_v: Vec<u8> = alive.to_vec();

    const WATER_THRESH: f32 = 5.0;
    const FOOD_THRESH: f32 = 5.0;
    const WOOD_THRESH: f32 = 30.0;
    const STONE_THRESH: f32 = 25.0;
    const HEIGHT_THRESH: f32 = 800.0;

    // Scan body: computes (water, food, shelter) hits for agent i.
    let scan_one = |i: usize| -> (Option<ScanHit>, Option<ScanHit>, Option<ScanHit>) {
        if alive_v[i] == 0 { return (None, None, None); }
        let px = agent_xy[i].0;
        let py = agent_xy[i].1;

        let mut best_w: Option<(f32, f32, f32, f32)> = None; // (d2, x, y, qty)
        let mut best_f: Option<(f32, f32, f32, f32)> = None;
        let mut best_s: Option<(f32, f32, f32, f32)> = None;

        for ci in 0..n_chunks {
            let cox = chunk_cx[ci] as f32 * chunk_side_m;
            let coy = chunk_cy[ci] as f32 * chunk_side_m;
            let cx1 = cox + chunk_side_m;
            let cy1 = coy + chunk_side_m;

            let dx_e = if px < cox { cox - px }
                       else if px > cx1 { px - cx1 }
                       else { 0.0 };
            let dy_e = if py < coy { coy - py }
                       else if py > cy1 { py - cy1 }
                       else { 0.0 };
            let edge_d2 = dx_e * dx_e + dy_e * dy_e;
            if edge_d2 > r2 { continue; }

            let need_w = best_w.map_or(true, |b| b.0 > edge_d2);
            let need_f = best_f.map_or(true, |b| b.0 > edge_d2);
            let need_s = best_s.map_or(true, |b| b.0 > edge_d2);
            if !need_w && !need_f && !need_s { continue; }

            let w = w_s[ci];
            let f = f_s[ci];
            let wd = wd_s[ci];
            let st = st_s[ci];
            let ht = ht_s[ci];

            for row in 0..chunk_side {
                let cell_y = coy + (row as f32 + 0.5) * voxel_m;
                let dy = cell_y - py;
                let dy2 = dy * dy;
                if dy2 > r2 { continue; }

                for col in 0..chunk_side {
                    let cell_x = cox + (col as f32 + 0.5) * voxel_m;
                    let dx = cell_x - px;
                    let d2 = dx * dx + dy2;
                    if d2 > r2 { continue; }

                    let idx = row * chunk_side + col;

                    if need_w && w[idx] > WATER_THRESH {
                        if best_w.map_or(true, |b| d2 < b.0) {
                            best_w = Some((d2, cell_x, cell_y, w[idx]));
                        }
                    }
                    if need_f && f[idx] > FOOD_THRESH {
                        if best_f.map_or(true, |b| d2 < b.0) {
                            best_f = Some((d2, cell_x, cell_y, f[idx]));
                        }
                    }
                    if need_s {
                        let is_shelter = wd[idx] > WOOD_THRESH
                            || (st[idx] > STONE_THRESH && ht[idx] > HEIGHT_THRESH);
                        if is_shelter && best_s.map_or(true, |b| d2 < b.0) {
                            best_s = Some((d2, cell_x, cell_y, wd[idx] + st[idx]));
                        }
                    }
                }
            }
        }

        let cvt = |opt: Option<(f32, f32, f32, f32)>| -> Option<ScanHit> {
            opt.map(|(d2, x, y, q)| (x, y, d2.sqrt(), q))
        };
        (cvt(best_w), cvt(best_f), cvt(best_s))
    };

    // Wave 61: conditional rayon parallelism.
    // Below 16 agents, rayon thread-pool overhead exceeds the computation
    // cost. Above 16, the O(N × chunks × cells) work amortises the fork.
    if n_agents >= 16 {
        // SAFETY: scan_one captures only:
        // - agent_xy, alive_v, chunk_cx, chunk_cy: owned Vecs → Send+Sync
        // - w_s/f_s/wd_s/st_s/ht_s: Vec<&[f32]> where &[f32] borrows
        //   numpy buffers that outlive this function call. The closure
        //   only reads these slices, and no mutation occurs anywhere.
        //   Rayon threads share these read-only references safely.
        #[allow(unsafe_code)]
        {
            // Transmute the closure's lifetime to satisfy Send.
            // This wrapper is safe because:
            // 1. The numpy arrays live on Python's stack frame (function args)
            // 2. The rayon join point is inside this function → no escape
            // 3. All access is immutable
            struct SendWrapper<F>(F);
            unsafe impl<F> Send for SendWrapper<F> {}
            unsafe impl<F> Sync for SendWrapper<F> {}
            let wrapper = SendWrapper(&scan_one);
            (0..n_agents).into_par_iter().map(|i| (wrapper.0)(i)).collect()
        }
    } else {
        (0..n_agents).map(scan_one).collect()
    }
}

// ---------------------------------------------------------------------------
// Wave 59: Rust drives update — single pass over all agents
// ---------------------------------------------------------------------------

/// Update all agent drives in-place for one tick.
///
/// Replaces the Python for-loop in `sim._tick_drives()`.  For N agents the
/// Python loop performs ~10 float conversions + 9 array writes per agent
/// with per-element Python overhead.  Rust does a single contiguous pass.
///
/// ``genesis_world.tick_drives(alive, hunger, thirst, fatigue, sleep_arr,
///                             pain, stress, injuries, vitality,
///                             h_rate, t_rate, f_rate, s_rate,
///                             pain_dec, stress_rate, stress_dec,
///                             inj_dec, vit_inc)``
#[pyfunction]
#[pyo3(signature = (alive, hunger, thirst, fatigue, sleep_arr, pain, stress,
                    injuries, vitality,
                    h_rate, t_rate, f_rate, s_rate,
                    pain_dec, stress_rate, stress_dec, inj_dec, vit_inc))]
fn py_tick_drives(
    alive:      PyReadonlyArray1<'_, u8>,
    mut hunger:     PyReadwriteArray1<'_, f32>,
    mut thirst:     PyReadwriteArray1<'_, f32>,
    mut fatigue:    PyReadwriteArray1<'_, f32>,
    mut sleep_arr:  PyReadwriteArray1<'_, f32>,
    mut pain:       PyReadwriteArray1<'_, f32>,
    mut stress:     PyReadwriteArray1<'_, f32>,
    mut injuries:   PyReadwriteArray1<'_, f32>,
    mut vitality:   PyReadwriteArray1<'_, f32>,
    h_rate: f32,
    t_rate: f32,
    f_rate: f32,
    s_rate: f32,
    pain_dec: f32,
    stress_rate: f32,
    stress_dec: f32,
    inj_dec: f32,
    vit_inc: f32,
) {
    let a = alive.as_slice().expect("alive not contiguous");
    let h = hunger.as_slice_mut().expect("hunger not contiguous");
    let t = thirst.as_slice_mut().expect("thirst not contiguous");
    let f = fatigue.as_slice_mut().expect("fatigue not contiguous");
    let sl = sleep_arr.as_slice_mut().expect("sleep not contiguous");
    let p = pain.as_slice_mut().expect("pain not contiguous");
    let st = stress.as_slice_mut().expect("stress not contiguous");
    let inj = injuries.as_slice_mut().expect("injuries not contiguous");
    let vit = vitality.as_slice_mut().expect("vitality not contiguous");
    let n = a.len();

    for i in 0..n {
        if a[i] == 0 { continue; }
        // Core drives — increment + clamp [0, 1.5]
        h[i] = (h[i] + h_rate).min(1.5);
        t[i] = (t[i] + t_rate).min(1.5);
        f[i] = (f[i] + f_rate).min(1.5);
        sl[i] = (sl[i] + s_rate).min(1.5);
        // Pain decay
        p[i] = (p[i] - pain_dec).max(0.0);
        // Stress = f(hunger, thirst) - passive decay
        let sv = st[i] + (h[i] + t[i]) * stress_rate - stress_dec;
        st[i] = sv.max(0.0).min(1.5);
        // Injuries heal
        inj[i] = (inj[i] - inj_dec).max(0.0);
        // Vitality recovery when calm
        if h[i] < 0.4 && t[i] < 0.4 && inj[i] < 0.3 {
            vit[i] = (vit[i] + vit_inc).min(1.0);
        }
    }
}

// ---------------------------------------------------------------------------
// Wave 58: batch near-agent scan — O(N²) brute force, N ≤ 200
// ---------------------------------------------------------------------------

/// Batch near-agent scan for ALL agents in one Rust call.
///
/// For N agents, computes pairwise distances (O(N²)) and returns for each
/// alive agent the sorted list of (neighbour_index, distance) pairs within
/// `radius`.  Distances use f64 arithmetic (matching Python's `float()` of
/// f32 positions) for bit-exact determinism.
///
/// ``genesis_world.batch_near_agents(pos_xy, alive, radius, max_k=16)``
///
/// - `pos_xy`: shape (N, ≥2) float32 — agent positions (columns 0=x, 1=y)
/// - `alive`:  shape (N,) bool — alive flags
/// - `radius`: perception radius in metres
/// - `max_k`:  max neighbours per agent (default 16)
///
/// Returns `list[list[(int, float)]]` — for each row index, the sorted list
/// of `(neighbour_row, distance)`.  Dead agents get an empty list.
#[pyfunction]
#[pyo3(signature = (pos_xy, alive, radius, max_k=16))]
fn py_batch_near_agents(
    pos_xy: PyReadonlyArray2<'_, f32>,
    alive:  PyReadonlyArray1<'_, u8>,
    radius: f32,
    max_k:  usize,
) -> Vec<Vec<(u32, f64)>> {
    let pos = pos_xy.as_array();
    let a = alive.as_slice().expect("alive not contiguous");
    let n = a.len();
    let r2 = (radius as f64) * (radius as f64);

    (0..n)
        .map(|i| {
            if a[i] == 0 { return Vec::new(); }
            let xi = pos[[i, 0]] as f64;
            let yi = pos[[i, 1]] as f64;
            let mut hits: Vec<(f64, u32)> = Vec::new();
            for j in 0..n {
                if i == j || a[j] == 0 { continue; }
                let dx = (pos[[j, 0]] as f64) - xi;
                let dy = (pos[[j, 1]] as f64) - yi;
                let d2 = dx * dx + dy * dy;
                if d2 < r2 {
                    hits.push((d2, j as u32));
                }
            }
            // Sort by (d², index) for deterministic tie-break matching Python.
            hits.sort_by(|a, b| {
                a.0.partial_cmp(&b.0)
                    .unwrap_or(std::cmp::Ordering::Equal)
                    .then(a.1.cmp(&b.1))
            });
            hits.truncate(max_k);
            hits.iter().map(|&(d2, j)| (j, d2.sqrt())).collect()
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Module Python
// ---------------------------------------------------------------------------

#[pymodule]
fn genesis_world(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyWorld>()?;
    m.add_function(wrap_pyfunction!(py_fbm_2d, m)?)?;
    m.add_function(wrap_pyfunction!(py_sample_terrain, m)?)?;
    m.add_function(wrap_pyfunction!(py_layer_salt, m)?)?;
    m.add_function(wrap_pyfunction!(py_scan_chunk, m)?)?;
    m.add_function(wrap_pyfunction!(py_regen_chunk, m)?)?;
    m.add_function(wrap_pyfunction!(py_batch_near_agents, m)?)?;
    m.add_function(wrap_pyfunction!(py_tick_drives, m)?)?;
    m.add_function(wrap_pyfunction!(py_batch_scan_resources, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("CHUNK_SIZE", CHUNK_SIZE)?;
    m.add("VOXEL_SIZE_M", VOXEL_SIZE_M)?;
    m.add("CHUNK_SIDE_M", CHUNK_SIDE_M)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn biome_mapping_covers_all_variants() {
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

    #[test]
    fn sample_chunk_terrain_bounded() {
        let s = sample_chunk_terrain(42, &TerrainParams::default(), 3, 7);
        for e in &s.elev {
            assert!(e.abs() < 5000.0, "elevation out of bounds: {e}");
        }
        for b in &s.biome {
            assert!(*b < 12, "biome out of range: {b}");
        }
    }

    #[test]
    fn lru_cache_basic() {
        let mut cache = ChunkCache::new(3);
        let p = TerrainParams::default();
        let s1 = sample_chunk_terrain(42, &p, 0, 0);
        let s2 = sample_chunk_terrain(42, &p, 1, 0);
        let s3 = sample_chunk_terrain(42, &p, 2, 0);
        let s4 = sample_chunk_terrain(42, &p, 3, 0);

        cache.insert((0, 0), s1);
        cache.insert((1, 0), s2);
        cache.insert((2, 0), s3);
        assert_eq!(cache.len(), 3);

        // Access (0,0) to promote it
        assert!(cache.get((0, 0)).is_some());

        // Insert (3,0) → should evict (1,0) which is now oldest
        cache.insert((3, 0), s4);
        assert_eq!(cache.len(), 3);
        assert!(cache.get((1, 0)).is_none(), "(1,0) should be evicted");
        assert!(cache.get((0, 0)).is_some(), "(0,0) should be retained (promoted)");
        assert!(cache.get((2, 0)).is_some());
        assert!(cache.get((3, 0)).is_some());
    }

    #[test]
    fn lru_cache_clear() {
        let mut cache = ChunkCache::new(10);
        let p = TerrainParams::default();
        cache.insert((0, 0), sample_chunk_terrain(42, &p, 0, 0));
        cache.insert((1, 1), sample_chunk_terrain(42, &p, 1, 1));
        assert_eq!(cache.len(), 2);
        cache.clear();
        assert_eq!(cache.len(), 0);
    }

    // -----------------------------------------------------------------------
    // Phase 3e — GENM v2 parsing + genesis blend
    // -----------------------------------------------------------------------

    /// Build a tiny GENM v2 binary for a 4×4 macro grid.
    fn make_test_genm_v2() -> Vec<u8> {
        let w: u32 = 4;
        let h: u32 = 4;
        let cell_km: f32 = 1000.0;
        let ox: f32 = 0.0;
        let oy: f32 = 0.0;
        let n = (w * h) as usize;

        let mut buf = Vec::new();
        buf.extend_from_slice(b"GENM");
        buf.extend_from_slice(&2u32.to_le_bytes());
        buf.extend_from_slice(&w.to_le_bytes());
        buf.extend_from_slice(&h.to_le_bytes());
        buf.extend_from_slice(&cell_km.to_le_bytes());
        buf.extend_from_slice(&ox.to_le_bytes());
        buf.extend_from_slice(&oy.to_le_bytes());
        // Elevation: gradient 0..n as float * 100
        for i in 0..n {
            buf.extend_from_slice(&((i as f32) * 100.0).to_le_bytes());
        }
        // Temperature: 25.0 - i as float
        for i in 0..n {
            buf.extend_from_slice(&(25.0 - i as f32).to_le_bytes());
        }
        // Precipitation: 500 + i * 50
        for i in 0..n {
            buf.extend_from_slice(&(500.0 + i as f32 * 50.0).to_le_bytes());
        }
        // Biome: all 3 (temperate forest)
        for _ in 0..n {
            buf.push(3);
        }
        buf
    }

    #[test]
    fn genm_v2_parse_roundtrip() {
        let data = make_test_genm_v2();
        let grid = MacroGrid::parse(&data).expect("GENM v2 should parse");
        assert_eq!(grid.w, 4);
        assert_eq!(grid.h, 4);
        assert_eq!(grid.cell_km, 1000.0);
        assert_eq!(grid.elev.len(), 16);
        assert_eq!(grid.temp.len(), 16);
        assert_eq!(grid.precip.len(), 16);
        // Check first/last elevation
        assert!((grid.elev[0] - 0.0).abs() < 0.01);
        assert!((grid.elev[15] - 1500.0).abs() < 0.01);
    }

    #[test]
    fn genm_v2_bilinear_corners() {
        let data = make_test_genm_v2();
        let grid = MacroGrid::parse(&data).unwrap();
        // Sample at first cell center (0.5 * 1000 = 500 km)
        let (e, t, p) = grid.sample(500.0, 500.0);
        // Should be close to cell [0,0] = elev 0, temp 25, precip 500
        assert!((e - 0.0).abs() < 150.0, "elev={e}");
        assert!((t - 25.0).abs() < 5.0, "temp={t}");
        assert!((p - 500.0).abs() < 100.0, "precip={p}");
    }

    #[test]
    fn genm_v2_reject_v1() {
        // Build a v1 header — should be rejected.
        let mut buf = Vec::new();
        buf.extend_from_slice(b"GENM");
        buf.extend_from_slice(&1u32.to_le_bytes());
        buf.extend_from_slice(&[0u8; 100]);
        assert!(MacroGrid::parse(&buf).is_none(), "v1 should be rejected");
    }

    #[test]
    fn genesis_blend_deterministic() {
        let data = make_test_genm_v2();
        let grid = MacroGrid::parse(&data).unwrap();
        let anchor = AnchorParams {
            sim_origin_x_km: 2000.0,
            sim_origin_y_km: 2000.0,
            blend: 1.0,
            micro_amp_m: 80.0,
            micro_amp_temp_c: 1.5,
            micro_amp_precip_mm: 150.0,
        };
        let p = TerrainParams::default();
        let a = sample_chunk_terrain_genesis(42, &p, 0, 0, &grid, &anchor);
        let b = sample_chunk_terrain_genesis(42, &p, 0, 0, &grid, &anchor);
        assert_eq!(a.elev, b.elev, "genesis sampling must be deterministic");
        assert_eq!(a.biome, b.biome);
    }

    #[test]
    fn genesis_blend_produces_valid_biomes() {
        let data = make_test_genm_v2();
        let grid = MacroGrid::parse(&data).unwrap();
        let anchor = AnchorParams::default();
        let p = TerrainParams::default();
        let s = sample_chunk_terrain_genesis(42, &p, 3, 7, &grid, &anchor);
        assert_eq!(s.elev.len(), CHUNK_N);
        for b in &s.biome {
            assert!(*b < 12, "biome out of range: {b}");
        }
    }

    // -----------------------------------------------------------------------
    // Wave 43 — Resource computation tests
    // -----------------------------------------------------------------------

    #[test]
    fn resources_correct_size() {
        let s = sample_chunk_terrain(42, &TerrainParams::default(), 0, 0);
        assert_eq!(s.stone.len(), CHUNK_N);
        assert_eq!(s.wood.len(), CHUNK_N);
        assert_eq!(s.metal.len(), CHUNK_N);
        assert_eq!(s.water.len(), CHUNK_N);
        assert_eq!(s.food_kcal.len(), CHUNK_N);
        assert_eq!(s.food_capacity.len(), CHUNK_N);
    }

    #[test]
    fn resources_non_negative() {
        let s = sample_chunk_terrain(42, &TerrainParams::default(), 5, -3);
        for v in &s.stone { assert!(*v >= 0.0, "stone negative: {v}"); }
        for v in &s.wood { assert!(*v >= 0.0, "wood negative: {v}"); }
        for v in &s.metal { assert!(*v >= 0.0, "metal negative: {v}"); }
        for v in &s.water { assert!(*v >= 0.0, "water negative: {v}"); }
        for v in &s.food_kcal { assert!(*v >= 0.0, "food_kcal negative: {v}"); }
        for v in &s.food_capacity { assert!(*v >= 0.0, "food_capacity negative: {v}"); }
    }

    #[test]
    fn resources_deterministic() {
        let p = TerrainParams::default();
        let a = sample_chunk_terrain(0xCAFE, &p, 2, 4);
        let b = sample_chunk_terrain(0xCAFE, &p, 2, 4);
        assert_eq!(a.stone, b.stone);
        assert_eq!(a.wood, b.wood);
        assert_eq!(a.metal, b.metal);
        assert_eq!(a.water, b.water);
    }

    #[test]
    fn resources_genesis_has_correct_size() {
        let data = make_test_genm_v2();
        let grid = MacroGrid::parse(&data).unwrap();
        let anchor = AnchorParams::default();
        let p = TerrainParams::default();
        let s = sample_chunk_terrain_genesis(42, &p, 0, 0, &grid, &anchor);
        assert_eq!(s.stone.len(), CHUNK_N);
        assert_eq!(s.wood.len(), CHUNK_N);
        assert_eq!(s.metal.len(), CHUNK_N);
        assert_eq!(s.water.len(), CHUNK_N);
        assert_eq!(s.food_kcal.len(), CHUNK_N);
        assert_eq!(s.food_capacity.len(), CHUNK_N);
    }

    #[test]
    fn resource_noise_in_unit_range() {
        for i in 0..100 {
            let v = resource_noise(i, 0xDEAD, 0xBEEF);
            assert!(v >= 0.0 && v < 1.0, "noise out of [0,1): {v}");
        }
    }

    // -----------------------------------------------------------------------
    // Wave 44 — content_root tests
    // -----------------------------------------------------------------------

    #[test]
    fn content_root_is_32_bytes() {
        let cr = compute_content_root(42, 0, 0, 0);
        assert_eq!(cr.len(), 32);
    }

    #[test]
    fn content_root_deterministic() {
        let a = compute_content_root(42, 3, 5, 0);
        let b = compute_content_root(42, 3, 5, 0);
        assert_eq!(a, b);
    }

    #[test]
    fn content_root_varies_with_coords() {
        let a = compute_content_root(42, 0, 0, 0);
        let b = compute_content_root(42, 1, 0, 0);
        let c = compute_content_root(42, 0, 1, 0);
        assert_ne!(a, b);
        assert_ne!(a, c);
        assert_ne!(b, c);
    }
}
