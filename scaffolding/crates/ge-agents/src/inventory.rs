//! Inventaire — objets portés / possédés.

use bevy_ecs::prelude::Component;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Type d'objet. Étendu en Phase 3 (outils, armes, vêtements).
#[derive(Copy, Clone, Eq, PartialEq, Hash, Debug, Serialize, Deserialize)]
pub enum ItemKind {
    /// Eau (litre).
    Water,
    /// Nourriture (kcal).
    Food,
    /// Bois (kg).
    Wood,
    /// Pierre (kg).
    Stone,
    /// Métal (kg).
    Metal,
    /// Outil (Phase 3).
    Tool,
}

/// Inventaire d'un agent (quantité par kind).
#[derive(Component, Clone, Debug, Default, Serialize, Deserialize)]
pub struct Inventory {
    /// Stock par type d'item.
    pub items: HashMap<ItemKind, f32>,
    /// Capacité de charge max (kg).
    pub capacity_kg: f32,
}

impl Inventory {
    /// Inventaire vide d'un humain (~20 kg de capacité).
    pub fn empty_human() -> Self {
        Self { items: HashMap::new(), capacity_kg: 20.0 }
    }

    /// Ajoute (clamp par capacité).
    pub fn add(&mut self, kind: ItemKind, qty: f32) -> f32 {
        let qty = qty.max(0.0);
        let added = qty.min(self.remaining());
        if added <= 0.0 {
            return 0.0;
        }
        let e = self.items.entry(kind).or_insert(0.0);
        *e += added;
        added
    }

    /// Retire.
    pub fn take(&mut self, kind: ItemKind, qty: f32) -> f32 {
        let e = self.items.entry(kind).or_insert(0.0);
        let taken = (*e).min(qty);
        *e -= taken;
        taken
    }

    /// Masse totale.
    pub fn total_mass(&self) -> f32 {
        self.items.values().sum()
    }

    fn remaining(&self) -> f32 {
        (self.capacity_kg - self.total_mass()).max(0.0)
    }
}
