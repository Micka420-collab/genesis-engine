# Documentation Genesis Engine

Index de la documentation **orientée contributeurs**. Pour démarrer le code : [`../README.md`](../README.md) et [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

---

## Statut & roadmap

| Document | Description |
|----------|-------------|
| [`../PROJECT-STATUS.md`](../PROJECT-STATUS.md) | **Synthèse** phases, waves 16–41, réalisme ~63 % |
| [`../NEXT-SPRINT.md`](../NEXT-SPRINT.md) | File de travail détaillée (journal session) |
| [`../ROADMAP.md`](../ROADMAP.md) | Phases produit 0 → 5 |
| [`ROADMAP-REALISME-TERRE.md`](ROADMAP-REALISME-TERRE.md) | Grille réalisme Terre + commandes vérif p72–p79 |
| [`../FUTURE-VISION.md`](../FUTURE-VISION.md) | Vision long terme (contrefactuelle humanity) |

---

## Guides par stack

| Document | Description |
|----------|-------------|
| [`../runtime/README.md`](../runtime/README.md) | Runtime Python, smokes, dashboard |
| [`../native/world-engine/README.md`](../native/world-engine/README.md) | Moteur Rust, cargo, WorldGraph |
| [`STACK.md`](STACK.md) | Stack technique 2026 |
| [`REALITY-ENGINE.md`](REALITY-ENGINE.md) | Hydrologie, faune, saisons, maladies |
| [`BIOSPHERE-EMERGENCE.md`](BIOSPHERE-EMERGENCE.md) | Pipeline 100 % émergent : protocellules → humains |
| [`WORLD-CREATION-SOFTWARE.md`](WORLD-CREATION-SOFTWARE.md) | WorldBuilder, exports, library |
| [`PROJECT-VIABILITY.md`](PROJECT-VIABILITY.md) | Entry points supportés, gates install |

---

## Historique des sessions (sprints)

Journal chronologique de ce que les agents IA et contributeurs ont livré :

- **Index & convention** : [`sprints/README.md`](sprints/README.md)
- **Session majeure 18 mai 2026** : Waves **16 → 41** (`sprints/2026-05-18_WAVE*.md`)
  - W16 genesis · W17 tectonique · W18 hydrologie chunk · W19–21 climat/marine
  - W22 global genesis · W23–26 NCA/WFC · W27 render · W28–32 settlements/polity
  - W33–40 observateurs · W41 atmosphère temporelle
- Phases antérieures : `2026-05-11` … `2026-05-16` dans le même dossier

> **Politique** : ne pas déplacer massivement ces fichiers — l’index suffit. Renommer selon `YYYY-MM-DD_<TYPE>-<topic>.md`.

---

## Renders & conformité visuelle

Assets PNG/GIF de preuve (ne pas supprimer sans accord équipe) :

| Dossier | Contenu |
|---------|---------|
| [`compliance/renders/`](compliance/renders/) | Captures compliance waves 27–37 (chunks, macro, trade, iso, timelapse) |
| [`renders/`](renders/) | Sorties récentes (ex. wave 41 atmosphère jour/nuit, iso 36) |

Les smokes régénèrent certaines images ; les README et sprints **pointent** vers ces chemins.

---

## Architecture & gouvernance (racine repo)

| Zone | Chemin |
|------|--------|
| Spec contractuelle | [`../Genesis_Engine_Architecture_v1.0.docx`](../Genesis_Engine_Architecture_v1.0.docx) |
| ADR | [`../adr/`](../adr/) |
| Architecture notes | [`../architecture/`](../architecture/) |
| Specs techniques | [`../specs/`](../specs/) |
| Éthique | [`../ethics/`](../ethics/), [`../ETHICS.md`](../ETHICS.md) |
| Sécurité | [`../security/`](../security/), [`../SECURITY.md`](../SECURITY.md) |
| Ops | [`../ops/`](../ops/) |
| Protocoles | [`../protocol/`](../protocol/) |

---

## Docs conceptuelles numérotées

| Fichier | Sujet |
|---------|--------|
| [`01-vision-and-philosophy.md`](01-vision-and-philosophy.md) | Hypothèse, philosophie |
| [`02-system-overview.md`](02-system-overview.md) | Vue couches |
| [`03-agent-cognition.md`](03-agent-cognition.md) | Cognition agents (PIANO) |
| [`04-world-engine.md`](04-world-engine.md) | Moteur monde |
| [`05-emergent-systems.md`](05-emergent-systems.md) | Langage, économie, religion |
| [`06-observation-and-tooling.md`](06-observation-and-tooling.md) | Observatoire, exports |
| [`07-glossary-and-conventions.md`](07-glossary-and-conventions.md) | Glossaire |

Référence croisée : [`INDEX.md`](INDEX.md).

---

## Audits & améliorations

| Fichier | Description |
|---------|-------------|
| [`../AUDIT.md`](../AUDIT.md) | Audit racine |
| [`../runtime/AUDIT.md`](../runtime/AUDIT.md) | Audit runtime |
| [`IMPROVEMENTS-SESSION.md`](IMPROVEMENTS-SESSION.md) | Notes session réalisme (mai 2026) |

---

## Gouvernance contributeur

| Document | Description |
|----------|-------------|
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Workflow, tests, conventions |
| [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) | Code de conduite (référence ; fichier local à ajouter si besoin) |
| [`../CHANGELOG.md`](../CHANGELOG.md) | Journal des versions |
