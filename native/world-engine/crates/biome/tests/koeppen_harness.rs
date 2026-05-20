//! Integration harness — Köppen reference climates (CI gate).

use genesis_biome::{harness_pass_rate, KoeppenClass, REFERENCE_CLIMATES};

#[test]
fn reference_climates_report() {
    let mut mismatches = Vec::new();
    for r in REFERENCE_CLIMATES {
        let got = KoeppenClass::classify(r.temp_annual_c, r.temp_coldest_c, r.precip_annual_mm);
        if got != r.expected {
            mismatches.push((r.name, r.expected.code(), got.code()));
        }
    }
    let rate = harness_pass_rate();
    eprintln!(
        "Köppen harness: {:.0}% ({}/{})",
        rate * 100.0,
        REFERENCE_CLIMATES.len() - mismatches.len(),
        REFERENCE_CLIMATES.len()
    );
    for (name, exp, got) in &mismatches {
        eprintln!("  mismatch {name}: expected {exp}, got {got}");
    }
    assert!(
        rate >= 0.5,
        "harness pass rate {:.0}% below 50% gate",
        rate * 100.0
    );
}
