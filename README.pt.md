<div align="center">

# 🌍 Genesis Engine

### Plataforma de simulação civilizacional autônoma
**Laboratório de vida artificial para civilizações emergentes**

🌐 **Idiomas** :
[🇫🇷 Français](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇩🇪 Deutsch](README.de.md) · [🇵🇹 Português](README.pt.md) · [🇮🇹 Italiano](README.it.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇷🇺 Русский](README.ru.md) · [🇰🇷 한국어](README.ko.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇳🇱 Nederlands](README.nl.md) · [🇵🇱 Polski](README.pl.md) · [🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Realismo Terra ~76%](https://img.shields.io/badge/realismo_Terra-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [Prompt mestre](docs/MASTER-SCALE-PROMPT-v2.md) · [Estado do projeto](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md)

*Um universo digital persistente onde agentes de IA autônomos nascem, evoluem, reproduzem e moldam a própria história.*

</div>

---

## 🎯 Visão em uma frase

> **Dada uma física coerente e regras mínimas, a complexidade civilizacional — linguagem, economia, conflito, governo — pode emergir espontaneamente de agentes autônomos?**

📖 Visão completa: [`FUTURE-VISION.md`](FUTURE-VISION.md)

---

## EMERGENCE SIM v2.0 — ZERO PRE-SCRIPT

Apenas **leis físicas** estão codificadas. Linguagem, ferramentas, civilização e terraformation devem **emergir** — nunca missões scriptadas.

Manifesto: **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| Camada | Conteúdo |
|--------|----------|
| **L0** Física | Termo, gravidade, hidrologia, erosão |
| **L1** Mundo | Genesis, clima, biomas, recursos |
| **L2** Biologia | DNA 256-D, metabolismo, seleção |
| **L3** Cognição | Percepção local, plasticidade (NEAT) |
| **L4** Civilização | Comércio, construção emergente, política, fala |

**Observador:** `make earth-console` → http://127.0.0.1:8090/

---

## Estado do projeto

| Eixo | Estado | Detalhe |
|------|--------|---------|
| Fases 0–2 | ✅ | Cognição, reprodução, léxico |
| Fase 4 | ✅ | Agricultura, escrita, política, metalurgia |
| Waves 16–41 | ✅ | Genesis → clima → assentamentos → render |
| **Realismo Terra (global)** | **~76 %** | Média de 7 dimensões → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (meta **80 %**) |

**Testes:** **157** pytest · smokes **p72–p87**

> **Nota:** Documentos antigos mostravam **68 %**, **74 %** ou **80 %** como global. **~76 %** é a média unificada.

---

## ✨ O que funciona hoje

| Capacidade | Estado |
|------------|--------|
| 🌍 Terreno ancorado na Terra | ✅ |
| 🌊 Hidrologia (D8 + sv1d) | ✅ |
| 🧬 Genoma 256 genes + demografia | ✅ |
| 🗣️ Proto-linguagem emergente | ✅ |
| 👁️ **Earth Console** (globo, iso 2.5D, voz dos agentes) | ✅ |

---

## Início rápido

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine && make earth-console
```

```bash
cd runtime && python -m pytest tests/ -q
python run.py terre --ticks 500
```

---

## Documentação

| Documento | Papel |
|-----------|-------|
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | **Realismo Terra ~76 %** (referência) |
| [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) | Observador ao vivo |
| [`PROJECT-STATUS.md`](PROJECT-STATUS.md) | Resumo para contribuidores |

---

## 📜 Licença

[AGPL-3.0](LICENSE)

[⬆ Voltar ao topo](#-genesis-engine)
