<div align="center">

# 🌍 Genesis Engine

### Платформа автономного моделирования цивилизаций
**Лаборатория искусственной жизни для эмерджентных цивилизаций**

🌐 **Языки** :
[🇫🇷 Français](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇩🇪 Deutsch](README.de.md) · [🇵🇹 Português](README.pt.md) · [🇮🇹 Italiano](README.it.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇷🇺 Русский](README.ru.md) · [🇰🇷 한국어](README.ko.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇳🇱 Nederlands](README.nl.md) · [🇵🇱 Polski](README.pl.md) · [🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Реализм Земли ~76%](https://img.shields.io/badge/%D0%A0%D0%B5%D0%B0%D0%BB%D0%B8%D0%B7%D0%BC_%D0%97%D0%B5%D0%BC%D0%BB%D0%B8-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [Мастер-промпт](docs/MASTER-SCALE-PROMPT-v2.md) · [Статус проекта](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md)

*Устойчивая цифровая вселенная, где автономные ИИ-агенты рождаются, эволюционируют, размножаются и формируют собственную историю.*

</div>

---

## 🎯 Видение в одном предложении

> **Может ли сложность цивилизации — язык, экономика, конфликт, управление — спонтанно возникать из автономных ИИ-агентов в согласованной физической среде?**

📖 Полное видение: [`FUTURE-VISION.md`](FUTURE-VISION.md)

---

## EMERGENCE SIM v2.0 — ZERO PRE-SCRIPT

Зашиты только **физические законы**. Язык, инструменты, цивилизация и терраформирование должны **эмерджировать** — без сценарных квестов.

Манифест: **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| Слой | Содержание |
|------|------------|
| **L0** Физика | Термо, гравитация, гидрология, эрозия |
| **L1** Мир | Genesis, климат, биомы, ресурсы |
| **L2** Биология | 256-D ДНК, метаболизм, отбор |
| **L3** Когниция | Локальное восприятие, пластичность (NEAT) |
| **L4** Цивилизация | Торговля, эмерджентное строительство, политика, речь |

**Наблюдатель:** `make earth-console` → http://127.0.0.1:8090/

---

## Статус проекта

| Область | Статус | Детали |
|---------|--------|--------|
| Фазы 0–2 | ✅ | Когниция, размножение, лексикон |
| Фаза 4 | ✅ | Сельское хозяйство, письменность, политика |
| Waves 16–41 | ✅ | Genesis → климат → поселения → рендер |
| **Реализм Земли (глобально)** | **~76 %** | Среднее 7 измерений → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (цель **80 %**) |

**Тесты:** **152** pytest · смоки **p72–p87**

> **Примечание:** Старые документы указывали **68 %**, **74 %** или **80 %** как глобальный балл. **~76 %** — единая средняя.

---

## ✨ Что работает сегодня

| Возможность | Статус |
|-------------|--------|
| 🌍 Рельеф, привязанный к Земле | ✅ |
| 🌊 Гидрология (D8 + sv1d) | ✅ |
| 🧬 Геном 256 генов | ✅ |
| 🗣️ Эмерджентный прото-язык | ✅ |
| 👁️ **Earth Console** (глобус, iso 2.5D, речь агентов) | ✅ |

---

## Быстрый старт

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine && make earth-console
```

```bash
cd runtime && python -m pytest tests/ -q
```

---

## Документация

| Документ | Роль |
|----------|------|
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | **Реализм Земли ~76 %** (эталон) |
| [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) | Живой наблюдатель |
| [`PROJECT-STATUS.md`](PROJECT-STATUS.md) | Сводка для контрибьюторов |

---

## 📜 Лицензия

[AGPL-3.0](LICENSE)

[⬆ Наверх](#-genesis-engine)
