//! Pas Saint-Venant CPU de référence — "pipe model" 4-voisins.
//!
//! Schéma symétrique :
//! - phase 1 : chaque cellule calcule un flux *vers* ses 4 voisins
//!   à partir du gradient de surface (terrain + eau). Le flux est
//!   borné par l'eau disponible (scaling).
//! - phase 2 : chaque cellule applique
//!   `nouvelle_eau = eau - sum(flux_sortants) + sum(flux_entrants)`.
//!
//! Cette construction garantit la **conservation de masse exacte**
//! (à la précision FP près) quand pluie/infiltration/évaporation
//! sont désactivées : chaque flux entre A et B est compté +1 fois
//! comme entrant pour B et -1 fois comme sortant pour A.
//!
//! Frontières : flux Neumann (no-flow) — l'eau ne quitte pas la grille.

use serde::{Deserialize, Serialize};

/// Paramètres du pas hydraulique.
///
/// Toutes les valeurs sont en SI sauf indication.
#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct HydroParams {
    /// Taille d'une cellule (m).
    pub dx: f32,
    /// Pas de temps simulé (s).
    pub dt: f32,
    /// Coefficient du "pipe model" (m/s par mètre de différence de
    /// surface). Calibré sur Saint-Venant linéarisé.
    pub pipe_coefficient: f32,
    /// Taux de pluie uniforme (m/s).
    pub rain_rate: f32,
    /// Taux d'infiltration vers le sol (m/s).
    pub k_infiltration: f32,
    /// Taux d'évaporation relatif (fraction de la colonne par seconde).
    pub k_evaporation: f32,
}

impl HydroParams {
    /// Paramètres "conservatifs" : ni pluie ni infiltration ni
    /// évaporation. Utilisé pour valider la conservation de masse
    /// dans les tests.
    pub fn closed() -> Self {
        Self {
            dx: 1.0,
            dt: 0.1,
            pipe_coefficient: 1.0,
            rain_rate: 0.0,
            k_infiltration: 0.0,
            k_evaporation: 0.0,
        }
    }

    /// Paramètres "calibrés Colorado River" — un point de départ
    /// raisonnable pour l'érosion fluviale terrestre.
    pub fn colorado_default() -> Self {
        Self {
            dx: 1.0,
            dt: 0.1,
            pipe_coefficient: 0.5,
            rain_rate: 1e-6,
            k_infiltration: 1e-5,
            k_evaporation: 1e-7,
        }
    }
}

/// Grille hydraulique 2D régulière.
///
/// `terrain[idx]` est l'altitude de la roche (immuable durant la
/// simulation de l'eau ; l'érosion modifiera cette couche dans un
/// autre module). `water[idx]` est la hauteur d'eau (m) au-dessus
/// du terrain.
#[derive(Clone, Debug)]
pub struct HydroGrid {
    /// Largeur (nb cellules en x).
    pub width: usize,
    /// Hauteur (nb cellules en y).
    pub height: usize,
    /// Altitude du terrain (m). Lecture seule pendant `step`.
    pub terrain: Vec<f32>,
    /// Hauteur d'eau (m). Modifiée par `step`.
    pub water: Vec<f32>,
}

impl HydroGrid {
    /// Crée une grille `width × height` plate, sans eau.
    pub fn flat(width: usize, height: usize) -> Self {
        Self {
            width,
            height,
            terrain: vec![0.0; width * height],
            water: vec![0.0; width * height],
        }
    }

    /// Index linéaire `(x, y) -> idx`.
    #[inline]
    pub fn idx(&self, x: usize, y: usize) -> usize {
        y * self.width + x
    }

    /// Volume total d'eau (m³, en supposant `dx`=1m²). Calculé en
    /// `f64` pour minimiser l'erreur de sommation FP — indispensable
    /// pour valider la conservation de masse sur grandes grilles.
    pub fn total_water(&self) -> f64 {
        self.water.iter().map(|&w| w as f64).sum()
    }

    /// Applique un pas de simulation Saint-Venant.
    pub fn step(&mut self, params: &HydroParams) {
        let w = self.width;
        let h = self.height;
        let n = w * h;
        debug_assert_eq!(self.terrain.len(), n, "terrain/water size mismatch");
        debug_assert_eq!(self.water.len(), n);

        // Phase 1 : calcul des flux sortants par voisin.
        let mut flux_n = vec![0.0f32; n];
        let mut flux_s = vec![0.0f32; n];
        let mut flux_e = vec![0.0f32; n];
        let mut flux_w = vec![0.0f32; n];

        for y in 0..h {
            for x in 0..w {
                let idx = y * w + x;
                let wv = self.water[idx];
                if wv <= 0.0 {
                    continue;
                }
                let s = self.terrain[idx] + wv;

                let mut fn_ = 0.0;
                let mut fs = 0.0;
                let mut fe = 0.0;
                let mut fw_ = 0.0;

                if y + 1 < h {
                    let nidx = idx + w;
                    let dh = s - (self.terrain[nidx] + self.water[nidx]);
                    if dh > 0.0 {
                        fn_ = params.pipe_coefficient * dh * params.dt;
                    }
                }
                if y >= 1 {
                    let nidx = idx - w;
                    let dh = s - (self.terrain[nidx] + self.water[nidx]);
                    if dh > 0.0 {
                        fs = params.pipe_coefficient * dh * params.dt;
                    }
                }
                if x + 1 < w {
                    let nidx = idx + 1;
                    let dh = s - (self.terrain[nidx] + self.water[nidx]);
                    if dh > 0.0 {
                        fe = params.pipe_coefficient * dh * params.dt;
                    }
                }
                if x >= 1 {
                    let nidx = idx - 1;
                    let dh = s - (self.terrain[nidx] + self.water[nidx]);
                    if dh > 0.0 {
                        fw_ = params.pipe_coefficient * dh * params.dt;
                    }
                }

                // Borne le flux total à l'eau disponible.
                let total = fn_ + fs + fe + fw_;
                let scale = if total > wv { wv / total } else { 1.0 };

                flux_n[idx] = fn_ * scale;
                flux_s[idx] = fs * scale;
                flux_e[idx] = fe * scale;
                flux_w[idx] = fw_ * scale;
            }
        }

        // Phase 2 : application symétrique (gain - perte) + sources/puits.
        for y in 0..h {
            for x in 0..w {
                let idx = y * w + x;

                let out = flux_n[idx] + flux_s[idx] + flux_e[idx] + flux_w[idx];

                let mut inflow = 0.0;
                if y >= 1 {
                    // Voisin du sud a envoyé NORD vers nous.
                    inflow += flux_n[idx - w];
                }
                if y + 1 < h {
                    // Voisin du nord a envoyé SUD vers nous.
                    inflow += flux_s[idx + w];
                }
                if x >= 1 {
                    // Voisin de l'ouest a envoyé EST vers nous.
                    inflow += flux_e[idx - 1];
                }
                if x + 1 < w {
                    // Voisin de l'est a envoyé OUEST vers nous.
                    inflow += flux_w[idx + 1];
                }

                let mut new_w = self.water[idx] - out + inflow;

                // Sources/puits — désactivés si params == closed().
                new_w += params.rain_rate * params.dt;
                let infil = (params.k_infiltration * params.dt).min(new_w);
                new_w -= infil;
                new_w -= new_w * params.k_evaporation * params.dt;

                if new_w < 0.0 {
                    new_w = 0.0;
                }
                self.water[idx] = new_w;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;
    use rand::Rng;
    use rand_chacha::ChaCha20Rng;

    /// Property test : sur un système fermé (sans pluie/infiltration/
    /// évaporation), la masse totale d'eau ne dérive pas significativement
    /// sur 100 pas, pour 10 graines aléatoires.
    ///
    /// Tolérance : 1e-2 m³ absolue. Sur un système d'env. 256 m³ d'eau,
    /// cela représente 4e-5 d'erreur relative — bien sous les exigences
    /// physiques. La marge couvre l'erreur cumulée de FP au cas où la
    /// borne `wv/total*total` introduit 1 ULP par cellule saturée
    /// (~1e-7 par event × 256 × 100 events worst case ≈ 2.5e-3).
    #[test]
    fn water_step_conserves_mass_property() {
        let params = HydroParams::closed();
        for seed in 0..10u64 {
            let mut rng = ChaCha20Rng::seed_from_u64(seed);
            let mut grid = HydroGrid::flat(16, 16);
            for v in grid.terrain.iter_mut() {
                *v = rng.gen_range(0.0..10.0);
            }
            for v in grid.water.iter_mut() {
                *v = rng.gen_range(0.0..2.0);
            }
            let mass_before = grid.total_water();
            for _ in 0..100 {
                grid.step(&params);
            }
            let mass_after = grid.total_water();
            let delta = (mass_after - mass_before).abs();
            assert!(
                delta < 1e-2,
                "seed {seed}: mass drift {delta} (before={mass_before}, after={mass_after})"
            );
        }
    }

    /// Sur une pente régulière (terrain monotone décroissant), l'eau
    /// placée au sommet doit migrer vers le pied de la pente.
    #[test]
    fn water_flows_downhill() {
        let params = HydroParams::closed();
        let mut grid = HydroGrid::flat(8, 1);
        // Pente : terrain[0] = 7.0, terrain[7] = 0.0
        for x in 0..8 {
            grid.terrain[x] = (7 - x) as f32;
        }
        // Eau initialement au sommet uniquement.
        grid.water[0] = 5.0;

        let mass_before = grid.total_water();
        for _ in 0..500 {
            grid.step(&params);
        }
        let mass_after = grid.total_water();

        // Conservation de masse.
        assert!((mass_after - mass_before).abs() < 1e-3);

        // L'eau doit s'être accumulée vers le bas de la pente
        // (somme des 4 dernières cellules > somme des 4 premières).
        let upper: f32 = grid.water[0..4].iter().sum();
        let lower: f32 = grid.water[4..8].iter().sum();
        assert!(
            lower > upper,
            "expected water to migrate downhill: upper={upper} lower={lower}"
        );
    }

    /// Déterminisme bit-exact : deux runs identiques produisent la
    /// même grille finale, octet par octet.
    #[test]
    fn step_is_bit_exact_deterministic() {
        let params = HydroParams::closed();
        let mut g1 = HydroGrid::flat(32, 32);
        let mut g2 = HydroGrid::flat(32, 32);
        let mut rng = ChaCha20Rng::seed_from_u64(0xC0FFEE);
        for i in 0..32 * 32 {
            let t = rng.gen_range(0.0..10.0);
            let w = rng.gen_range(0.0..1.0);
            g1.terrain[i] = t;
            g2.terrain[i] = t;
            g1.water[i] = w;
            g2.water[i] = w;
        }
        for _ in 0..50 {
            g1.step(&params);
            g2.step(&params);
        }
        assert_eq!(g1.water, g2.water, "non-deterministic water step");
    }

    /// L'eau ne franchit pas une barrière supérieure à son niveau.
    #[test]
    fn water_does_not_flow_uphill_against_barrier() {
        let params = HydroParams::closed();
        let mut grid = HydroGrid::flat(4, 1);
        // Cuvette : sols [0]=5, [1]=0, [2]=0, [3]=5
        grid.terrain[0] = 5.0;
        grid.terrain[1] = 0.0;
        grid.terrain[2] = 0.0;
        grid.terrain[3] = 5.0;
        // Un peu d'eau dans la cuvette.
        grid.water[1] = 1.0;
        grid.water[2] = 1.0;

        let mass_before = grid.total_water();
        for _ in 0..200 {
            grid.step(&params);
        }
        let mass_after = grid.total_water();
        assert!((mass_after - mass_before).abs() < 1e-4);

        // Les cellules barrières doivent rester sèches.
        assert!(grid.water[0] < 1e-5, "water leaked uphill to [0]");
        assert!(grid.water[3] < 1e-5, "water leaked uphill to [3]");
    }

    /// Le `total_water` initial vaut bien la somme des cellules.
    #[test]
    fn total_water_sums_correctly() {
        let mut g = HydroGrid::flat(3, 3);
        for (i, v) in g.water.iter_mut().enumerate() {
            *v = (i + 1) as f32;
        }
        // 1+2+3+4+5+6+7+8+9 = 45
        assert!((g.total_water() - 45.0).abs() < 1e-9);
    }
}
