//! Debug overlay — produce PNG heatmaps from chunk data for dev tooling.
//!
//! Plug as new axum endpoints :
//!   GET /debug/heatmap?layer=temp&cx=0&cy=0      → PNG
//!   GET /debug/heatmap?layer=humidity&cx=0&cy=0  → PNG
//!   GET /debug/heatmap?layer=drainage&cx=0&cy=0  → PNG
//!
//! This module produces the *bytes* in-memory (axum integration is a few
//! lines at the call site). To keep this file dep-free we ship a minimal
//! PPM (P6) writer ; production should use the `image` crate.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// A 2D scalar grid we want to visualise.
#[derive(Clone, Debug)]
pub struct GridF32 {
    /// Width.
    pub w: u32,
    /// Height.
    pub h: u32,
    /// Row-major data.
    pub data: Vec<f32>,
}

/// Choose a colormap.
#[derive(Copy, Clone, Debug)]
pub enum Colormap {
    /// Single hue: black → red.
    Heat,
    /// Black → blue → cyan → green → yellow → red (a viridis-ish ramp).
    Viridis,
    /// Greyscale.
    Grey,
}

/// Auto-normalise to `[min, max]` then map through the colormap. Returns a
/// PPM-format (P6) image blob ready to write.
#[must_use]
pub fn render_ppm(g: &GridF32, cmap: Colormap) -> Vec<u8> {
    let (lo, hi) = data_range(&g.data);
    let inv = if hi - lo > 0.0 { 1.0 / (hi - lo) } else { 0.0 };
    let mut bytes = Vec::with_capacity((15 + (g.w * g.h * 3)) as usize);
    bytes.extend_from_slice(format!("P6\n{} {}\n255\n", g.w, g.h).as_bytes());
    for v in &g.data {
        let t = ((*v - lo) * inv).clamp(0.0, 1.0);
        let (r, gn, b) = sample_colormap(cmap, t);
        bytes.push(r);
        bytes.push(gn);
        bytes.push(b);
    }
    bytes
}

fn data_range(d: &[f32]) -> (f32, f32) {
    let mut lo = f32::INFINITY;
    let mut hi = f32::NEG_INFINITY;
    for v in d {
        if v.is_finite() {
            if *v < lo {
                lo = *v;
            }
            if *v > hi {
                hi = *v;
            }
        }
    }
    if !lo.is_finite() || !hi.is_finite() {
        return (0.0, 1.0);
    }
    (lo, hi)
}

fn sample_colormap(c: Colormap, t: f32) -> (u8, u8, u8) {
    let t = t.clamp(0.0, 1.0);
    match c {
        Colormap::Grey => {
            let g = (t * 255.0) as u8;
            (g, g, g)
        }
        Colormap::Heat => {
            let r = (t * 255.0) as u8;
            let g = ((t * t) * 180.0) as u8;
            let b = ((t * t * t) * 80.0) as u8;
            (r, g, b)
        }
        Colormap::Viridis => {
            // Five-stop linear ramp.
            // 0.0 dark purple → 0.25 blue → 0.5 teal → 0.75 green → 1.0 yellow
            let stops: [[f32; 3]; 5] = [
                [0.267, 0.005, 0.329],
                [0.230, 0.322, 0.546],
                [0.128, 0.567, 0.551],
                [0.369, 0.788, 0.382],
                [0.993, 0.906, 0.144],
            ];
            let s = (t * 4.0).min(3.9999);
            let i = s as usize;
            let f = s - i as f32;
            let a = stops[i];
            let b = stops[i + 1];
            let r = a[0] + (b[0] - a[0]) * f;
            let g = a[1] + (b[1] - a[1]) * f;
            let bb = a[2] + (b[2] - a[2]) * f;
            (
                (r * 255.0) as u8,
                (g * 255.0) as u8,
                (bb * 255.0) as u8,
            )
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ramp(w: u32, h: u32) -> GridF32 {
        let mut data = Vec::with_capacity((w * h) as usize);
        for j in 0..h {
            for i in 0..w {
                data.push((i as f32 / (w - 1) as f32) + 0.001 * j as f32);
            }
        }
        GridF32 { w, h, data }
    }

    #[test]
    fn ppm_starts_with_p6() {
        let g = ramp(8, 8);
        let bytes = render_ppm(&g, Colormap::Heat);
        assert!(bytes.starts_with(b"P6\n8 8\n255\n"));
    }

    #[test]
    fn output_size_matches_pixels() {
        let g = ramp(16, 10);
        let bytes = render_ppm(&g, Colormap::Viridis);
        let header_end = bytes.iter().enumerate()
            .filter(|(_, &b)| b == b'\n').nth(2).unwrap().0;
        let pixel_bytes = bytes.len() - header_end - 1;
        assert_eq!(pixel_bytes, (16 * 10 * 3));
    }

    #[test]
    fn colormaps_differ() {
        let g = ramp(4, 1);
        let a = render_ppm(&g, Colormap::Heat);
        let b = render_ppm(&g, Colormap::Viridis);
        assert_ne!(a, b);
    }
}
