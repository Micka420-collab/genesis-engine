# Moteur Hybride Quantique-Classique — Roadmap 2030

## 1. Vision

Construire un moteur de rendu/simulation **hybride** : la boucle principale reste classique (CPU/GPU), et un **QPU** (Quantum Processing Unit) est appelé comme co-processeur sur des tâches précises où il a un avantage prouvé. On ne remplace pas le pipeline graphique — on l'augmente.

Cible : matériel quantique tolérant aux fautes (FTQC) disponible vers 2029-2032 (IBM Condor → Kookaburra, IonQ Tempo, Quantinuum Helios, PsiQuantum, Google Willow+).

---

## 2. Architecture cible

```
┌────────────────────────────────────────────┐
│         GAME / SIM LOGIC (C++/Rust)        │
└────────────────────────────────────────────┘
            │                       │
            ▼                       ▼
┌──────────────────┐      ┌──────────────────┐
│  CLASSIC ENGINE  │◄────►│  QUANTUM BROKER  │
│  (Vulkan/DX12/   │      │  (async dispatch │
│   CUDA/Metal)    │      │   + caching)     │
└──────────────────┘      └──────────────────┘
            │                       │
            ▼                       ▼
       GPU / CPU                 QPU (cloud
                                 ou local)
```

**Quantum Broker** = couche d'abstraction. Le moteur classique pousse des *jobs quantiques* (sampling, optimisation, simulation) via une file async. Résultats mis en cache agressivement.

---

## 3. Où le quantique apporte du gain réel

| Domaine                       | Algorithme           | Gain théorique     | Usage moteur                              |
|-------------------------------|----------------------|--------------------|-------------------------------------------|
| Path tracing / Monte Carlo    | Quantum Amplitude Est. | Quadratique (√N) | Échantillonnage lumière, GI, caustiques  |
| Optimisation IA PNJ           | QAOA, VQE            | Polynomial         | Pathfinding global, stratégie temps réel  |
| Simulation physique fine      | Quantum simulation   | Exponentiel        | Fluides, fumée, matériaux déformables    |
| Génération procédurale        | Quantum walks        | Quadratique        | Terrains, biomes, distribution organique  |
| Cryptographie / anti-cheat    | Post-quantum + QKD   | —                  | Sessions sécurisées, intégrité            |
| Compression neuronale         | Quantum ML           | Variable           | Textures, animations, voix                |

**À NE PAS faire en quantique** : rasterization, shaders pixel/vertex, I/O, audio temps réel, logique de gameplay. Tout ce qui est séquentiel ou latence-critique reste classique.

---

## 4. Contraintes techniques 2030

- **Latence QPU** : ~1-10 ms par job utile (post-correction d'erreur). Incompatible avec rendu 60/120 fps en direct → **pré-calcul ou frame N+k**.
- **Bande passante classique↔quantique** : encoder un état quantique coûte cher. Minimiser les allers-retours.
- **Coût** : QPU cloud facturé à la shot. Mise en cache + déduplication obligatoires.
- **Bruit résiduel** : même avec FTQC, prévoir validation classique des résultats critiques.
- **Disponibilité** : prévoir un **fallback classique** systématique. Le jeu doit tourner sans QPU.

---

## 5. Stack technique recommandée

### Côté classique
- Moteur : **Unreal 6 / Unity DOTS / moteur custom Rust+wgpu**
- GPU : Vulkan 1.4+ / DirectX 12 Ultimate / Metal 4
- Async runtime : Tokio (Rust) ou std::execution (C++26)

### Côté quantique
- SDK : **Qiskit 2.x** (IBM), **Cirq** (Google), **PennyLane** (cross-platform, ML hybride), **Q#** (Azure Quantum)
- Cloud : IBM Quantum Network, AWS Braket, Azure Quantum, Google Quantum AI
- Compilation : **Catalyst** (Xanadu) pour compiler hybride classique/quantique
- Simulateur de repli : **Qiskit Aer**, **cuQuantum** (NVIDIA, simulation GPU jusqu'à ~40 qubits)

### Glue
- gRPC / Cap'n Proto pour communication moteur ↔ broker
- Redis / RocksDB pour cache de résultats quantiques
- OpenTelemetry pour profiler les jobs

---

## 6. Roadmap d'implémentation

### Phase 1 — Aujourd'hui → 2027 : Préparation
1. **Identifier 1 à 3 sous-systèmes** isolables (ex : sampler Monte Carlo du path tracer).
2. Implémenter une **interface abstraite** `IQuantumKernel` avec backend classique uniquement.
3. Prototyper en **simulateur Qiskit/PennyLane** sur des problèmes jouets (≤ 20 qubits).
4. Benchmarker : à quel point le quantique *simulé* bat-il (ou pas) la version GPU ?
5. Mettre en place un **pipeline CI** qui teste les deux backends.

### Phase 2 — 2027-2029 : NISQ utile
1. Passer du simulateur à du QPU réel (IBM, IonQ) via cloud.
2. Implémenter QAOA pour 1 problème d'optimisation (ex : placement de PNJ).
3. Mesurer **latence end-to-end** réelle, pas théorique.
4. Construire le **système de cache** quantique (clé = état initial hashé, valeur = distribution résultat).
5. Implémenter le **fallback automatique** si QPU indisponible / trop lent.

### Phase 3 — 2029-2031 : FTQC early access
1. Migrer les kernels vers algorithmes corrigés (Shor-friendly, Grover-friendly).
2. Activer le **path tracing quantique** sur pré-calcul de lightmaps.
3. Intégrer **quantum ML** pour compression de textures/animations.
4. Optimiser le broker : batch des jobs, prefetch spéculatif.

### Phase 4 — 2031+ : Production
1. Premier titre AAA avec composante quantique optionnelle.
2. Mode "Quantum Ultra" qui requiert abonnement cloud QPU.
3. Edge QPU pour stations pro (PsiQuantum / IonQ rack).

---

## 7. Squelette de code (Rust + PennyLane bridge)

```rust
// crates/quantum-broker/src/kernel.rs
pub trait QuantumKernel: Send + Sync {
    type Input;
    type Output;

    fn run_classical(&self, input: &Self::Input) -> Self::Output;
    fn run_quantum(&self, input: &Self::Input) -> impl Future<Output = Self::Output>;

    fn cache_key(&self, input: &Self::Input) -> u64;
}

pub struct Broker {
    backend: Backend,        // Classical | Simulator | QPU(provider)
    cache: Arc<DashMap<u64, CachedResult>>,
    budget_ms: u32,
}

impl Broker {
    pub async fn dispatch<K: QuantumKernel>(
        &self, kernel: &K, input: K::Input,
    ) -> K::Output {
        let key = kernel.cache_key(&input);
        if let Some(hit) = self.cache.get(&key) { return hit.decode(); }

        match self.backend {
            Backend::QPU(_) => {
                tokio::select! {
                    r = kernel.run_quantum(&input) => r,
                    _ = sleep(Duration::from_millis(self.budget_ms as u64)) => {
                        kernel.run_classical(&input)  // fallback
                    }
                }
            }
            _ => kernel.run_classical(&input),
        }
    }
}
```

---

## 8. Risques & mitigation

| Risque                                | Mitigation                                          |
|---------------------------------------|-----------------------------------------------------|
| FTQC repoussé au-delà de 2032         | Pipeline 100 % fonctionnel en simulateur/classique  |
| Coût cloud QPU trop élevé             | Cache agressif + budget par session + tier "free"   |
| Vendor lock-in (IBM vs Google vs…)    | Abstraction via PennyLane / OpenQASM 3              |
| Bruit/erreurs sur résultats           | Vote majoritaire + validation classique             |
| Décalage hype/réalité côté marketing  | Ne jamais promettre "100 % quantique"               |

---

## 9. KPI à suivre

- **Temps moyen d'un dispatch quantique** (cible : < 5 ms p99 en 2030)
- **Cache hit rate** (cible : > 80 %)
- **Différence de qualité** GI quantique vs classique (SSIM, FLIP)
- **Coût $ par heure de jeu** sur backend quantique
- **% fallback** (cible : < 5 % en production)

---

## 10. Lectures à suivre d'ici 2030

- Roadmap IBM Quantum (Condor → Flamingo → Kookaburra)
- Papers : "Quantum Algorithms for Computer Graphics" (Johnston et al.)
- NVIDIA cuQuantum + CUDA-Q docs
- Xanadu PennyLane hybrid tutorials
- Veille : arXiv quant-ph, sections "applied" et "computing"

---

**Principe directeur** : on construit *aujourd'hui* l'architecture qui saura accueillir le QPU *demain*, sans dépendre de lui. Le jour où le matériel arrive, on flippe un flag — pas on réécrit le moteur.
