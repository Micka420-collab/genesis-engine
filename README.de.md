<div align="center">

# 🌍 Genesis Engine

### Plattform für autonome Zivilisationssimulation
**Ein Labor für künstliches Leben und emergente Zivilisationen**

🌐 **Sprachen** :
[🇫🇷 Français](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇩🇪 Deutsch](README.de.md) · [🇵🇹 Português](README.pt.md) · [🇮🇹 Italiano](README.it.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇷🇺 Русский](README.ru.md) · [🇰🇷 한국어](README.ko.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇳🇱 Nederlands](README.nl.md) · [🇵🇱 Polski](README.pl.md) · [🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Earth realism ~76%](https://img.shields.io/badge/Erd_Realismus-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [Master-Prompt](docs/MASTER-SCALE-PROMPT-v2.md) · [Projektstatus](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md)

*Ein persistentes digitales Universum, in dem autonome KI-Agenten entstehen, sich entwickeln, fortpflanzen und ihre eigene Geschichte formen.*

</div>

---

## 🎯 Vision in einem Satz

> **Kann zivilisatorische Komplexität — Sprache, Wirtschaft, Konflikt, Governance — spontan aus autonomen KI-Agenten in einer kohärenten physikalischen Umgebung entstehen?**

📖 Vollständige Vision: [`FUTURE-VISION.md`](FUTURE-VISION.md)

---

## EMERGENCE SIM v2.0 — ZERO PRE-SCRIPT

Nur **physikalische Gesetze** sind fest codiert. Sprache, Werkzeuge, Zivilisation und Terraforming müssen **emergieren** — keine skriptierten Quests.

Manifest: **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| Schicht | Inhalt |
|---------|--------|
| **L0** Physik | Thermo, Gravitation, Hydrologie, Erosion |
| **L1** Welt | Genesis, Klima, Biome, Ressourcen |
| **L2** Biologie | 256-D-DNA, Stoffwechsel, Selektion |
| **L3** Kognition | Lokale Wahrnehmung, Plastizität (NEAT) |
| **L4** Zivilisation | Handel, emergenter Bau, Politik, Sprache |

**Beobachter:** `make earth-console` → http://127.0.0.1:8090/

---

## Projektstand

| Bereich | Status | Detail |
|---------|--------|--------|
| Phasen 0–2 | ✅ | Kognition, Fortpflanzung, Lexikon |
| Phase 4 | ✅ | Landwirtschaft, Schrift, Politik, Metallurgie |
| Waves 16–41 | ✅ | Genesis → Klima → Siedlungen → Render |
| **Erd-Realismus (global)** | **~76 %** | 7-Dimensionen-Durchschnitt → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (Ziel **80 %**) |

**Tests:** **152** pytest · Smokes **p72–p86**

> **Hinweis:** Ältere Docs zeigten **68 %**, **74 %** oder **80 %** als Globalwert. **~76 %** ist der einheitliche Durchschnitt.

---

## ✨ Was heute funktioniert

| Fähigkeit | Status |
|-----------|--------|
| 🌍 Erdverankertes Terrain (Copernicus + WorldCover) | ✅ |
| 🌊 Hydrologie (D8 + sv1d) | ✅ |
| 🧬 256-Gene-Genom + Demografie | ✅ |
| 🗣️ Emergentes Proto-Sprache | ✅ |
| 👁️ **Earth Console** (Globus, Iso 2.5D, Agentenstimme) | ✅ |
| 💾 Speichern / Laden / Verzweigen | ✅ |

---

## Schnellstart

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine
make earth-console
# Browser: http://127.0.0.1:8090/
```

```bash
cd runtime && python -m pytest tests/ -q
python run.py terre --ticks 500
```

---

## Dokumentation

| Dokument | Rolle |
|----------|-------|
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | **Erd-Realismus ~76 %** (Referenz) |
| [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) | Live-Beobachter |
| [`PROJECT-STATUS.md`](PROJECT-STATUS.md) | Status für Mitwirkende |

---

## 📜 Lizenz

[AGPL-3.0](LICENSE) — Open Source. Bei SaaS-Hosting Quellcode der Modifikationen bereitstellen.

[⬆ Nach oben](#-genesis-engine)
