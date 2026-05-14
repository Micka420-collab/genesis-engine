//! Lignée — graphe parent → enfants.
//!
//! Sert à dessiner les arbres généalogiques + à mesurer la persistance d'une
//! population (combien de descendants un fondateur a-t-il à T+10 000 ticks ?).

use ge_core::AgentId;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Carte des lignées.
#[derive(Default, Clone, Debug, Serialize, Deserialize)]
pub struct LineageMap {
    /// Pour chaque agent, ses enfants.
    children: HashMap<AgentId, Vec<AgentId>>,
    /// Pour chaque agent, son ou ses parents.
    parents: HashMap<AgentId, Vec<AgentId>>,
}

impl LineageMap {
    /// Constructeur.
    pub fn new() -> Self {
        Self::default()
    }

    /// Enregistre une naissance.
    pub fn record_birth(&mut self, child: AgentId, parents: &[AgentId]) {
        self.parents.insert(child, parents.to_vec());
        for p in parents {
            self.children.entry(*p).or_default().push(child);
        }
    }

    /// Enfants directs.
    pub fn children(&self, id: AgentId) -> &[AgentId] {
        self.children.get(&id).map(Vec::as_slice).unwrap_or(&[])
    }

    /// Compte transitif des descendants.
    pub fn descendant_count(&self, id: AgentId) -> usize {
        let mut count = 0;
        let mut stack = vec![id];
        let mut visited = std::collections::HashSet::new();
        while let Some(node) = stack.pop() {
            if !visited.insert(node) {
                continue;
            }
            for c in self.children(node) {
                count += 1;
                stack.push(*c);
            }
        }
        count
    }
}
