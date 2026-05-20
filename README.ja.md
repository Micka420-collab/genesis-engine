<div align="center">

# 🌍 Genesis Engine（ジェネシス・エンジン）

### 自律文明シミュレーションプラットフォーム
**創発文明のための人工生命ラボ**

🌐 **言語** :
[🇫🇷 Français](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇩🇪 Deutsch](README.de.md) · [🇵🇹 Português](README.pt.md) · [🇮🇹 Italiano](README.it.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇷🇺 Русский](README.ru.md) · [🇰🇷 한국어](README.ko.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇳🇱 Nederlands](README.nl.md) · [🇵🇱 Polski](README.pl.md) · [🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![地球リアリズム ~76%](https://img.shields.io/badge/%E5%9C%B0%E7%90%83%E3%83%AA%E3%82%A2%E3%83%AA%E3%82%BA%E3%83%A0-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [マスタープロンプト](docs/MASTER-SCALE-PROMPT-v2.md) · [プロジェクト状況](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md)

*自律 AI エージェントが生まれ、進化し、繁殖し、独自の歴史を形作る永続的なデジタル宇宙。*

</div>

---

## 🎯 一言でいうビジョン

> **一貫した物理環境と最小限のルールのもとで、言語・経済・紛争・統治といった文明の複雑性は自律エージェントから自発的に創発できるか？**

📖 完全なビジョン: [`FUTURE-VISION.md`](FUTURE-VISION.md)

---

## EMERGENCE SIM v2.0 — ZERO PRE-SCRIPT（ゼロ事前脚本）

ハードコードされるのは **物理法則のみ**。言語・道具・文明・地形形成はエージェントから **創発** しなければならない。

マニフェスト: **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| 層 | 内容 |
|----|------|
| **L0** 物理 | 熱力学、重力、水文、侵食 |
| **L1** 世界 | Genesis、気候、バイオーム、資源 |
| **L2** 生物 | 256 次元 DNA、代謝、選択 |
| **L3** 認知 | 局所知覚、可塑性（NEAT） |
| **L4** 文明 | 交易、創発的建設、政治、発話 |

**観測:** `make earth-console` → http://127.0.0.1:8090/

---

## プロジェクトの現状

| 領域 | 状態 | 詳細 |
|------|------|------|
| フェーズ 0–2 | ✅ | 認知、繁殖、語彙 |
| フェーズ 4 | ✅ | 農業、文字、政治、冶金 |
| Waves 16–41 | ✅ | Genesis → 気候 → 集落 → レンダリング |
| **地球リアリズム（全体）** | **~76 %** | 7 次元の平均 → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md)（目標 **80 %**） |

**テスト:** **152** pytest · スモーク **p72–p86**

> **注:** 旧ドキュメントの **68 %**、**74 %**、**80 %** は統一グローバル値ではない。**~76 %** が公式平均。

---

## ✨ 現在の機能

| 機能 | 状態 |
|------|------|
| 🌍 地球アンカー地形 | ✅ |
| 🌊 水文（D8 + sv1d） | ✅ |
| 🧬 256 遺伝子ゲノム | ✅ |
| 🗣️ 創発プロト言語 | ✅ |
| 👁️ **Earth Console**（地球儀・等角 2.5D・エージェント音声） | ✅ |

---

## クイックスタート

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine && make earth-console
```

```bash
cd runtime && python -m pytest tests/ -q
```

---

## ドキュメント

| 文書 | 役割 |
|------|------|
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | **地球リアリズム ~76 %**（公式） |
| [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) | ライブ観測 UI |
| [`PROJECT-STATUS.md`](PROJECT-STATUS.md) | 貢献者向け概要 |

---

## 📜 ライセンス

[AGPL-3.0](LICENSE)

[⬆ トップへ](#-genesis-engineジェネシスエンジン)
