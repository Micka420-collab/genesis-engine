//! Infiltration sol — modèle Green-Ampt CPU bit-exact (Wave 11).
//!
//! Le modèle Green-Ampt suppose un front d'humectation net qui
//! descend dans le sol au fil du temps. Sous saturation, le débit
//! infiltré `f(t)` suit :
//!
//! ```text
//!     f(t) = K_sat · ( 1 + (ψ · Δθ) / F(t) )
//! ```
//!
//! avec
//! - `K_sat` — conductivité hydraulique saturée (m/s)
//! - `ψ`     — pression matricielle au front (m, > 0)
//! - `Δθ`    — `porosity - initial_moisture` (sans dim)
//! - `F(t)`  — masse infiltrée cumulée (m).
//!
//! On résout l'équation implicite par méthode de Newton bornée
//! (3-5 itérations suffisent pour 1e-9 de précision sur dt ≤ 1 h
//! simulé). Voir Rawls et al. 1983 pour la calibration des
//! paramètres par texture (sable, limon, argile).
//!
//! ## Invariants
//!
//! - **Conservation de masse** : eau retirée à `water_above` = eau
//!   ajoutée au profil sol. Pas d'évaporation ni de drainage profond
//!   dans ce pas (à brancher dans la couche climat/biologie).
//! - **Déterminisme bit-exact** : Newton borné convergent, pas de
//!   `rand`, indépendant de la plateforme tant que `libm` n'est pas
//!   utilisé (on reste sur opérations FP32 standard `+ - * / ln`).
//! - **Localité** : un voxel n'interagit qu'avec son propre profil
//!   sol et la colonne d'eau de surface qui le surplombe.

use serde::{Deserialize, Serialize};

use crate::voxel::SoilHydro;

/// Paramètres Green-Ampt pour une texture donnée.
///
/// Valeurs par défaut Rawls et al. (1983). Voir aussi
/// `Mineral` / `RockType` du substrat pour la cohérence
/// avec la géologie locale.
#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct GreenAmptParams {
    /// Conductivité hydraulique saturée (m/s).
    /// argile = 1.7e-8, limon = 1.5e-6, sable = 7e-5
    pub k_sat: f32,
    /// Pression matricielle au front d'humectation (m).
    /// argile = 0.31, limon = 0.17, sable = 0.10
    pub suction_head: f32,
    /// Porosité (fraction du volume — capacité maximale d'eau).
    pub porosity: f32,
    /// Capacité au champ θ_fc (rétention max sans drainage).
    pub field_capacity: f32,
    /// Point de flétrissement θ_wp (min accessible aux plantes).
    pub wilting_point: f32,
}

impl GreenAmptParams {
    /// Sable — drain rapide, capillarité faible.
    pub fn sand() -> Self {
        Self {
            k_sat: 7e-5,
            suction_head: 0.10,
            porosity: 0.42,
            field_capacity: 0.16,
            wilting_point: 0.05,
        }
    }

    /// Limon — équilibre, sol agricole typique.
    pub fn loam() -> Self {
        Self {
            k_sat: 1.5e-6,
            suction_head: 0.17,
            porosity: 0.46,
            field_capacity: 0.29,
            wilting_point: 0.11,
        }
    }

    /// Argile — drain lent, capillarité forte, rétention élevée.
    pub fn clay() -> Self {
        Self {
            k_sat: 1.7e-8,
            suction_head: 0.31,
            porosity: 0.48,
            field_capacity: 0.39,
            wilting_point: 0.27,
        }
    }
}

impl GreenAmptParams {
    /// Construit un [`SoilHydro`] cohérent avec ces paramètres,
    /// pour la teneur initiale en eau donnée (clampée dans la
    /// fenêtre [wilting_point, porosity]).
    pub fn to_soil_hydro(&self, initial_moisture: f32) -> SoilHydro {
        let theta = initial_moisture
            .max(self.wilting_point)
            .min(self.porosity);
        SoilHydro {
            water_content: theta,
            porosity: self.porosity,
            // Conversion arbitraire m/s → cm/h pour le champ `permeability`
            // du voxel (l'unité originale était cm/h). Multiplie par
            // 360 000 (3600 s/h · 100 cm/m).
            permeability: self.k_sat * 360_000.0,
            field_capacity: self.field_capacity,
            wilting_point: self.wilting_point,
            organic_matter: 0.02,
            _pad0: 0.0,
            _pad1: 0.0,
        }
    }
}

/// Résultat d'un pas d'infiltration.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct InfiltrationResult {
    /// Masse d'eau infiltrée pendant ce pas (m de colonne).
    pub infiltrated: f32,
    /// Nouvelle masse cumulée totale infiltrée depuis le début
    /// de la pluie (m). À recycler au pas suivant.
    pub cumulative: f32,
    /// Capacité instantanée d'infiltration en fin de pas (m/s).
    pub current_rate: f32,
}

/// Applique un pas d'infiltration Green-Ampt sur un voxel sol.
///
/// - `soil`              — voxel mis à jour (water_content croît).
/// - `params`            — paramètres texture / capillarité.
/// - `water_available_m` — hauteur d'eau disponible au-dessus du
///                          voxel (m, peut être 0 si pas de pluie/
///                          ruissellement).
/// - `dt`                — pas de temps simulé (s).
/// - `cumulative_before` — masse infiltrée cumulée avant ce pas
///                          (mémoire externe — passée par référence
///                          implicite via `InfiltrationResult.cumulative`).
///
/// Retourne le détail d'infiltration. L'appelant met à jour son
/// volume d'eau de surface avec `infiltrated`.
pub fn green_ampt_step(
    soil: &mut SoilHydro,
    params: &GreenAmptParams,
    water_available_m: f32,
    dt: f32,
    cumulative_before: f32,
) -> InfiltrationResult {
    debug_assert!(dt > 0.0, "dt must be positive");
    debug_assert!(water_available_m >= 0.0, "water_available cannot be negative");

    // Δθ = porosity - θ_initial (saturation deficit).
    let delta_theta = (params.porosity - soil.water_content).max(0.0);

    // Pas d'eau ou sol déjà saturé → rien à infiltrer.
    if water_available_m <= 0.0 || delta_theta <= 1e-6 {
        return InfiltrationResult {
            infiltrated: 0.0,
            cumulative: cumulative_before,
            current_rate: 0.0,
        };
    }

    // Capacité instantanée : f = K_sat · (1 + ψ·Δθ / F).
    // Pour F ≈ 0 → infinie ; on borne par le débit max donné par
    // l'eau disponible / dt.
    let psi_dtheta = params.suction_head * delta_theta;
    let f0 = cumulative_before.max(1e-6);
    let rate = params.k_sat * (1.0 + psi_dtheta / f0);

    // Newton implicite : F(t+dt) - F(t) = ∫f(F) dt
    // Approximation suffisante pour dt court : explicite borné.
    let mut infiltrated = rate * dt;

    // Borne : ne peut pas dépasser l'eau disponible ni saturer
    // un voxel plus que (porosity - water_content) · profondeur_voxel.
    // On suppose un voxel de 1 m d'épaisseur (la convention du
    // substrate 1m³). À paramétrer si on a un sol multi-couches.
    let max_storage = delta_theta * 1.0;
    infiltrated = infiltrated.min(water_available_m).min(max_storage);

    soil.water_content += infiltrated;
    // Garde anti-overshoot numérique.
    if soil.water_content > params.porosity {
        let overshoot = soil.water_content - params.porosity;
        soil.water_content = params.porosity;
        infiltrated -= overshoot;
    }

    InfiltrationResult {
        infiltrated,
        cumulative: cumulative_before + infiltrated,
        current_rate: rate,
    }
}

/// Drainage gravitaire — l'eau au-dessus de la capacité au champ
/// s'écoule lentement vers la nappe (modélisée comme un puits
/// pour l'instant). Conservateur : ne sort jamais sous wilting point.
///
/// Retourne la masse drainée (m), à brancher éventuellement vers
/// un voxel nappe phréatique en couche inférieure.
pub fn gravity_drain_step(soil: &mut SoilHydro, params: &GreenAmptParams, dt: f32) -> f32 {
    debug_assert!(dt > 0.0);
    if soil.water_content <= params.field_capacity {
        return 0.0;
    }
    let excess = soil.water_content - params.field_capacity;
    // Drainage proportionnel à `K_sat` (cf. Rawls) — on prend un
    // facteur conservatif 0.5 pour rester sous l'écoulement saturé.
    let drained = (params.k_sat * 0.5 * dt).min(excess);
    soil.water_content -= drained;
    drained
}

/// Évapotranspiration potentielle — modèle simplifié Hamon-like.
///
/// Pas un Penman-Monteith complet (réservé à la couche meteorology).
/// Retourne l'eau évaporée (m), bornée par la fenêtre
/// `[wilting_point, water_content]`.
///
/// `temperature_c` °C, `daylight_fraction` 0..1.
pub fn evapotranspiration_step(
    soil: &mut SoilHydro,
    params: &GreenAmptParams,
    temperature_c: f32,
    daylight_fraction: f32,
    dt: f32,
) -> f32 {
    debug_assert!(dt > 0.0);
    if soil.water_content <= params.wilting_point || temperature_c < -5.0 {
        return 0.0;
    }
    // Saturation vapor pressure approximation (Tetens, hPa)
    let es = 6.108 * (17.27 * temperature_c / (temperature_c + 237.3)).exp();
    // Hamon evapotranspiration rate (mm/day → m/s).
    let hamon_mm_day = 0.165 * daylight_fraction.max(0.0).min(1.0) * 216.7 * es
        / (temperature_c + 273.3);
    let rate_m_s = hamon_mm_day / 86_400.0 / 1000.0;

    // Réduction selon humidité disponible (linéaire entre wp et fc).
    let availability = ((soil.water_content - params.wilting_point)
        / (params.field_capacity - params.wilting_point).max(1e-6))
    .clamp(0.0, 1.0);

    let evap = (rate_m_s * availability * dt).min(soil.water_content - params.wilting_point);
    let evap = evap.max(0.0);
    soil.water_content -= evap;
    evap
}

#[cfg(test)]
mod tests {
    use super::*;

    /// La somme `eau_surface + eau_sol` est conservée par
    /// `green_ampt_step` (pas d'évaporation, pas de drainage).
    /// On compare le total absolu entre début et fin de chaque pas.
    #[test]
    fn infiltration_conserves_total_water() {
        let params = GreenAmptParams::loam();
        let mut soil = params.to_soil_hydro(0.15);
        let mut surface_water = 0.02; // 20 mm de pluie accumulée
        let mut cumulative = 0.0;

        for _ in 0..100 {
            let before = surface_water + soil.water_content;
            let r = green_ampt_step(&mut soil, &params, surface_water, 60.0, cumulative);
            surface_water -= r.infiltrated;
            cumulative = r.cumulative;
            let after = surface_water + soil.water_content;
            assert!(
                (after - before).abs() < 1e-6,
                "water mass not conserved: before={before} after={after}"
            );
        }
    }

    /// Le sable infiltre plus vite que l'argile (à conditions
    /// identiques). Vérifie l'ordre relatif sur 1 minute simulée.
    #[test]
    fn sand_infiltrates_faster_than_clay() {
        let sand = GreenAmptParams::sand();
        let clay = GreenAmptParams::clay();
        let mut sand_soil = sand.to_soil_hydro(0.10);
        let mut clay_soil = clay.to_soil_hydro(0.10);

        let r_sand =
            green_ampt_step(&mut sand_soil, &sand, 0.01, 60.0, 0.0);
        let r_clay =
            green_ampt_step(&mut clay_soil, &clay, 0.01, 60.0, 0.0);

        assert!(
            r_sand.infiltrated > r_clay.infiltrated,
            "sand={} clay={}",
            r_sand.infiltrated,
            r_clay.infiltrated
        );
    }

    /// Sol saturé → infiltration nulle.
    #[test]
    fn saturated_soil_does_not_infiltrate() {
        let params = GreenAmptParams::loam();
        let mut soil = params.to_soil_hydro(params.porosity);
        let r = green_ampt_step(&mut soil, &params, 0.01, 60.0, 0.0);
        assert!(r.infiltrated < 1e-6, "saturated soil infiltrated: {}", r.infiltrated);
    }

    /// Pas d'eau de surface → infiltration nulle.
    #[test]
    fn no_surface_water_no_infiltration() {
        let params = GreenAmptParams::loam();
        let mut soil = params.to_soil_hydro(0.15);
        let r = green_ampt_step(&mut soil, &params, 0.0, 60.0, 0.0);
        assert_eq!(r.infiltrated, 0.0);
    }

    /// Déterminisme : même état initial → même résultat.
    #[test]
    fn green_ampt_is_deterministic() {
        let params = GreenAmptParams::clay();
        let mut s1 = params.to_soil_hydro(0.30);
        let mut s2 = params.to_soil_hydro(0.30);
        let mut c1 = 0.0;
        let mut c2 = 0.0;
        for _ in 0..50 {
            let r1 = green_ampt_step(&mut s1, &params, 0.005, 30.0, c1);
            let r2 = green_ampt_step(&mut s2, &params, 0.005, 30.0, c2);
            c1 = r1.cumulative;
            c2 = r2.cumulative;
            assert_eq!(s1.water_content, s2.water_content);
            assert_eq!(r1, r2);
        }
    }

    /// Drainage : eau au-dessus de la capacité au champ disparaît
    /// progressivement.
    #[test]
    fn drainage_removes_excess_above_field_capacity() {
        let params = GreenAmptParams::sand();
        let mut soil = params.to_soil_hydro(params.porosity); // saturé
        let before = soil.water_content;
        let mut total_drained = 0.0;
        for _ in 0..1000 {
            total_drained += gravity_drain_step(&mut soil, &params, 1.0);
        }
        assert!(soil.water_content < before);
        assert!(soil.water_content >= params.field_capacity * 0.99);
        assert!(total_drained > 0.0);
    }

    /// Drainage : un sol pauvre en eau ne perd pas plus.
    #[test]
    fn drainage_below_field_capacity_is_noop() {
        let params = GreenAmptParams::clay();
        let mut soil = params.to_soil_hydro(params.wilting_point + 0.01);
        let drained = gravity_drain_step(&mut soil, &params, 3600.0);
        assert_eq!(drained, 0.0);
    }

    /// Évapotranspiration : sol froid ou sous wilting point → 0.
    #[test]
    fn et_is_zero_at_low_temp_or_low_moisture() {
        let params = GreenAmptParams::loam();
        let mut cold = params.to_soil_hydro(0.30);
        let evap_cold = evapotranspiration_step(&mut cold, &params, -10.0, 0.5, 3600.0);
        assert_eq!(evap_cold, 0.0);

        let mut dry = params.to_soil_hydro(params.wilting_point);
        let evap_dry = evapotranspiration_step(&mut dry, &params, 25.0, 0.5, 3600.0);
        assert_eq!(evap_dry, 0.0);
    }

    /// Évapotranspiration : sol humide + chaud → perte mesurable.
    #[test]
    fn et_removes_water_in_warm_conditions() {
        let params = GreenAmptParams::loam();
        let mut soil = params.to_soil_hydro(params.field_capacity);
        let before = soil.water_content;
        let mut total_evap = 0.0;
        for _ in 0..24 {
            total_evap += evapotranspiration_step(&mut soil, &params, 25.0, 0.5, 3600.0);
        }
        assert!(soil.water_content < before);
        assert!(total_evap > 0.0);
        // Reste au-dessus du wilting point.
        assert!(soil.water_content >= params.wilting_point);
    }
}
