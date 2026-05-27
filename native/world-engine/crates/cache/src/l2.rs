//! L2 (on-disk) content-addressed cache.
//!
//! Layout: `$root/aa/<hex(key)>.cas` where `aa` is the first byte of the key
//! in hex (256-way sharding). Each `.cas` file is a `zstd`-compressed
//! `bincode` blob, prefixed by an 8-byte magic + 8-byte version.

use crate::key::CacheKey;
use crate::CacheError;
use serde::{de::DeserializeOwned, Serialize};
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

const MAGIC: &[u8; 8] = b"GENCAS01";

/// L2 configuration.
#[derive(Clone, Debug)]
pub struct L2Config {
    /// Root directory (created if missing).
    pub root: PathBuf,
    /// Zstd compression level (1..22). 3 = sweet spot.
    pub zstd_level: i32,
}

impl L2Config {
    /// Default at `$TMP/genesis-cache`.
    #[must_use]
    pub fn default_tmp() -> Self {
        Self {
            root: std::env::temp_dir().join("genesis-cache"),
            zstd_level: 3,
        }
    }
}

/// Disk-backed L2 cache.
pub struct L2Cache {
    config: L2Config,
}

impl L2Cache {
    /// Open or create a cache at the configured root.
    pub fn open(config: L2Config) -> Result<Self, CacheError> {
        fs::create_dir_all(&config.root)?;
        Ok(Self { config })
    }

    fn path_for(&self, key: CacheKey) -> PathBuf {
        let shard = key.shard_prefix();
        let mut p = self.config.root.clone();
        p.push(shard);
        p
    }

    fn file_for(&self, key: CacheKey) -> PathBuf {
        let mut p = self.path_for(key);
        p.push(format!("{}.cas", key.to_hex()));
        p
    }

    /// Load a value if present. Returns `Ok(None)` on miss, `Err(_)` on
    /// corruption or I/O error.
    pub fn load<T: DeserializeOwned>(&self, key: CacheKey) -> Result<Option<T>, CacheError> {
        let p = self.file_for(key);
        if !p.exists() {
            return Ok(None);
        }
        let mut f = fs::File::open(&p)?;
        let mut header = [0u8; 16];
        f.read_exact(&mut header)?;
        if &header[..8] != MAGIC {
            tracing::warn!(?p, "ignoring corrupt L2 file (bad magic)");
            return Ok(None);
        }
        let mut compressed = Vec::new();
        f.read_to_end(&mut compressed)?;
        let raw = zstd::stream::decode_all(compressed.as_slice())?;
        let v: T = bincode::deserialize(&raw)?;
        Ok(Some(v))
    }

    /// Store a value. Atomic via temp-file + rename.
    pub fn store<T: Serialize>(&self, key: CacheKey, value: &T) -> Result<(), CacheError> {
        let dir = self.path_for(key);
        fs::create_dir_all(&dir)?;
        let final_path = self.file_for(key);
        let tmp_path = final_path.with_extension("tmp");

        let raw = bincode::serialize(value)?;
        let compressed = zstd::stream::encode_all(raw.as_slice(), self.config.zstd_level)?;

        {
            let mut f = fs::File::create(&tmp_path)?;
            f.write_all(MAGIC)?;
            // 8-byte version (= u64 0 for now)
            f.write_all(&0u64.to_le_bytes())?;
            f.write_all(&compressed)?;
            f.sync_data()?;
        }
        // Atomic rename
        rename_atomic(&tmp_path, &final_path)?;
        Ok(())
    }

    /// Store an already-serialized blob. The scheduler uses this when it
    /// serializes a type-erased value through `DynPass::serialize_output`.
    pub fn store_bytes(&self, key: CacheKey, payload: &[u8]) -> Result<(), CacheError> {
        let dir = self.path_for(key);
        fs::create_dir_all(&dir)?;
        let final_path = self.file_for(key);
        let tmp_path = final_path.with_extension("tmp");
        let compressed = zstd::stream::encode_all(payload, self.config.zstd_level)?;
        {
            let mut f = fs::File::create(&tmp_path)?;
            f.write_all(MAGIC)?;
            f.write_all(&0u64.to_le_bytes())?;
            f.write_all(&compressed)?;
            f.sync_data()?;
        }
        rename_atomic(&tmp_path, &final_path)?;
        Ok(())
    }

    /// Load a raw blob (the scheduler will deserialize it via the pass).
    pub fn load_bytes(&self, key: CacheKey) -> Result<Option<Vec<u8>>, CacheError> {
        let p = self.file_for(key);
        if !p.exists() {
            return Ok(None);
        }
        let mut f = fs::File::open(&p)?;
        let mut header = [0u8; 16];
        f.read_exact(&mut header)?;
        if &header[..8] != MAGIC {
            return Ok(None);
        }
        let mut compressed = Vec::new();
        f.read_to_end(&mut compressed)?;
        let raw = zstd::stream::decode_all(compressed.as_slice())?;
        Ok(Some(raw))
    }

    /// Number of `.cas` files on disk (slow; for diagnostics).
    pub fn count_entries(&self) -> Result<usize, CacheError> {
        let mut n = 0;
        for shard in fs::read_dir(&self.config.root)? {
            let shard = shard?;
            if !shard.file_type()?.is_dir() {
                continue;
            }
            for entry in fs::read_dir(shard.path())? {
                let entry = entry?;
                if entry
                    .path()
                    .extension()
                    .map(|e| e == "cas")
                    .unwrap_or(false)
                {
                    n += 1;
                }
            }
        }
        Ok(n)
    }
}

#[cfg(windows)]
fn rename_atomic(from: &Path, to: &Path) -> std::io::Result<()> {
    // On Windows, `rename` over an existing file fails; remove first.
    if to.exists() {
        let _ = fs::remove_file(to);
    }
    fs::rename(from, to)
}

#[cfg(not(windows))]
fn rename_atomic(from: &Path, to: &Path) -> std::io::Result<()> {
    fs::rename(from, to)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::key::KeyBuilder;

    #[test]
    fn store_and_load_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let cache = L2Cache::open(L2Config {
            root: dir.path().to_path_buf(),
            zstd_level: 3,
        })
        .unwrap();
        let key = KeyBuilder::new().mix_u64("x", 7).build();
        let value: Vec<u32> = (0..100).collect();
        cache.store(key, &value).unwrap();
        let back: Vec<u32> = cache.load(key).unwrap().unwrap();
        assert_eq!(value, back);
    }

    #[test]
    fn miss_returns_none() {
        let dir = tempfile::tempdir().unwrap();
        let cache = L2Cache::open(L2Config {
            root: dir.path().to_path_buf(),
            zstd_level: 3,
        })
        .unwrap();
        let key = KeyBuilder::new().mix_u64("nope", 0).build();
        let v: Option<Vec<u8>> = cache.load(key).unwrap();
        assert!(v.is_none());
    }
}
