<div align="center">

# 🌍 Genesis Engine

### 자율 문명 시뮬레이션 플랫폼
**창발적 문명을 위한 인공 생명 연구소**

🌐 **언어** :
[🇫🇷 Français](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇩🇪 Deutsch](README.de.md) · [🇵🇹 Português](README.pt.md) · [🇮🇹 Italiano](README.it.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇷🇺 Русский](README.ru.md) · [🇰🇷 한국어](README.ko.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇳🇱 Nederlands](README.nl.md) · [🇵🇱 Polski](README.pl.md) · [🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![지구 현실성 ~76%](https://img.shields.io/badge/%EC%A7%80%EA%B5%AC_%ED%98%84%EC%8B%A4%EC%84%B1-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [마스터 프롬프트](docs/MASTER-SCALE-PROMPT-v2.md) · [프로젝트 상태](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md)

*자율 AI 에이전트가 태어나고, 진화하고, 번식하며, 자신만의 역사를 만드는 지속적인 디지털 우주.*

</div>

---

## 🎯 한 문장 비전

> **일관된 물리 환경과 최소 규칙만으로, 언어·경제·갈등·통치 같은 문명의 복잡성이 자율 AI 에이전트로부터 자발적으로 창발할 수 있는가?**

📖 전체 비전: [`FUTURE-VISION.md`](FUTURE-VISION.md)

---

## EMERGENCE SIM v2.0 — ZERO PRE-SCRIPT

**물리 법칙만** 하드코딩됩니다. 언어, 도구, 문명, 지형 변화는 **창발**해야 합니다 — 스크립트 퀘스트 없음.

선언문: **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| 계층 | 내용 |
|------|------|
| **L0** 물리 | 열역학, 중력, 수문, 침식 |
| **L1** 세계 | Genesis, 기후, 생물군계, 자원 |
| **L2** 생물 | 256차원 DNA, 대사, 선택 |
| **L3** 인지 | 국소 지각, 가소성 (NEAT) |
| **L4** 문명 | 무역, 창발적 건설, 정치, 발화 |

**관측:** `make earth-console` → http://127.0.0.1:8090/

---

## 프로젝트 현황

| 영역 | 상태 | 세부 |
|------|------|------|
| 단계 0–2 | ✅ | 인지, 번식, 어휘 |
| 단계 4 | ✅ | 농업, 문자, 정치, 야금 |
| Waves 16–41 | ✅ | Genesis → 기후 → 정착 → 렌더 |
| **지구 현실성 (전체)** | **~76 %** | 7차원 평균 → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (목표 **80 %**) |

**테스트:** **133** pytest · 스모크 **p72–p86**

> **참고:** 이전 문서의 **68 %**, **74 %**, **80 %**는 통합 전역 점수가 아닙니다. **~76 %**가 공식 평균입니다.

---

## ✨ 현재 기능

| 기능 | 상태 |
|------|------|
| 🌍 지구 기반 지형 | ✅ |
| 🌊 수문 (D8 + sv1d) | ✅ |
| 🧬 256유전자 게놈 | ✅ |
| 🗣️ 창발 프로토어 | ✅ |
| 👁️ **Earth Console** (지구본, iso 2.5D, 에이전트 음성) | ✅ |

---

## 빠른 시작

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine && make earth-console
```

```bash
cd runtime && python -m pytest tests/ -q
```

---

## 문서

| 문서 | 역할 |
|------|------|
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | **지구 현실성 ~76 %** (기준) |
| [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) | 라이브 관측 UI |
| [`PROJECT-STATUS.md`](PROJECT-STATUS.md) | 기여자 요약 |

---

## 📜 라이선스

[AGPL-3.0](LICENSE)

[⬆ 맨 위로](#-genesis-engine)
