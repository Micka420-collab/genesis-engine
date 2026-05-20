//! Hot-reload pour `BiomeRegistry` (et plus largement tout YAML de
//! configuration moteur). Le but : modifier `config/biomes.yaml` et
//! voir le moteur en cours d'exécution adopter les nouvelles règles
//! sans relancer la sim ni recompiler.
//!
//! Stratégie :
//!  - Un watcher `notify` poll le mtime du fichier.
//!  - Sur changement → lit, parse, valide, *swap atomique* du registre
//!    derrière un `ArcSwap` (pas inclus ici comme dep mais trivial à ajouter).
//!
//! Pour rester compile-only sans `notify` ici, ce stub définit l'API et
//! un poller manuel : à intégrer, brancher `notify::recommended_watcher`.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use parking_lot::RwLock;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::SystemTime;

/// Une règle de biome simplifiée (YAML-mappable).
#[derive(Clone, Debug, PartialEq)]
pub struct BiomeRule {
    /// Nom du biome.
    pub name: String,
    /// Plage de température °C (min, max).
    pub temp_c: (f32, f32),
    /// Plage d'humidité [0,1] (min, max).
    pub humidity: (f32, f32),
    /// Élévation min (m).
    pub min_elev_m: f32,
    /// Élévation max (m).
    pub max_elev_m: f32,
}

/// Registre échangeable à chaud.
#[derive(Default, Debug)]
pub struct ReloadableRegistry {
    inner: RwLock<Arc<Vec<BiomeRule>>>,
    path: RwLock<Option<PathBuf>>,
    last_mtime: RwLock<Option<SystemTime>>,
}

impl ReloadableRegistry {
    /// Nouveau registre vide.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Pointer vers un fichier de config à recharger.
    pub fn bind(&self, path: &Path) {
        *self.path.write() = Some(path.to_path_buf());
        let _ = self.poll_if_changed();
    }

    /// Échange immédiat (utile pour tests).
    pub fn swap_now(&self, rules: Vec<BiomeRule>) {
        *self.inner.write() = Arc::new(rules);
    }

    /// Lit la version courante (clone bon marché : Arc).
    #[must_use]
    pub fn current(&self) -> Arc<Vec<BiomeRule>> {
        Arc::clone(&self.inner.read())
    }

    /// Sondage manuel : si le mtime du fichier a changé, reload.
    /// Retourne `true` si un reload a effectivement eu lieu.
    pub fn poll_if_changed(&self) -> Result<bool, ReloadError> {
        let path_opt = self.path.read().clone();
        let Some(path) = path_opt else {
            return Ok(false);
        };
        let meta = std::fs::metadata(&path)?;
        let mtime = meta.modified()?;
        if let Some(prev) = *self.last_mtime.read() {
            if mtime == prev {
                return Ok(false);
            }
        }
        let raw = std::fs::read_to_string(&path)?;
        let rules = parse_yaml_minimal(&raw)?;
        // Validation simple : pas de plage vide.
        for r in &rules {
            if r.temp_c.0 > r.temp_c.1 {
                return Err(ReloadError::Validation(format!(
                    "biome {}: temp_c min > max",
                    r.name
                )));
            }
        }
        *self.inner.write() = Arc::new(rules);
        *self.last_mtime.write() = Some(mtime);
        Ok(true)
    }
}

/// Erreurs du module.
#[derive(Debug, thiserror::Error)]
pub enum ReloadError {
    /// IO.
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    /// Validation des règles.
    #[error("validation: {0}")]
    Validation(String),
    /// Parsing très simple ; à remplacer par `serde_yaml`.
    #[error("parse: {0}")]
    Parse(String),
}

/// Mini-parser YAML (pas de dep). Format toléré :
/// ```yaml
/// - name: Tundra
///   temp_c: [-15, 5]
///   humidity: [0.2, 0.7]
///   min_elev_m: 0
///   max_elev_m: 1500
/// ```
fn parse_yaml_minimal(raw: &str) -> Result<Vec<BiomeRule>, ReloadError> {
    let mut out = Vec::new();
    let mut current: Option<BiomeRule> = None;
    for (lineno, line_raw) in raw.lines().enumerate() {
        let line = line_raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if line.starts_with("- name:") {
            if let Some(c) = current.take() {
                out.push(c);
            }
            let v = line.trim_start_matches("- name:").trim().trim_matches('"').to_string();
            current = Some(BiomeRule {
                name: v,
                temp_c: (0.0, 0.0),
                humidity: (0.0, 0.0),
                min_elev_m: 0.0,
                max_elev_m: 0.0,
            });
            continue;
        }
        let Some(ref mut cur) = current else {
            return Err(ReloadError::Parse(format!("line {lineno}: expected '- name:' first")));
        };
        if let Some(rest) = line.strip_prefix("temp_c:") {
            cur.temp_c = parse_pair(rest, lineno)?;
        } else if let Some(rest) = line.strip_prefix("humidity:") {
            cur.humidity = parse_pair(rest, lineno)?;
        } else if let Some(rest) = line.strip_prefix("min_elev_m:") {
            cur.min_elev_m = rest.trim().parse().map_err(|e| ReloadError::Parse(format!("line {lineno}: {e}")))?;
        } else if let Some(rest) = line.strip_prefix("max_elev_m:") {
            cur.max_elev_m = rest.trim().parse().map_err(|e| ReloadError::Parse(format!("line {lineno}: {e}")))?;
        }
    }
    if let Some(c) = current {
        out.push(c);
    }
    Ok(out)
}

fn parse_pair(s: &str, lineno: usize) -> Result<(f32, f32), ReloadError> {
    let inner = s.trim().trim_start_matches('[').trim_end_matches(']');
    let mut parts = inner.split(',');
    let a = parts
        .next()
        .ok_or_else(|| ReloadError::Parse(format!("line {lineno}: missing min")))?
        .trim()
        .parse::<f32>()
        .map_err(|e| ReloadError::Parse(format!("line {lineno}: {e}")))?;
    let b = parts
        .next()
        .ok_or_else(|| ReloadError::Parse(format!("line {lineno}: missing max")))?
        .trim()
        .parse::<f32>()
        .map_err(|e| ReloadError::Parse(format!("line {lineno}: {e}")))?;
    Ok((a, b))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_minimal_yaml() {
        let raw = "- name: Tundra\n  temp_c: [-15, 5]\n  humidity: [0.2, 0.7]\n  min_elev_m: 0\n  max_elev_m: 1500\n";
        let rules = parse_yaml_minimal(raw).unwrap();
        assert_eq!(rules.len(), 1);
        assert_eq!(rules[0].name, "Tundra");
        assert_eq!(rules[0].temp_c, (-15.0, 5.0));
    }

    #[test]
    fn swap_replaces_atomically() {
        let r = ReloadableRegistry::new();
        r.swap_now(vec![BiomeRule {
            name: "A".into(),
            temp_c: (0.0, 10.0),
            humidity: (0.1, 0.9),
            min_elev_m: 0.0,
            max_elev_m: 100.0,
        }]);
        let before = r.current();
        r.swap_now(vec![]);
        let after = r.current();
        assert_eq!(before.len(), 1);
        assert_eq!(after.len(), 0);
    }

    #[test]
    fn yaml_change_updates_registry() {
        let tmp = std::env::temp_dir().join("biome_test_reload.yaml");
        std::fs::write(&tmp, "- name: A\n  temp_c: [0, 10]\n  humidity: [0, 1]\n  min_elev_m: 0\n  max_elev_m: 100\n").unwrap();
        let reg = ReloadableRegistry::new();
        reg.bind(&tmp);
        assert_eq!(reg.current().len(), 1);
        assert_eq!(reg.current()[0].name, "A");
        // Force a different mtime: sleep and rewrite.
        std::thread::sleep(std::time::Duration::from_millis(10));
        std::fs::write(&tmp, "- name: B\n  temp_c: [0, 10]\n  humidity: [0, 1]\n  min_elev_m: 0\n  max_elev_m: 100\n- name: C\n  temp_c: [10, 20]\n  humidity: [0, 1]\n  min_elev_m: 0\n  max_elev_m: 100\n").unwrap();
        let changed = reg.poll_if_changed().unwrap();
        assert!(changed);
        assert_eq!(reg.current().len(), 2);
        let _ = std::fs::remove_file(&tmp);
    }
}
