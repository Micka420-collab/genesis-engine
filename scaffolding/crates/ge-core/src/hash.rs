//! Hashing pour intégrité (BLAKE3) et chaîne de signature de tick.

use blake3::Hasher;

pub type TickRoot = [u8; 32];

/// Combine le root du tick précédent avec le delta du tick courant.
pub fn chain_tick_root(prev_root: &TickRoot, tick_delta_root: &TickRoot) -> TickRoot {
    let mut h = Hasher::new();
    h.update(prev_root);
    h.update(tick_delta_root);
    *h.finalize().as_bytes()
}
