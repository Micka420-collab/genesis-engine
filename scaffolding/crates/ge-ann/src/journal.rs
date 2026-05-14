//! Journal historique append-only.
//!
//! Phase 1 : écriture en JSON-lines local (1 fichier / 10 000 ticks).
//! Phase 2+ : Parquet sur MinIO + index dans CockroachDB.

use crate::event::Event;
use std::io::{self, BufWriter, Write};
use std::path::PathBuf;

/// Sink pour persister les événements.
pub trait Sink: Send {
    /// Écrit un lot d'événements.
    fn append(&mut self, events: &[Event]) -> io::Result<()>;
    /// Flush.
    fn flush(&mut self) -> io::Result<()>;
}

/// Sink JSONL (newline-delimited JSON).
pub struct JsonlSink {
    writer: BufWriter<std::fs::File>,
    path: PathBuf,
}

impl JsonlSink {
    /// Ouvre/crée le fichier en mode append.
    pub fn open(path: impl Into<PathBuf>) -> io::Result<Self> {
        let path = path.into();
        let f = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)?;
        Ok(Self { writer: BufWriter::new(f), path })
    }

    /// Chemin du fichier ouvert.
    pub fn path(&self) -> &PathBuf {
        &self.path
    }
}

impl Sink for JsonlSink {
    fn append(&mut self, events: &[Event]) -> io::Result<()> {
        for e in events {
            let line = serde_json::to_string(e)
                .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
            self.writer.write_all(line.as_bytes())?;
            self.writer.write_all(b"\n")?;
        }
        Ok(())
    }

    fn flush(&mut self) -> io::Result<()> {
        self.writer.flush()
    }
}
