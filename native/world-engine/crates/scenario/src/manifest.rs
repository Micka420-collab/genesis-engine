//! FAIR manifest — accompanies every run for reproducibility.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Findable / Accessible / Interoperable / Reusable manifest written next
/// to the export artefacts.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FairManifest {
    /// Unique run id (UUID-like, content-addressed).
    pub run_id: String,
    /// ISO 8601 UTC timestamp.
    pub started_at: DateTime<Utc>,
    /// ISO 8601 UTC timestamp.
    pub finished_at: DateTime<Utc>,
    /// Name of the scenario.
    pub scenario_name: String,
    /// Version of the engine that ran it.
    pub engine_version: String,
    /// 32-byte BLAKE3 of the scenario YAML, hex-encoded.
    pub scenario_hash: String,
    /// Authors copied from the scenario.
    pub authors: Vec<String>,
    /// SPDX license.
    pub license: String,
    /// Free-text keywords.
    pub keywords: Vec<String>,
    /// Optional DOI.
    pub doi: Option<String>,
    /// Per-output artefact summary.
    pub artefacts: Vec<Artefact>,
    /// Summary of the run.
    pub summary: RunSummary,
}

/// One artefact produced by the run.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Artefact {
    /// Local path (relative to the run directory).
    pub path: String,
    /// Detected format ("csv", "json", "netcdf", ...).
    pub format: String,
    /// BLAKE3 of the file content, hex-encoded.
    pub blake3: String,
    /// File size in bytes.
    pub size_bytes: u64,
}

/// Summary statistics about a run.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct RunSummary {
    /// Total ticks executed.
    pub ticks: u64,
    /// Total chunks materialised.
    pub chunks: u64,
    /// Wall-clock duration in seconds.
    pub wall_seconds: f64,
    /// Number of measurements recorded.
    pub measurements_recorded: u64,
}

/// Compute the BLAKE3 hex of a buffer.
#[must_use]
pub fn blake3_hex(bytes: &[u8]) -> String {
    blake3::hash(bytes).to_hex().to_string()
}
