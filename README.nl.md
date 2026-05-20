<div align="center">

# 🌍 Genesis Engine

### Platform voor autonome beschavings simulatie
**Een kunstmatig-leven laboratorium voor emergente beschavingen**

🌐 **Talen** :
[🇫🇷 Français](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇩🇪 Deutsch](README.de.md) · [🇵🇹 Português](README.pt.md) · [🇮🇹 Italiano](README.it.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇷🇺 Русский](README.ru.md) · [🇰🇷 한국어](README.ko.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇳🇱 Nederlands](README.nl.md) · [🇵🇱 Polski](README.pl.md) · [🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Aarde realisme ~76%](https://img.shields.io/badge/Aarde_realisme-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [Master prompt](docs/MASTER-SCALE-PROMPT-v2.md) · [Projectstatus](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md)

*Een persistent digitaal universum waarin autonome AI-agenten worden geboren, evolueren, zich voortplanten en hun eigen geschiedenis vormen.*

</div>

---

## 🎯 Visie in één zin

> **Kunnen taal, economie, conflict en bestuur spontaan ontstaan uit autonome AI-agenten in een samenhangende fysieke omgeving?**

📖 Volledige visie: [`FUTURE-VISION.md`](FUTURE-VISION.md)

---

## EMERGENCE SIM v2.0 — ZERO PRE-SCRIPT

Alleen **natuurwetten** zijn vastgelegd. Taal, gereedschappen, beschaving en terraforming moeten **emergent** zijn — geen gescripte quests.

Manifest: **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| Laag | Inhoud |
|------|--------|
| **L0** Fysica | Thermo, zwaartekracht, hydrologie, erosie |
| **L1** Wereld | Genesis, klimaat, biomen, hulpbronnen |
| **L2** Biologie | 256-D DNA, metabolisme, selectie |
| **L3** Cognitie | Lokale waarneming, plasticiteit (NEAT) |
| **L4** Beschaving | Handel, emergente bouw, politiek, spraak |

**Observator:** `make earth-console` → http://127.0.0.1:8090/

---

## Projectstatus

| Gebied | Status | Detail |
|--------|--------|--------|
| Fasen 0–2 | ✅ | Cognitie, voortplanting, lexicon |
| Fase 4 | ✅ | Landbouw, schrift, politiek, metallurgie |
| Waves 16–41 | ✅ | Genesis → klimaat → nederzettingen → render |
| **Aarde-realisme (globaal)** | **~76 %** | Gemiddelde 7 dimensies → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (doel **80 %**) |

**Tests:** **152** pytest · smokes **p72–p87**

> **Let op:** Oudere docs toonden **68 %**, **74 %** of **80 %** als globaal. **~76 %** is het officiële gemiddelde.

---

## ✨ Wat werkt vandaag

| Mogelijkheid | Status |
|--------------|--------|
| 🌍 Aarde-verankerd terrein | ✅ |
| 🌊 Hydrologie (D8 + sv1d) | ✅ |
| 🧬 256-genen genoom | ✅ |
| 🗣️ Emergent proto-taal | ✅ |
| 👁️ **Earth Console** (globe, iso 2.5D, agentenstem) | ✅ |

---

## Snel starten

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine && make earth-console
```

```bash
cd runtime && python -m pytest tests/ -q
```

---

## Documentatie

| Document | Rol |
|----------|-----|
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | **Aarde-realisme ~76 %** (referentie) |
| [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) | Live observator |
| [`PROJECT-STATUS.md`](PROJECT-STATUS.md) | Samenvatting bijdragers |

---

## 📜 Licentie

[AGPL-3.0](LICENSE)

[⬆ Naar boven](#-genesis-engine)
