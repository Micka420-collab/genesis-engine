//! Cross-backend equivalence test.
//!
//! Skipped at compile time when the `gpu` feature is off, and at runtime
//! when no GPU adapter is present (CI on headless boxes).

#![cfg(feature = "gpu")]

use genesis_core::Prf;
use genesis_gpu::HydraulicErosionGpu;
use genesis_terrain::{generate, hydraulic_erode, TerrainParams};

#[test]
fn gpu_and_cpu_agree_within_tolerance() {
    let prf = Prf::new(42);
    let params = TerrainParams::default();

    // CPU run.
    let mut hm_cpu = generate(prf, 0, 0, params);
    hydraulic_erode(&mut hm_cpu, 12345, 2, 256);

    // GPU run. If no adapter, the test is a no-op.
    let gpu = match HydraulicErosionGpu::try_new() {
        Ok(g) => g,
        Err(_) => {
            eprintln!("skipping: no GPU adapter");
            return;
        }
    };
    let mut hm_gpu = generate(prf, 0, 0, params);
    gpu.erode(&mut hm_gpu, 12345, 2 * 256, 30)
        .expect("gpu erode failed");

    // Tolerance is generous because parallel droplet ordering differs;
    // we're checking that the result is in the same neighbourhood, not
    // bit-identical.
    let mut max_diff = 0.0_f32;
    for (a, b) in hm_cpu.data.iter().zip(hm_gpu.data.iter()) {
        max_diff = max_diff.max((a - b).abs());
    }
    println!("max diff CPU vs GPU = {max_diff:.2} m");
    assert!(max_diff < 200.0, "CPU/GPU diverged too much: {max_diff}");
}
