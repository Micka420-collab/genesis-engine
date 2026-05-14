//! ge-ann — l'Annaliste.
//!
//! Composant qui détecte, classifie et archive les événements saillants
//! de la simulation (naissance, mort, innovation, conflit, fondation, etc.).
//!
//! Il opère hors du chemin chaud du tick : un buffer ring lock-free reçoit les
//! tick deltas, un thread consumer applique les détecteurs et émet sur
//! Redpanda + écrit dans le journal historique.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod event;
pub mod detectors;
pub mod lineage;
pub mod journal;

pub use event::*;
pub use detectors::*;
pub use lineage::*;
pub use journal::*;
