//! Pseudo-Random Function (PRF) — la clé du déterminisme.
//!
//! Tout aléa dans la simulation doit dériver d'un PRF indexé par
//! (world_seed, contexte, paramètres). Aucun appel à `rand::thread_rng()`
//! n'est autorisé — un lint cargo-check le bloque.
//!
//! Construction : BLAKE3 keyed → seed → ChaCha20.

use blake3;
use rand_chacha::ChaCha20Rng;
use rand::SeedableRng;

/// Seed de monde (u128).
pub type WorldSeed = u128;

/// Construit un RNG déterministe à partir d'un contexte.
///
/// Exemple (illustratif — voir les tests pour de vrais appels) :
/// ```ignore
/// let rng = prf_rng(world_seed, &["world", "chunk", "stone_density"], &[chunk_x as u64, chunk_y as u64]);
/// ```
pub fn prf_rng(seed: WorldSeed, ctx: &[&str], indices: &[u64]) -> ChaCha20Rng {
    let mut hasher = blake3::Hasher::new_keyed(&seed_to_key(seed));
    for c in ctx {
        hasher.update(b"|");
        hasher.update(c.as_bytes());
    }
    for i in indices {
        hasher.update(b"|");
        hasher.update(&i.to_le_bytes());
    }
    let out = hasher.finalize();
    ChaCha20Rng::from_seed(*out.as_bytes())
}

fn seed_to_key(seed: WorldSeed) -> [u8; 32] {
    let mut out = [0u8; 32];
    out[..16].copy_from_slice(&seed.to_le_bytes());
    out[16..].copy_from_slice(&seed.to_be_bytes());
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::Rng;

    #[test]
    fn determinism() {
        let seed = 42_u128;
        let mut r1 = prf_rng(seed, &["test"], &[1, 2, 3]);
        let mut r2 = prf_rng(seed, &["test"], &[1, 2, 3]);
        let a: u64 = r1.gen();
        let b: u64 = r2.gen();
        assert_eq!(a, b);
    }

    #[test]
    fn different_context_differs() {
        let seed = 42_u128;
        let mut r1 = prf_rng(seed, &["a"], &[1]);
        let mut r2 = prf_rng(seed, &["b"], &[1]);
        let a: u64 = r1.gen();
        let b: u64 = r2.gen();
        assert_ne!(a, b);
    }
}
