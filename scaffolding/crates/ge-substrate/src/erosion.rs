//! Érosion hydraulique CPU bit-exact — réf. Theobald / bshishov.
//!
//! Wave 11 — extension additive du substrat physique. Le pas
//! d'érosion consomme une `HydroGrid` (sortie de `water::step`)
//! et applique trois mécanismes physiquement fondés :
//!
//! 1. **Transport de sédiment** : la capacité d'une cellule à
//!    porter du sédiment dépend de la vitesse du flux et de la
//!    pente locale (`capacity = K_c · |v| · sin(slope)`). Si la
//!    cellule porte moins que sa capacité, elle creuse le terrain
//!    (dissolution `K_d`). Si elle en porte plus, elle dépose
//!    (`K_s`).
//!
//! 2. **Advection des sédiments** : les sédiments en suspension
//!    sont transportés selon le champ de flux entrant/sortant
//!    calculé par le pas Saint-Venant. Schéma upwind (donor-cell)
//!    pour rester stable inconditionnellement.
//!
//! 3. **Érosion thermique** (cryoclastie + éboulement) : si la
//!    pente locale dépasse l'angle de repos `θ_repose`, du
//!    matériau est transféré vers le voxel aval. Les cycles
//!    gel/dégel accélèrent l'effet — couplage T° fourni par le
//!    paramètre `freeze_thaw_cycles`.
//!
//! ## Invariants
//!
//! - **Conservation de masse solide** : `Δterrain + Δsédiment ≈ 0`
//!   à la précision FP près, sur tout pas sans pluie ni évaporation.
//!   Vérifié par property test (cf. tests).
//! - **Déterminisme bit-exact** : même état initial → même état
//!   final octet par octet, identique entre runs et entre threads.
//! - **Localité** : un voxel n'est affecté que par ses 4 voisins
//!   immédiats (compatible compute shader 8×8 workgroup).
//!
//! ## Hook debris-flow (Wave 11.1 - future)
//!
//! La fonction [`apply_debris_flow_step`] est un stub documenté
//! pour l'extension D8 (TOG 2024, doi 10.1145/3658213) :
//! formulation unifiée debris-flow + fluvial. À implémenter dans
//! un sprint dédié quand les flux d'agents auront besoin de cônes
//! de déjection et de glissements de terrain.

use serde::{Deserialize, Serialize};

use crate::water::HydroGrid;

/// Paramètres du pas d'érosion. Toutes valeurs SI.
///
/// Valeurs par défaut calibrées approximativement sur le bassin
/// du Colorado (climat semi-aride, transport actif). Les unités
/// précises dépendent du contexte numérique mais elles sont
/// dimensionnellement cohérentes avec un pas `dt` de l'ordre de
/// 0.05–0.2 s simulé.
#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct ErosionParams {
    /// Taille de cellule (m).
    pub dx: f32,
    /// Pas de temps simulé (s).
    pub dt: f32,
    /// `K_c` — capacité de transport de sédiments.
    /// Sans dimension dans cette formulation simplifiée.
    pub sediment_capacity: f32,
    /// `K_d` — taux de dissolution (érosion par flux). 0.001 à 0.01.
    pub dissolution_rate: f32,
    /// `K_s` — taux de déposition. 0.001 à 0.005.
    pub deposition_rate: f32,
    /// `K_e` — taux d'évaporation des sédiments en suspension
    /// (les sédiments ne restent pas suspendus à l'infini sans flux).
    pub sediment_settling: f32,
    /// Angle de repos sec (radians). Au-delà, matériau s'éboule.
    /// Sable sec ≈ 0.61 rad (35°), gravier ≈ 0.70 rad (40°).
    pub repose_angle: f32,
    /// Fraction de matériau transféré par cycle gel-dégel.
    /// Calibré sur des taux d'érosion alpine (~mm/an réels).
    pub freeze_thaw_factor: f32,
    /// Nombre de cycles gel-dégel dans le pas courant (sans dim).
    /// = 0 pour climat chaud, = 1–4 pour climat tempéré sur 1 an.
    pub freeze_thaw_cycles: u32,
}

impl ErosionParams {
    /// Paramètres "conservatifs" — érosion thermique seule désactivée,
    /// dissolution et déposition équilibrées. Utilisé pour valider
    /// la conservation de masse solide dans les property tests.
    pub fn conservative() -> Self {
        Self {
            dx: 1.0,
            dt: 0.1,
            sediment_capacity: 0.02,
            dissolution_rate: 0.005,
            deposition_rate: 0.005,
            sediment_settling: 0.0,
            repose_angle: std::f32::consts::FRAC_PI_2, // 90° → jamais déclenché
            freeze_thaw_factor: 0.0,
            freeze_thaw_cycles: 0,
        }
    }

    /// Calibration "Colorado River" — sédimentaire, transport actif.
    pub fn colorado_default() -> Self {
        Self {
            dx: 1.0,
            dt: 0.1,
            sediment_capacity: 0.02,
            dissolution_rate: 0.005,
            deposition_rate: 0.003,
            sediment_settling: 0.001,
            repose_angle: 0.61, // 35° sable sec
            freeze_thaw_factor: 1e-4,
            freeze_thaw_cycles: 0,
        }
    }

    /// Calibration "alpine" — érosion thermique dominante, débit faible.
    pub fn alpine_default() -> Self {
        Self {
            dx: 1.0,
            dt: 0.1,
            sediment_capacity: 0.01,
            dissolution_rate: 0.002,
            deposition_rate: 0.004,
            sediment_settling: 0.002,
            repose_angle: 0.70, // 40° gravier
            freeze_thaw_factor: 5e-4,
            freeze_thaw_cycles: 2,
        }
    }
}

/// Grille d'érosion. Couplée à une [`HydroGrid`] qui fournit eau
/// et terrain (mutables tous deux).
///
/// `sediment[idx]` = sédiments en suspension (kg, ou m d'épaisseur
/// équivalente pour densité 2.65). `velocity[idx]` = vitesse
/// estimée du flux en sortie de la cellule (m/s).
#[derive(Clone, Debug)]
pub struct ErosionGrid {
    /// Largeur en cellules.
    pub width: usize,
    /// Hauteur en cellules.
    pub height: usize,
    /// Sédiments en suspension dans chaque cellule.
    pub sediment: Vec<f32>,
    /// Vitesse moyenne du flux par cellule (mise à jour à chaque step).
    pub velocity: Vec<f32>,
}

impl ErosionGrid {
    /// Construit une grille d'érosion vide, compatible avec une
    /// `HydroGrid` de mêmes dimensions.
    pub fn empty(width: usize, height: usize) -> Self {
        Self {
            width,
            height,
            sediment: vec![0.0; width * height],
            velocity: vec![0.0; width * height],
        }
    }

    /// Masse totale de sédiments en suspension. `f64` pour limiter
    /// l'erreur de sommation FP (cf. argument dans [`HydroGrid::total_water`]).
    pub fn total_sediment(&self) -> f64 {
        self.sediment.iter().map(|&s| s as f64).sum()
    }

    /// Applique un pas d'érosion sur la grille hydraulique. Mute :
    /// - `hydro.terrain` (creusement / déposition / éboulement)
    /// - `hydro.water` (les sédiments en transit n'affectent pas
    ///   le volume d'eau dans cette formulation simplifiée — densité
    ///   ignorée. À raffiner si réalisme acoustique/optique requis.)
    /// - `self.sediment` (transport + advection)
    /// - `self.velocity` (mis à jour depuis le gradient de surface)
    ///
    /// L'ordre des phases est fixé pour garantir le déterminisme :
    /// 1. vitesse (depuis gradient de surface)
    /// 2. transport (dissolution / déposition)
    /// 3. advection sédiments (donor-cell upwind)
    /// 4. érosion thermique (talus + gel-dégel)
    pub fn step(&mut self, hydro: &mut HydroGrid, params: &ErosionParams) {
        let w = self.width;
        let h = self.height;
        debug_assert_eq!(hydro.width, w, "hydro/erosion width mismatch");
        debug_assert_eq!(hydro.height, h, "hydro/erosion height mismatch");
        debug_assert_eq!(self.sediment.len(), w * h);
        debug_assert_eq!(self.velocity.len(), w * h);

        // ──────────────────────────────────────────────────────────
        // Phase 1 — estimation vitesse depuis le gradient de surface.
        // On utilise la magnitude du gradient (terrain + eau) qui est
        // un proxy stable pour |v| dans la formulation pipe model.
        // ──────────────────────────────────────────────────────────
        for y in 0..h {
            for x in 0..w {
                let idx = y * w + x;
                let s = hydro.terrain[idx] + hydro.water[idx];
                let mut grad_x = 0.0;
                let mut grad_y = 0.0;
                if x + 1 < w {
                    let nidx = idx + 1;
                    grad_x += s - (hydro.terrain[nidx] + hydro.water[nidx]);
                }
                if x >= 1 {
                    let nidx = idx - 1;
                    grad_x -= s - (hydro.terrain[nidx] + hydro.water[nidx]);
                }
                if y + 1 < h {
                    let nidx = idx + w;
                    grad_y += s - (hydro.terrain[nidx] + hydro.water[nidx]);
                }
                if y >= 1 {
                    let nidx = idx - w;
                    grad_y -= s - (hydro.terrain[nidx] + hydro.water[nidx]);
                }
                // Vitesse proxy : pente normalisée. Pas de v exact
                // (impose-rait un solveur shallow-water complet) — mais
                // monotone et déterministe : suffisant pour driver
                // dissolution/déposition.
                let v = (grad_x * grad_x + grad_y * grad_y).sqrt() / (2.0 * params.dx);
                self.velocity[idx] = v;
            }
        }

        // ──────────────────────────────────────────────────────────
        // Phase 2 — transport (dissolution / déposition).
        //
        // Capacity = K_c · |v| · sin(slope). Avec slope ≈ |grad| (rad),
        // on a déjà ces deux grandeurs dans `velocity` ci-dessus.
        // Pour limiter la duplication, on ré-utilise `velocity` à la
        // fois comme |v| et comme proxy de sin(slope) : capacity ∝ v².
        //
        // Cette simplification est cohérente avec Theobald 2008 §3.2
        // et bshishov/UnityTerrainErosionGPU (cf. veille D11).
        // ──────────────────────────────────────────────────────────
        for idx in 0..(w * h) {
            let v = self.velocity[idx];
            // Pas d'érosion si pas d'eau ou pas de pente.
            if hydro.water[idx] <= 1e-6 || v <= 1e-6 {
                continue;
            }

            let capacity = params.sediment_capacity * v * v;
            let s = self.sediment[idx];

            if s < capacity {
                // Creusement — eau "soif" de sédiments.
                let delta = (params.dissolution_rate * (capacity - s) * params.dt)
                    // borne supérieure : la dissolution ne peut pas
                    // creuser plus que le terrain existant dans la
                    // colonne (terrain ≥ 0).
                    .min(hydro.terrain[idx]);
                hydro.terrain[idx] -= delta;
                self.sediment[idx] += delta;
            } else {
                // Déposition — la cellule largue son surplus.
                let delta = (params.deposition_rate * (s - capacity) * params.dt)
                    // borne supérieure : on ne dépose pas plus qu'on
                    // ne porte.
                    .min(s);
                hydro.terrain[idx] += delta;
                self.sediment[idx] -= delta;
            }

            // Settling : sédiments lourds qui retombent même sans
            // changement de capacité (turbulence faible).
            let settled =
                (self.sediment[idx] * params.sediment_settling * params.dt).min(self.sediment[idx]);
            self.sediment[idx] -= settled;
            hydro.terrain[idx] += settled;
        }

        // ──────────────────────────────────────────────────────────
        // Phase 3 — advection donor-cell upwind.
        //
        // Schéma symétrique : chaque cellule donne une fraction de
        // ses sédiments à chaque voisin proportionnellement au flux
        // sortant relatif. Stable inconditionnellement (CFL trivial).
        // ──────────────────────────────────────────────────────────
        let mut sed_out = vec![0.0f32; w * h];
        let mut sed_in = vec![0.0f32; w * h];

        for y in 0..h {
            for x in 0..w {
                let idx = y * w + x;
                let s = self.sediment[idx];
                if s <= 0.0 || hydro.water[idx] <= 1e-6 {
                    continue;
                }
                let surface = hydro.terrain[idx] + hydro.water[idx];

                // Fractions de flux vers chaque voisin (positives = sortant).
                let mut f_n = 0.0;
                let mut f_s = 0.0;
                let mut f_e = 0.0;
                let mut f_w_ = 0.0;
                if y + 1 < h {
                    let nidx = idx + w;
                    let dh = surface - (hydro.terrain[nidx] + hydro.water[nidx]);
                    if dh > 0.0 {
                        f_n = dh;
                    }
                }
                if y >= 1 {
                    let nidx = idx - w;
                    let dh = surface - (hydro.terrain[nidx] + hydro.water[nidx]);
                    if dh > 0.0 {
                        f_s = dh;
                    }
                }
                if x + 1 < w {
                    let nidx = idx + 1;
                    let dh = surface - (hydro.terrain[nidx] + hydro.water[nidx]);
                    if dh > 0.0 {
                        f_e = dh;
                    }
                }
                if x >= 1 {
                    let nidx = idx - 1;
                    let dh = surface - (hydro.terrain[nidx] + hydro.water[nidx]);
                    if dh > 0.0 {
                        f_w_ = dh;
                    }
                }

                let total = f_n + f_s + f_e + f_w_;
                if total <= 0.0 {
                    continue;
                }

                // Fraction transportée par pas = velocity * dt / dx.
                // Cappée à 0.5 pour rester sous CFL (donor-cell stable).
                let frac = (self.velocity[idx] * params.dt / params.dx).min(0.5);
                let transported = s * frac;

                // Distribution proportionnelle aux flux sortants.
                let share_n = transported * (f_n / total);
                let share_s = transported * (f_s / total);
                let share_e = transported * (f_e / total);
                let share_w = transported * (f_w_ / total);

                sed_out[idx] += share_n + share_s + share_e + share_w;
                if y + 1 < h {
                    sed_in[idx + w] += share_n;
                }
                if y >= 1 {
                    sed_in[idx - w] += share_s;
                }
                if x + 1 < w {
                    sed_in[idx + 1] += share_e;
                }
                if x >= 1 {
                    sed_in[idx - 1] += share_w;
                }
            }
        }

        for idx in 0..(w * h) {
            // Application symétrique : la masse échangée est comptée
            // +1 fois comme entrant dans le voisin, -1 fois comme
            // sortant ici. Conservation exacte par construction.
            let new_s = self.sediment[idx] - sed_out[idx] + sed_in[idx];
            self.sediment[idx] = new_s.max(0.0);
        }

        // ──────────────────────────────────────────────────────────
        // Phase 4 — érosion thermique (talus + gel-dégel).
        //
        // Si pente > angle de repos, on transfère du matériau vers
        // l'aval. La fraction transférée par pas est bornée par
        // `freeze_thaw_factor * cycles`.
        // ──────────────────────────────────────────────────────────
        if params.freeze_thaw_cycles > 0 && params.freeze_thaw_factor > 0.0 {
            let cycles = params.freeze_thaw_cycles as f32;
            let max_slope_height = params.repose_angle.tan() * params.dx;
            let transfer_rate = params.freeze_thaw_factor * cycles * params.dt;

            // Calcul des transferts (lecture seule), puis application.
            // Évite les effets d'ordre dans la boucle.
            let mut talus_out = vec![0.0f32; w * h];
            let mut talus_in = vec![0.0f32; w * h];

            for y in 0..h {
                for x in 0..w {
                    let idx = y * w + x;
                    let h_here = hydro.terrain[idx];
                    // Récolte les voisins valides dont la dénivelée
                    // dépasse l'angle de repos. Tableau borné à 4
                    // entrées (les 4 voisins cardinaux).
                    let mut deltas: [f32; 4] = [0.0; 4];
                    let mut neigh_idx: [usize; 4] = [idx; 4];
                    let mut count = 0;
                    if y + 1 < h {
                        let nidx = idx + w;
                        let dh = h_here - hydro.terrain[nidx];
                        if dh > max_slope_height {
                            deltas[count] = dh - max_slope_height;
                            neigh_idx[count] = nidx;
                            count += 1;
                        }
                    }
                    if y >= 1 {
                        let nidx = idx - w;
                        let dh = h_here - hydro.terrain[nidx];
                        if dh > max_slope_height {
                            deltas[count] = dh - max_slope_height;
                            neigh_idx[count] = nidx;
                            count += 1;
                        }
                    }
                    if x + 1 < w {
                        let nidx = idx + 1;
                        let dh = h_here - hydro.terrain[nidx];
                        if dh > max_slope_height {
                            deltas[count] = dh - max_slope_height;
                            neigh_idx[count] = nidx;
                            count += 1;
                        }
                    }
                    if x >= 1 {
                        let nidx = idx - 1;
                        let dh = h_here - hydro.terrain[nidx];
                        if dh > max_slope_height {
                            deltas[count] = dh - max_slope_height;
                            neigh_idx[count] = nidx;
                            count += 1;
                        }
                    }
                    if count == 0 {
                        continue;
                    }
                    let sum_excess: f32 = deltas[..count].iter().sum();
                    // Borne la fraction sortante pour éviter d'aller
                    // sous le voisin (creuser plus que l'excès cumulé).
                    let transferred = (transfer_rate * sum_excess).min(sum_excess * 0.5);
                    for k in 0..count {
                        let share = transferred * (deltas[k] / sum_excess);
                        talus_out[idx] += share;
                        talus_in[neigh_idx[k]] += share;
                    }
                }
            }

            for idx in 0..(w * h) {
                hydro.terrain[idx] = (hydro.terrain[idx] - talus_out[idx] + talus_in[idx]).max(0.0);
            }
        }
    }
}

/// Hook pour l'extension debris-flow (D8 — TOG 2024).
///
/// Aujourd'hui : no-op documenté. Implémentation prévue dans un
/// sprint dédié quand les conditions seront réunies :
///
/// - Couplage avec la couche `ge-world::climate` pour piloter
///   l'humidité initiale du sol (déclencheur principal).
/// - Détection de glissements (zones où `dh > 1.5 · repose_angle`).
/// - Modèle de transport visqueux (debris-flow ≠ flux d'eau pure).
///
/// L'API est figée dès maintenant pour que les appelants puissent
/// brancher l'appel sans changement de signature ultérieur.
pub fn apply_debris_flow_step(
    _hydro: &mut HydroGrid,
    _erosion: &mut ErosionGrid,
    _params: &ErosionParams,
) {
    // Wave 11.1 — TOG 2024 unified algorithm.
    // Intentionnellement vide.
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::water::{HydroGrid, HydroParams};
    use rand::Rng;
    use rand::SeedableRng;
    use rand_chacha::ChaCha20Rng;

    /// **Invariant fondamental** : la somme `terrain + sédiment` est
    /// conservée à la précision FP près quand on enchaîne pas d'eau +
    /// pas d'érosion en système fermé (pas de pluie, pas d'évaporation,
    /// pas d'érosion thermique). Property test sur 8 graines.
    ///
    /// Tolérance : 1e-3 m sur la masse solide totale d'une grille 16×16.
    #[test]
    fn solid_mass_conserved_property() {
        let water_params = HydroParams::closed();
        let erosion_params = ErosionParams::conservative();
        for seed in 0..8u64 {
            let mut rng = ChaCha20Rng::seed_from_u64(seed);
            let mut grid = HydroGrid::flat(16, 16);
            let mut ero = ErosionGrid::empty(16, 16);
            for v in grid.terrain.iter_mut() {
                *v = rng.gen_range(0.0..10.0);
            }
            for v in grid.water.iter_mut() {
                *v = rng.gen_range(0.0..1.0);
            }
            let solid_before: f64 = grid.terrain.iter().map(|&t| t as f64).sum::<f64>()
                + ero.total_sediment();

            for _ in 0..50 {
                grid.step(&water_params);
                ero.step(&mut grid, &erosion_params);
            }

            let solid_after: f64 = grid.terrain.iter().map(|&t| t as f64).sum::<f64>()
                + ero.total_sediment();
            let delta = (solid_after - solid_before).abs();
            assert!(
                delta < 1e-3,
                "seed {seed}: solid mass drift {delta} (before={solid_before}, after={solid_after})"
            );
        }
    }

    /// L'eau qui coule sur une pente doit creuser un sillon en amont
    /// et déposer en aval. On vérifie qu'après N steps, le terrain
    /// initial monotone n'est plus strictement décroissant : il y a
    /// eu redistribution.
    #[test]
    fn slope_gets_eroded_into_redistribution() {
        let water_params = HydroParams::closed();
        let erosion_params = ErosionParams::colorado_default();
        let mut grid = HydroGrid::flat(16, 1);
        // Pente : t[0]=15.0 → t[15]=0.0 (∇=-1 par cellule)
        for x in 0..16 {
            grid.terrain[x] = (15 - x) as f32;
        }
        // Eau initialement uniforme sur le sommet.
        for x in 0..8 {
            grid.water[x] = 1.0;
        }
        let mut ero = ErosionGrid::empty(16, 1);

        let terrain_before = grid.terrain.clone();
        for _ in 0..200 {
            grid.step(&water_params);
            ero.step(&mut grid, &erosion_params);
        }

        // Quelque part la cellule de bas-de-pente doit avoir gagné de
        // l'altitude (déposition) OU la cellule de haut-de-pente doit
        // avoir perdu (creusement). On vérifie qu'au moins un voxel
        // a bougé significativement.
        let mut any_diff = false;
        for x in 0..16 {
            if (grid.terrain[x] - terrain_before[x]).abs() > 1e-3 {
                any_diff = true;
                break;
            }
        }
        assert!(any_diff, "no erosion/deposition observed on a slope");
    }

    /// Déterminisme bit-exact : 2 runs avec mêmes seeds → mêmes
    /// grilles finales, octet par octet, pour terrain ET sédiment.
    #[test]
    fn step_is_bit_exact_deterministic() {
        let water_params = HydroParams::colorado_default();
        let erosion_params = ErosionParams::colorado_default();
        let mut g1 = HydroGrid::flat(24, 24);
        let mut g2 = HydroGrid::flat(24, 24);
        let mut e1 = ErosionGrid::empty(24, 24);
        let mut e2 = ErosionGrid::empty(24, 24);
        let mut rng = ChaCha20Rng::seed_from_u64(0xDEAD_BEEF);
        for i in 0..24 * 24 {
            let t = rng.gen_range(0.0..5.0);
            let w = rng.gen_range(0.0..0.5);
            g1.terrain[i] = t;
            g2.terrain[i] = t;
            g1.water[i] = w;
            g2.water[i] = w;
        }
        for _ in 0..30 {
            g1.step(&water_params);
            g2.step(&water_params);
            e1.step(&mut g1, &erosion_params);
            e2.step(&mut g2, &erosion_params);
        }
        assert_eq!(g1.terrain, g2.terrain, "non-deterministic erosion terrain");
        assert_eq!(e1.sediment, e2.sediment, "non-deterministic erosion sediment");
    }

    /// Sans eau, pas d'érosion fluviale. La cellule sèche reste
    /// intacte (sauf si érosion thermique activée — désactivée ici).
    #[test]
    fn dry_cell_does_not_erode() {
        let erosion_params = ErosionParams::conservative();
        let mut grid = HydroGrid::flat(4, 4);
        for v in grid.terrain.iter_mut() {
            *v = 5.0;
        }
        // Aucune cellule n'a d'eau.
        let mut ero = ErosionGrid::empty(4, 4);

        let before = grid.terrain.clone();
        for _ in 0..50 {
            ero.step(&mut grid, &erosion_params);
        }
        assert_eq!(grid.terrain, before, "dry cells eroded without water");
        assert!(
            ero.total_sediment() < 1e-9,
            "sediment appeared from nowhere"
        );
    }

    /// Érosion thermique : un escarpement raide s'aplanit avec le
    /// temps quand `freeze_thaw_cycles > 0`. Vérifie qu'après N pas,
    /// la falaise initiale s'est partiellement éboulée.
    #[test]
    fn freeze_thaw_relaxes_steep_slope() {
        let water_params = HydroParams::closed();
        let mut erosion_params = ErosionParams::alpine_default();
        // Force des cycles forts pour test concentré.
        erosion_params.freeze_thaw_cycles = 10;
        erosion_params.freeze_thaw_factor = 1e-2;

        let mut grid = HydroGrid::flat(8, 1);
        // Falaise : t[0..4] = 10.0, t[4..8] = 0.0 → ∆=10 > tan(40°)≈0.84
        for x in 0..4 {
            grid.terrain[x] = 10.0;
        }
        for x in 4..8 {
            grid.terrain[x] = 0.0;
        }
        let mut ero = ErosionGrid::empty(8, 1);

        let cliff_top_before = grid.terrain[3];
        let cliff_bottom_before = grid.terrain[4];

        for _ in 0..100 {
            grid.step(&water_params);
            ero.step(&mut grid, &erosion_params);
        }

        assert!(
            grid.terrain[3] < cliff_top_before,
            "cliff top did not erode: {} → {}",
            cliff_top_before,
            grid.terrain[3]
        );
        assert!(
            grid.terrain[4] > cliff_bottom_before,
            "cliff foot did not receive talus: {} → {}",
            cliff_bottom_before,
            grid.terrain[4]
        );
    }

    /// Le hook debris-flow est un no-op (pour l'instant).
    #[test]
    fn debris_flow_stub_is_noop() {
        let water_params = HydroParams::closed();
        let erosion_params = ErosionParams::conservative();
        let mut grid = HydroGrid::flat(4, 4);
        let mut ero = ErosionGrid::empty(4, 4);
        for v in grid.terrain.iter_mut() {
            *v = 3.0;
        }
        grid.water[0] = 1.0;
        let before_terrain = grid.terrain.clone();
        let before_water = grid.water.clone();
        let before_sediment = ero.sediment.clone();

        let _ = water_params;
        apply_debris_flow_step(&mut grid, &mut ero, &erosion_params);

        assert_eq!(grid.terrain, before_terrain);
        assert_eq!(grid.water, before_water);
        assert_eq!(ero.sediment, before_sediment);
    }
}
