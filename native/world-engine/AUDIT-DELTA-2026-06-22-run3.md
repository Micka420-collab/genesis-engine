# Genesis World Engine — Delta-Audit 2026-06-22 run #3 (J+12, run capacité fer)

**Mode :** scheduled task `genesis-engine--world-realism-system-v20` (routine
veille-first), run **automatique**, user **absent**.
**Successeur de** [`AUDIT-DELTA-2026-06-22.md`](./AUDIT-DELTA-2026-06-22.md) (J+12
run capacité = Cap. C16 `food_curing`) et de son companion
[`AUDIT-DELTA-2026-06-22-meta.md`](./AUDIT-DELTA-2026-06-22-meta.md) (méta/hygiène).
**Contrainte env :** `cargo` absent ([ADR-0008](../../adr/0008-python-rust-frontier.md),
D7). Affirmations Rust = lecture-seule ; CI = vérité.

---

## 0. Verdict express

> **J+12 run #3 EXÉCUTE `R-J12-2` (et consomme `R-J9r2-1`).** La Cap. **C17
> `iron_bloomery`** est le **bas-fourneau du fer** — la **2ᵉ transformation
> métallurgique** (après C13 cuivre) et le **seuil de l'âge du fer**. Elle
> **réalise** le `reaches_iron_bloomery_temp` que C12 exposait et que C13 différait
> explicitement. C'est le **1ᵉʳ retour fire-based depuis C13** (après 3 capacités
> non-fire C14/C15/C16) → **D9 redémarre à 1** (alternance honorée, cf.
> `R-J9r2-1`). C'est aussi la **2ᵉ mutation** de l'arc (après `smelt_at` C13) →
> ouverture de [`crates/MUTATION-FRONTIER.md`](./crates/MUTATION-FRONTIER.md)
> (déclencheur `R-J9-2` / `R-J9r2-2`). **D10 documenté** (un seul point de mutation
> `geo.mine_at`, frontière gelée et sûre). Veille J+12 r#3 : **0 combo externe**
> (tous gated) ; l'archéométrie du bas-fourneau a calibré la physique.

### Le contexte : collision de concurrence résolue proprement

Le run C16 `food_curing` ([audit](./AUDIT-DELTA-2026-06-22.md) §0bis) avait détecté
ce travail `iron_bloomery` **in-flight** et recommandé (`R-J12-2`) de **renuméroter
C16→C17 / p148→p149** au rebase, `food_curing` ayant pris C16/p148. **Fait :**

| Avant (collision) | Après (ce run) |
|---|---|
| `iron_bloomery` revendiquait C16 / p148 (untracked, non vérifié) | **C17 / p149**, vérifié vert |
| `mensonge rendu visible #7` | **#8** (`food_curing` a pris #7) |
| D8 « 10ᵉ par composition » | **11ᵉ** (`food_curing` est la 10ᵉ) |

Séquence finale **cohérente** : C16 salaison (non-fire, axe 3) → **C17 fer
(fire-based, rouvre D9, axe métallurgie)** — exactement l'enchaînement que
`R-J9r2-1` anticipait.

---

## 1. ÉTAPE 0 — Veille technologique (avant tout code)

Détail : [`docs/veille/2026-06-22_VEILLE_iron_bloomery.md`](../../docs/veille/2026-06-22_VEILLE_iron_bloomery.md).
Axes 1/2/3 inchangés depuis la veille C16 (Bevy 0.18 / multi-agent LLM / ML-KEM —
tous gated). **Recherche ciblée** sur l'archéométrie du bas-fourneau (la physique
de C17) :

- **D1 — réduction solide-état + fayalite :** le bas-fourneau opère ~1100–1300 °C,
  **sous** la fusion du fer (1538 °C) → réduction **solide** (CO diffuse dans
  l'oxyde) → **loupe** spongieuse + scorie de **fayalite** (`Fe₂SiO₄`) ;
  rendement lossy < 1 (la scorie retient du Fe). **→ COMBO_TODAY** (calibre la SSOT).
- **D2 — pyrite red-short :** `FeS₂` riche en Fe mais le **soufre indéracinable**
  rend le fer **cassant** ; les vrais minerais sont les oxydes (hématite/magnétite).
  **→ COMBO_TODAY** (la 3ᵉ voie du mensonge #8).
- **CVE :** `CVE-2026-22705` (ML-DSA, medium, patchée) — aucune surface live.

## 2. ÉTAPE 1 — COMBO

- **COMBO_RETENU : aucun combo *externe* intégrable** (gated).
- **COMBO_INTERNE :** C12 `forced_draught` (`reaches_iron_bloomery_temp`, four
  ≥1200 °C réfractaire) **×** C1 `surface_mineralization` (gossan, le « chapeau de
  fer ») **×** catalogue (`yields_per_kg_ore["Fe"]`, `category`). Effet **1+1>2** :
  réduction effective du fer ssi **four réfractaire ET gossan ferreux** coexistent.

## 3. Ce que C17 livre

| Dimension | Avant J+12 r#3 (C16) | Après J+12 r#3 (C17) |
|---|---|---|
| Capacités émergentes (cumul) | 16 | **17** |
| dont *fire-based* | 7 (D9 à 0) | **8** (**D9 redémarre à 1**) |
| Capacités non-fire consécutives | 3 (C14/C15/C16) | **0** (retour au feu) |
| Transformations métallurgiques | 1 (C13 cuivre) | **2** (+ **fer**) |
| Mutations d'état (D10) | 1 (`smelt_at` C13) | **2** (+ `bloom_at` C17) |
| `crates/MUTATION-FRONTIER.md` | absent | **créé** (R-J9-2 fermée) |
| `PY_TO_RUST` | 15 | **15** (D8 par composition, **11ᵉ**) |
| Axe métallurgie (axe 1/5) | cuivre | **fer (âge du fer)** |

**Le design** (émergence absolue, déterministe, « le monde ne ment jamais ») :

- L'agent ne *sait* pas qu'« on réduit la roche rouille au charbon pour en tirer le
  fer ». Il **voit** le chapeau de fer rouille (C1 gossan), **sait faire** un four
  réfractaire soufflé (C12), et **découvre** l'éponge de fer au fond — qu'il faut
  **marteler** (la forge émerge).
- **Physique calculée** (veille) : `iron_bloom_yield` gate sur
  `fd.IRON_BLOOMERY_TEMP_C` (1200 °C, réemploi C12). Oxyde (hématite/magnétite) →
  réduction directe, fer **sain** ; sulfure (pyrite) → **griller** d'abord, fer
  **red-short** ; non-fer (galène/sphalérite) → **0 fer**. Rendement monte avec la
  surchauffe, plafonné < 1 (la fayalite garde du Fe).
- **Mensonge rendu visible #8** (chapeau de fer polyminéral) : le **même** tell
  gossan coiffe l'oxyde (fer sain), le sulfure (fer red-short) ET le non-fer
  (plomb/zinc) — inversion **à 5 voies** (vs binaire C13).
- **Mensonge physique** : le fer **ne fond JAMAIS** (1538 °C hors d'atteinte) →
  réduction solide, `is_solid_bloom` toujours True, `requires_forging` toujours
  True. La fonte/haut-fourneau différés honnêtement (`furnace_reaches_iron_melt`
  toujours False).
- **La RÉDUCTION EFFECTIVE (2ᵉ mutation)** : `bloom_at` **consomme** le minerai
  (réemploi `geo.mine_at`, le **seul** point de mutation de l'arc) et **rend** une
  loupe + scorie. « Le monde ne ment pas » au sens FORT : le fer rendu == la
  promesse de l'oracle.
- **Invariant prouvé** sur monde Genesis réel (seed `0x42`, ancrage déterministe
  **sans injection**) : **78/144 sites de bas-fourneau = 47 hématite (oxyde, fer
  sain) + 31 pyrite (sulfure, red-short), 0 violation**. smoke `p149` **8/8**,
  **23 tests**, ruff clean.

## 4. État des 6 axes (J+12 r#3)

| Axe | État réel | Δ depuis C16 |
|---|---|---|
| 1. Réalisme géologique / **métallurgie** | **âge du fer** (2ᵉ métal après le cuivre) | **+1** |
| 2. Climat & météo | inchangé | 0 |
| 3. Écosystème vivant | inchangé (C16 l'avait entamé) | 0 |
| 4. Performance | statu quo (`gpu` dormant, gated cargo) | 0 |
| 5. API agents IA | **+1 capacité** (réduire le fer) ; 17 caps | **+1** |
| 6. Outils de dév | statu quo (DST backlog C16) | 0 |

## 5. Métriques J+12 r#3

| Métrique | C16 (food_curing) | **C17 (iron_bloomery)** | Δ |
|---|---|---|---|
| Commits Rust (`crates/`) | 0 | **0** (1 doc `.md` MUTATION-FRONTIER, pas de code) | 0 |
| Commits Python `runtime/` | 1 | **1 (C17)** | — |
| Tests pytest (passed) | 714* | **737** | **+23** |
| Capacités émergentes (cumul) | 16 | **17** | +1 |
| dont *fire-based* | 7 | **8** (D9 → 1) | +1 |
| Transformations métallurgiques | 1 | **2** | +1 |
| Mutations d'état (D10) | 1 | **2** | +1 |
| `PY_TO_RUST` | 15 | **15** | 0 |

\* La mesure C16 « 737 » de l'audit voisin comptait par erreur les tests
`iron_bloomery` alors **présents-mais-untracked** sur disque. Mesure propre :
**714 passed / 1 skip** avec `food_curing` seul ; **+23** (`test_iron_bloomery.py`)
→ **737 passed / 1 skip** après C17. Reproductible
(`pytest runtime/tests`, 242 s).

## 6. Recos J+12 r#3 (pour J+13)

### R-J12r3-1 (P1) — D9 a redémarré : prévoir un opérateur orthogonal après le fer
C17 rouvre la chaîne fire-based à 1 (après l'alternance C14/C15/C16). Pour ne pas
ré-escalader D9 (verrou des audits J+8), la **prochaine** capacité devrait être
**orthogonale** (9ᵉ opérateur : eau bouillante / fermentation / levier — liste
`R-J9r2-1`) OU une transformation **non-fire** (p.ex. forge à froid / martelage de
consolidation de la loupe, qui composerait C17 sans feu).

### R-J12r3-2 (P2) — La forge de consolidation ferme la chaîne du fer
La loupe de C17 est **spongieuse** (`requires_forging` True) : le **martelage à
chaud** (cinglage) qui en chasse la scorie et la consolide en fer forgé est la
suite naturelle — **sans nouveau tell, sans feu nouveau** (réutilise la chaleur du
foyer C7). Candidat C18/C19. Le **bronze** (Cu + `cassiterite` **sans tell de
surface** → exploration aveugle) reste l'autre branche métallurgique différée.

### R-J12r3-3 (P2) — MUTATION-FRONTIER : réévaluer à la 1ʳᵉ mutation de DÉPÔT
Les 2 mutations actuelles (C13, C17) ne font que **retirer** via `geo.mine_at`
(D10 gelé sûr). La 1ʳᵉ mutation qui **dépose** (scorie re-déposée, remblai)
touchera le contrat `PY_TO_RUST` (D8) → rouvrir `MUTATION-FRONTIER.md` §4 (D10-b).

### R-J12r3-4 (P1, process) — Coordination multi-agent (rappel R-J12-1)
Ce run confirme l'utilité de `R-J12-1` (audit C16) : un run autonome doit
`git status` / `ls runtime/engine` AVANT de choisir un numéro, pour prendre le
**numéro libre suivant** et éviter la double-numérotation. Appliqué ici (C16→C17,
p148→p149) au lieu d'écraser `food_curing`.

---

**Fin du delta-audit J+12 run #3 (capacité fer).** `R-J12-2` **exécutée**
(renumérotation propre + fer livré) ; `R-J9r2-1` **consommée** (1ᵉʳ retour
fire-based, D9 → 1) ; `R-J9-2`/`R-J9r2-2` **fermée** (MUTATION-FRONTIER.md créé,
D10 documenté/gelé) ; âge du fer ouvert (2ᵉ métallurgie). 1 commit Python (C17),
0 commit Rust. Veille → 0 combo externe ; l'archéométrie a porté la physique.
