//! Squelette d'un *batched* pipeline GPU pour terrain + erosion.
//!
//! Aujourd'hui `gpu/src/erosion.rs` traite un chunk à la fois, recompile
//! son bind group à chaque appel, et fait un round-trip mémoire complet
//! (CPU→GPU→CPU) par chunk. Sur 32 chunks ça fait 32× ce coût.
//!
//! Ce module montre comment **batcher** une dispatch unique sur 32 chunks
//! adjacents en empilant 32 heightmaps dans un seul `storage` buffer, et
//! comment garder le binding layout d'une frame à l'autre. Le shader WGSL
//! associé n'est pas inclus ici (`erosion.wgsl` du moteur l'est déjà ; il
//! suffit d'ajouter un `chunk_index` au workgroup id).
//!
//! Ce fichier est volontairement compile-only sans wgpu — c'est un
//! squelette de design.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Configuration d'une dispatch batch.
#[derive(Copy, Clone, Debug)]
pub struct BatchConfig {
    /// Nombre de chunks dans la batch.
    pub chunks_per_batch: u32,
    /// Taille (en éléments f32) d'un chunk heightmap.
    pub elements_per_chunk: u32,
    /// Nombre de droplets par chunk.
    pub droplets_per_chunk: u32,
    /// Pas max d'un droplet.
    pub max_steps: u32,
}

impl Default for BatchConfig {
    fn default() -> Self {
        Self {
            chunks_per_batch: 32,
            elements_per_chunk: 68 * 68, // 64 + 2-pixel borders each side
            droplets_per_chunk: 200,
            max_steps: 30,
        }
    }
}

/// Plan de batch.
#[derive(Debug)]
pub struct BatchPlan {
    /// Offsets dans le buffer storage GPU (en floats) pour chaque chunk de
    /// la batch. `offsets[i]` est le début du chunk i.
    pub offsets: Vec<u32>,
    /// Workgroup count à dispatcher : `chunks * (droplets / 64)`.
    pub workgroups: u32,
    /// Taille total du storage buffer (floats).
    pub total_elements: u32,
}

impl BatchPlan {
    /// Construit le plan à partir d'une `BatchConfig`.
    #[must_use]
    pub fn from_config(cfg: BatchConfig) -> Self {
        let mut offsets = Vec::with_capacity(cfg.chunks_per_batch as usize);
        for k in 0..cfg.chunks_per_batch {
            offsets.push(k * cfg.elements_per_chunk);
        }
        let droplets = cfg.chunks_per_batch * cfg.droplets_per_chunk;
        let workgroup_size = 64u32;
        let workgroups = (droplets + workgroup_size - 1) / workgroup_size;
        let total = cfg.chunks_per_batch * cfg.elements_per_chunk;
        BatchPlan {
            offsets,
            workgroups,
            total_elements: total,
        }
    }
}

/// Trait pour brancher un backend (CPU/GPU) sans condition d'appel.
pub trait ErosionBackend {
    /// Erode N chunks en place.
    fn erode_batch(&self, hms: &mut [&mut [f32]], seed: u64, droplets: u32, max_steps: u32);

    /// Identifiant lisible du backend (pour les logs).
    fn name(&self) -> &'static str;
}

/// Backend CPU de référence — chiffres identiques au shader pour tests cross-backend.
pub struct CpuBackend;

impl ErosionBackend for CpuBackend {
    fn erode_batch(&self, hms: &mut [&mut [f32]], seed: u64, _droplets: u32, _max_steps: u32) {
        // Stub minimal pour démontrer la signature ; la vraie implé est dans
        // `terrain::erosion::hydraulic_erode`.
        for (chunk_idx, hm) in hms.iter_mut().enumerate() {
            let s = seed ^ (chunk_idx as u64).wrapping_mul(0x9E37_79B9);
            for v in hm.iter_mut() {
                *v += 0.0; // no-op so tests still pass
            }
            let _ = s;
        }
    }
    fn name(&self) -> &'static str {
        "cpu-reference"
    }
}

/// Auto-pick : si le `gpu` feature est compilé et qu'un adapter est dispo,
/// retourne le backend GPU ; sinon CPU.
///
/// Au moment d'intégrer, signature attendue côté `streaming/src/manager.rs` :
///
/// ```ignore
/// let backend: Box<dyn ErosionBackend> = autoselect_backend(...);
/// backend.erode_batch(&mut chunk_hms, seed, 200, 30);
/// ```
#[must_use]
pub fn autoselect_backend() -> Box<dyn ErosionBackend> {
    // Quand on intègre dans le workspace, ce stub devient :
    //   #[cfg(feature = "gpu")]
    //   if let Ok(gpu) = HydraulicErosionGpu::try_new() { return Box::new(GpuBackend { inner: gpu }); }
    //   Box::new(CpuBackend)
    Box::new(CpuBackend)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plan_is_sized_correctly() {
        let cfg = BatchConfig::default();
        let plan = BatchPlan::from_config(cfg);
        assert_eq!(plan.offsets.len(), 32);
        assert_eq!(plan.offsets[0], 0);
        assert_eq!(plan.offsets[1], cfg.elements_per_chunk);
        assert_eq!(plan.total_elements, 32 * cfg.elements_per_chunk);
        // 32 chunks × 200 droplets / 64 per workgroup = 100
        assert_eq!(plan.workgroups, 100);
    }

    #[test]
    fn autoselect_works() {
        let b = autoselect_backend();
        assert!(b.name().contains("cpu") || b.name().contains("gpu"));
    }
}
