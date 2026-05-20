<div align="center">

# 🌍 Genesis Engine

### स्वायत्त सभ्यता सिमुलेशन प्लेटफ़ॉर्म
**उभरती सभ्यताओं के लिए कृत्रिम जीवन प्रयोगशाला**

🌐 **भाषाएँ** :
[🇫🇷 Français](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇩🇪 Deutsch](README.de.md) · [🇵🇹 Português](README.pt.md) · [🇮🇹 Italiano](README.it.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇷🇺 Русский](README.ru.md) · [🇰🇷 한국어](README.ko.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇳🇱 Nederlands](README.nl.md) · [🇵🇱 Polski](README.pl.md) · [🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![पृथ्वी यथार्थवाद ~76%](https://img.shields.io/badge/%E0%A4%AA%E0%A5%83%E0%A4%A5%E0%A5%8D%E0%A4%B5%E0%A5%80_%E0%A4%AF%E0%A4%A5%E0%A4%BE%E0%A4%B0%E0%A5%8D%E0%A4%A4%E0%A4%B5%E0%A4%BE%E0%A4%A6-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [मास्टर प्रॉम्प्ट](docs/MASTER-SCALE-PROMPT-v2.md) · [परियोजना स्थिति](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md)

*एक स्थायी डिजिटल ब्रह्मांड जहाँ स्वायत्त AI एजेंट जन्म लेते हैं, विकसित होते हैं, प्रजनन करते हैं और अपना इतिहास बनाते हैं।*

</div>

---

## 🎯 एक वाक्य में दृष्टि

> **क्या सुसंगत भौतिक वातावरण और न्यूनतम नियमों के साथ, भाषा, अर्थव्यवस्था, संघर्ष और शासन जैसी सभ्यतागत जटिलता स्वायत्त AI एजेंटों से स्वतः उभर सकती है?**

📖 पूर्ण दृष्टि: [`FUTURE-VISION.md`](FUTURE-VISION.md)

---

## EMERGENCE SIM v2.0 — ZERO PRE-SCRIPT

केवल **भौतिक नियम** हार्डकोड हैं। भाषा, उपकरण, सभ्यता और भू-रूपांतरण को **उभरना** चाहिए — स्क्रिप्टेड क्वेस्ट नहीं।

घोषणापत्र: **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| परत | सामग्री |
|-----|---------|
| **L0** भौतिकी | ऊष्मा, गुरुत्व, जल, अपरदन |
| **L1** विश्व | Genesis, जलवायु, बायोम, संसाधन |
| **L2** जीव विज्ञान | 256-D DNA, चयापचय, चयन |
| **L3** संज्ञान | स्थानीय धारणा, लचीलापन (NEAT) |
| **L4** सभ्यता | व्यापार, उभरता निर्माण, राजनीति, भाषण |

**प्रेक्षक:** `make earth-console` → http://127.0.0.1:8090/

---

## परियोजना की स्थिति

| क्षेत्र | स्थिति | विवरण |
|--------|--------|--------|
| चरण 0–2 | ✅ | संज्ञान, प्रजनन, शब्दकोश |
| चरण 4 | ✅ | कृषि, लेखन, राजनीति, धातुकर्म |
| Waves 16–41 | ✅ | Genesis → जलवायु → बस्तियाँ → रेंडर |
| **पृथ्वी यथार्थवाद (वैश्विक)** | **~76 %** | 7 आयामों का औसत → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (लक्ष्य **80 %**) |

**परीक्षण:** **133** pytest · स्मोक **p72–p86**

> **नोट:** पुराने दस्तावेज़ों में **68 %**, **74 %** या **80 %** वैश्विक नहीं थे। **~76 %** आधिकारिक औसत है।

---

## ✨ आज क्या काम करता है

| क्षमता | स्थिति |
|--------|--------|
| 🌍 पृथ्वी-आधारित भूभाग | ✅ |
| 🌊 जल विज्ञान (D8 + sv1d) | ✅ |
| 🧬 256-जीन जीनोम | ✅ |
| 🗣️ उभरती प्रोटो-भाषा | ✅ |
| 👁️ **Earth Console** (ग्लोब, iso 2.5D, एजेंट आवाज़) | ✅ |

---

## त्वरित शुरुआत

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine && make earth-console
```

```bash
cd runtime && python -m pytest tests/ -q
```

---

## प्रलेखन

| दस्तावेज़ | भूमिका |
|-----------|--------|
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | **पृथ्वी यथार्थवाद ~76 %** (संदर्भ) |
| [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) | लाइव प्रेक्षक |
| [`PROJECT-STATUS.md`](PROJECT-STATUS.md) | योगदानकर्ता सारांश |

---

## 📜 लाइसेंस

[AGPL-3.0](LICENSE)

[⬆ ऊपर](#-genesis-engine)
