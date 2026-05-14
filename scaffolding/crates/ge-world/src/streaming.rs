//! Streaming des chunks — chargement/déchargement à la demande.
//!
//! Stratégie Phase 1 (mono-node) :
//! - Une zone active = ensemble des chunks dans un rayon `view_radius_chunks` autour
//!   de chaque agent (ou caméra observer).
//! - On charge tout chunk actif manquant.
//! - On décharge tout chunk inactif depuis `keep_alive_ticks`.
//!
//! Phase 2+ : ajouter une priority queue + un budget de génération par tick.

use crate::chunk::{generate_chunk, Chunk};
use crate::terrain::TerrainParams;
use ge_core::{ChunkCoord, Tick, WorldSeed};
use std::collections::HashMap;
use tracing::{debug, info};

/// Cache de chunks générés.
pub struct ChunkStreamer {
    /// Cache de chunks générés.
    pub cache: HashMap<ChunkCoord, Chunk>,
    /// Dernier tick où le chunk a été marqué actif.
    pub last_touch: HashMap<ChunkCoord, Tick>,
    /// Combien de ticks on garde un chunk inactif avant unload.
    pub keep_alive_ticks: u64,
    /// Paramètres de génération.
    pub params: TerrainParams,
    /// Seed du monde.
    pub seed: WorldSeed,
}

impl ChunkStreamer {
    /// Constructeur.
    pub fn new(seed: WorldSeed, params: TerrainParams) -> Self {
        Self {
            cache: HashMap::new(),
            last_touch: HashMap::new(),
            keep_alive_ticks: 10_000,
            params,
            seed,
        }
    }

    /// Marque les chunks dans `area` comme actifs et les génère si besoin.
    pub fn touch_area(&mut self, tick: Tick, area: impl Iterator<Item = ChunkCoord>) {
        for c in area {
            self.last_touch.insert(c, tick);
            if !self.cache.contains_key(&c) {
                let chunk = generate_chunk(self.seed, c, &self.params);
                debug!(?c, "generated chunk");
                self.cache.insert(c, chunk);
            }
        }
    }

    /// Décharge les chunks inactifs depuis trop longtemps.
    pub fn gc(&mut self, tick: Tick) {
        let cutoff = tick.get().saturating_sub(self.keep_alive_ticks);
        let to_drop: Vec<ChunkCoord> = self
            .last_touch
            .iter()
            .filter_map(|(c, t)| if t.get() < cutoff { Some(*c) } else { None })
            .collect();
        for c in &to_drop {
            self.cache.remove(c);
            self.last_touch.remove(c);
        }
        if !to_drop.is_empty() {
            info!(count = to_drop.len(), "gc unloaded chunks");
        }
    }

    /// Récupère un chunk (déjà chargé sinon génère).
    pub fn get(&mut self, tick: Tick, coord: ChunkCoord) -> &Chunk {
        if !self.cache.contains_key(&coord) {
            self.cache.insert(coord, generate_chunk(self.seed, coord, &self.params));
        }
        self.last_touch.insert(coord, tick);
        self.cache.get(&coord).unwrap()
    }
}

/// Génère l'ensemble des chunks dans un rayon Tchebychev autour d'un centre.
pub fn area_around(center: ChunkCoord, radius: i32) -> impl Iterator<Item = ChunkCoord> {
    let r = radius;
    let cx = center.x;
    let cy = center.y;
    let cz = center.z;
    (-r..=r).flat_map(move |dy| (-r..=r).map(move |dx| ChunkCoord::new(cx + dx, cy + dy, cz)))
}
