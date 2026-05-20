//! Portable binary interchange `GENM` v1 (Python export ↔ Rust load).

use crate::{MacroBridgeError, MacroGrid};
use std::io::{Read, Write};

/// Magic bytes `GENM`.
pub const MAGIC: &[u8; 4] = b"GENM";
/// Format version.
pub const VERSION: u32 = 1;

/// Write a grid to `writer` (little-endian).
pub fn write_binary<W: Write>(grid: &MacroGrid, mut w: W) -> std::io::Result<()> {
    w.write_all(MAGIC)?;
    w.write_all(&VERSION.to_le_bytes())?;
    w.write_all(&(grid.width as u32).to_le_bytes())?;
    w.write_all(&(grid.height as u32).to_le_bytes())?;
    w.write_all(&grid.cell_km.to_le_bytes())?;
    w.write_all(&grid.origin_km.0.to_le_bytes())?;
    w.write_all(&grid.origin_km.1.to_le_bytes())?;
    for v in &grid.elevation_m {
        w.write_all(&v.to_le_bytes())?;
    }
    w.write_all(&grid.biome)?;
    Ok(())
}

/// Read a grid from `reader`.
pub fn read_binary<R: Read>(mut r: R) -> Result<MacroGrid, MacroBridgeError> {
    let mut magic = [0u8; 4];
    r.read_exact(&mut magic)?;
    if magic != *MAGIC {
        return Err(MacroBridgeError::BadMagic);
    }
    let mut ver = [0u8; 4];
    r.read_exact(&mut ver)?;
    if u32::from_le_bytes(ver) != VERSION {
        return Err(MacroBridgeError::UnsupportedVersion);
    }
    let width = read_u32(&mut r)? as usize;
    let height = read_u32(&mut r)? as usize;
    let cell_km = read_f32(&mut r)?;
    let origin_x = read_f32(&mut r)?;
    let origin_y = read_f32(&mut r)?;
    let n = width
        .checked_mul(height)
        .ok_or(MacroBridgeError::SizeMismatch { expected: 0, got: 0 })?;
    let mut elevation_m = Vec::with_capacity(n);
    for _ in 0..n {
        elevation_m.push(read_f32(&mut r)?);
    }
    let mut biome = vec![0u8; n];
    r.read_exact(&mut biome)?;
    MacroGrid::from_buffers(width, height, cell_km, (origin_x, origin_y), elevation_m, biome)
}

fn read_u32<R: Read>(r: &mut R) -> std::io::Result<u32> {
    let mut b = [0u8; 4];
    r.read_exact(&mut b)?;
    Ok(u32::from_le_bytes(b))
}

fn read_f32<R: Read>(r: &mut R) -> std::io::Result<f32> {
    let mut b = [0u8; 4];
    r.read_exact(&mut b)?;
    Ok(f32::from_le_bytes(b))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_binary() {
        let g = MacroGrid::from_buffers(
            3,
            3,
            5.0,
            (1.0, 2.0),
            vec![0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0],
            vec![0, 1, 2, 3, 4, 5, 6, 7, 8],
        )
        .unwrap();
        let mut buf = Vec::new();
        write_binary(&g, &mut buf).unwrap();
        let g2 = read_binary(buf.as_slice()).unwrap();
        assert_eq!(g2.width, 3);
        assert_eq!(g2.elevation_m[4], 40.0);
    }
}
