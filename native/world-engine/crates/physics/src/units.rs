//! Strong SI units. Newtype `f64` wrappers with restricted arithmetic.

use serde::{Deserialize, Serialize};
use std::ops::{Add, Div, Mul, Neg, Sub};

macro_rules! define_unit {
    ($name:ident, $unit_str:expr) => {
        #[doc = concat!("A quantity in `", $unit_str, "`.")]
        #[derive(
            Copy, Clone, Debug, Default, PartialEq, PartialOrd, Serialize, Deserialize,
        )]
        #[repr(transparent)]
        pub struct $name(pub f64);

        impl $name {
            /// The numerical value in this unit's SI base.
            #[inline]
            #[must_use]
            pub const fn value(self) -> f64 {
                self.0
            }

            /// Build from a raw `f64`.
            #[inline]
            #[must_use]
            pub const fn from_f64(v: f64) -> Self {
                Self(v)
            }

            /// Pretty-print with unit suffix.
            #[must_use]
            pub fn format(self) -> String {
                format!("{} {}", self.0, $unit_str)
            }
        }

        impl Add for $name {
            type Output = $name;
            #[inline]
            fn add(self, rhs: $name) -> $name {
                $name(self.0 + rhs.0)
            }
        }
        impl Sub for $name {
            type Output = $name;
            #[inline]
            fn sub(self, rhs: $name) -> $name {
                $name(self.0 - rhs.0)
            }
        }
        impl Neg for $name {
            type Output = $name;
            #[inline]
            fn neg(self) -> $name {
                $name(-self.0)
            }
        }
        impl Mul<f64> for $name {
            type Output = $name;
            #[inline]
            fn mul(self, rhs: f64) -> $name {
                $name(self.0 * rhs)
            }
        }
        impl Mul<$name> for f64 {
            type Output = $name;
            #[inline]
            fn mul(self, rhs: $name) -> $name {
                $name(self * rhs.0)
            }
        }
        impl Div<f64> for $name {
            type Output = $name;
            #[inline]
            fn div(self, rhs: f64) -> $name {
                $name(self.0 / rhs)
            }
        }
        impl Div<$name> for $name {
            type Output = f64;
            #[inline]
            fn div(self, rhs: $name) -> f64 {
                self.0 / rhs.0
            }
        }
    };
}

define_unit!(Meter, "m");
define_unit!(SquareMeter, "m²");
define_unit!(CubicMeter, "m³");
define_unit!(Second, "s");
define_unit!(Kilogram, "kg");
define_unit!(Kelvin, "K");
define_unit!(Celsius, "°C");
define_unit!(Pascal, "Pa");
define_unit!(Joule, "J");
define_unit!(Watt, "W");
define_unit!(MeterPerSecond, "m/s");
define_unit!(MeterPerSecondSquared, "m/s²");
define_unit!(Newton, "N");
define_unit!(KilogramPerCubicMeter, "kg/m³");
define_unit!(MillimetersPerHour, "mm/h");
define_unit!(WattPerSquareMeter, "W/m²");
define_unit!(JoulePerKilogramKelvin, "J/(kg·K)");

// ---- Dimensional arithmetic between distinct units -----------------------

impl Mul<Meter> for Meter {
    type Output = SquareMeter;
    #[inline]
    fn mul(self, rhs: Meter) -> SquareMeter {
        SquareMeter(self.0 * rhs.0)
    }
}

impl Mul<SquareMeter> for Meter {
    type Output = CubicMeter;
    #[inline]
    fn mul(self, rhs: SquareMeter) -> CubicMeter {
        CubicMeter(self.0 * rhs.0)
    }
}

impl Div<Second> for Meter {
    type Output = MeterPerSecond;
    #[inline]
    fn div(self, rhs: Second) -> MeterPerSecond {
        MeterPerSecond(self.0 / rhs.0)
    }
}

impl Div<Second> for MeterPerSecond {
    type Output = MeterPerSecondSquared;
    #[inline]
    fn div(self, rhs: Second) -> MeterPerSecondSquared {
        MeterPerSecondSquared(self.0 / rhs.0)
    }
}

impl Mul<MeterPerSecondSquared> for Kilogram {
    type Output = Newton;
    #[inline]
    fn mul(self, rhs: MeterPerSecondSquared) -> Newton {
        Newton(self.0 * rhs.0)
    }
}

impl Div<SquareMeter> for Newton {
    type Output = Pascal;
    #[inline]
    fn div(self, rhs: SquareMeter) -> Pascal {
        Pascal(self.0 / rhs.0)
    }
}

impl Mul<Meter> for Newton {
    type Output = Joule;
    #[inline]
    fn mul(self, rhs: Meter) -> Joule {
        Joule(self.0 * rhs.0)
    }
}

impl Div<Second> for Joule {
    type Output = Watt;
    #[inline]
    fn div(self, rhs: Second) -> Watt {
        Watt(self.0 / rhs.0)
    }
}

impl Div<SquareMeter> for Watt {
    type Output = WattPerSquareMeter;
    #[inline]
    fn div(self, rhs: SquareMeter) -> WattPerSquareMeter {
        WattPerSquareMeter(self.0 / rhs.0)
    }
}

// ---- Temperature conversion ----------------------------------------------

impl Celsius {
    /// 0 °C in Kelvin.
    pub const ZERO_C_IN_KELVIN: f64 = 273.15;

    /// Convert °C → K.
    #[inline]
    #[must_use]
    pub fn to_kelvin(self) -> Kelvin {
        Kelvin(self.0 + Self::ZERO_C_IN_KELVIN)
    }
}

impl Kelvin {
    /// Convert K → °C.
    #[inline]
    #[must_use]
    pub fn to_celsius(self) -> Celsius {
        Celsius(self.0 - Celsius::ZERO_C_IN_KELVIN)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn area_from_two_meters() {
        let l = Meter(3.0);
        let w = Meter(4.0);
        let a: SquareMeter = l * w;
        assert!((a.0 - 12.0).abs() < 1e-9);
    }

    #[test]
    fn velocity_from_distance_time() {
        let d = Meter(100.0);
        let t = Second(10.0);
        let v: MeterPerSecond = d / t;
        assert!((v.0 - 10.0).abs() < 1e-9);
    }

    #[test]
    fn force_mass_accel() {
        let m = Kilogram(2.0);
        let a = MeterPerSecondSquared(9.81);
        let f: Newton = m * a;
        assert!((f.0 - 19.62).abs() < 1e-9);
    }

    #[test]
    fn temperature_conversion() {
        let c = Celsius(25.0);
        let k = c.to_kelvin();
        assert!((k.0 - 298.15).abs() < 1e-9);
        let back = k.to_celsius();
        assert!((back.0 - 25.0).abs() < 1e-9);
    }
}
