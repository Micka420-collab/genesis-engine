<div align="center" dir="rtl">

# 🌍 Genesis Engine (محرّك التكوين)

### منصة محاكاة الحضارات المستقلة
**مختبر حياة اصطناعية للحضارات الناشئة**

🌐 **اللغات** :
[🇫🇷 Français](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇩🇪 Deutsch](README.de.md) · [🇵🇹 Português](README.pt.md) · [🇮🇹 Italiano](README.it.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇷🇺 Русский](README.ru.md) · [🇰🇷 한국어](README.ko.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇳🇱 Nederlands](README.nl.md) · [🇵🇱 Polski](README.pl.md) · [🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3140/)
[![Status: Phase 5g](https://img.shields.io/badge/status-Phase_5g_alpha-orange.svg)](#️-خارطة-الطريق)
[![Earth-anchored](https://img.shields.io/badge/Earth-anchored-green.svg)](#-مرتبط-بالأرض-الحقيقية)
[![Deterministic](https://img.shields.io/badge/deterministic-✓-purple.svg)](#-الحتمية)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)
[![واقعية الأرض ~76%](https://img.shields.io/badge/%D9%88%D8%A7%D9%82%D8%B9%D9%8A%D8%A9_%D8%A7%D9%84%D8%A3%D8%B1%D8%B6-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [المطالبة الرئيسية](docs/MASTER-SCALE-PROMPT-v2.md) · [حالة المشروع](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md) · [Runtime](runtime/README.md) · [Rust](native/world-engine/README.md)

*بناء كون رقمي دائم تولد فيه عملاء الذكاء الاصطناعي المستقلون حقًا، ويتطوّرون، ويتكاثرون، ويصوغون تاريخهم الخاص، ويسمحون بالملاحظة العلمية للحضارات الاصطناعية الناشئة.*

[الرؤية](#-الرؤية-في-جملة) ·
[البنية](#️-بنية-طبقية) ·
[البدء السريع](#-البدء-السريع) ·
[خارطة الطريق](#️-خارطة-الطريق) ·
[المساهمة](#-كيف-تساهم) ·
[المواصفات الكاملة](Genesis_Engine_Architecture_v1.0.docx)

</div>

---

<div dir="rtl">

## 🎯 الرؤية في جملة

> **في ظل بيئة فيزيائية متماسكة ومجموعة دنيا من القواعد الأساسية، هل يمكن للتعقيد الحضاري — اللغة، الاقتصاد، الدين، العلم، النزاع، الحكم — أن ينبثق تلقائيًا من عملاء ذكاء اصطناعي مستقلين؟**

فرضية قابلة للتفنيد وقابلة للاستنساخ، مستوحاة من Conway (لعبة الحياة) و Ray (Tierra) و Generative Agents (Park 2023) و Project Sid (PIANO 2024) ونماذج العالم 2025-2026 (Genie 3، Cosmos، V-JEPA-2، Marble).

### 🔭 الرؤية على المدى الطويل — البشرية البديلة

> **الهدف النهائي**: إعطاء عملاء الذكاء الاصطناعي جميع أسس العالم الحقيقي (الفيزياء، الكيمياء، المواد، البيولوجيا، الجغرافيا)، ثم تركهم يستكشفون **أنماط بناء أخرى، هياكل اجتماعية أخرى**، لرؤية **ما كان يمكن للبشرية أن تفعله**. يمكن للذكاء الاصطناعي **اختراع مواد جديدة** — ولكن دائمًا مع **احترام قوانين الطبيعة** (حفظ الكتلة والطاقة، طاقات الروابط، الديناميكا الحرارية).

التاريخ البشري هو سحب واحد من بين مليارات الاحتمالات. يهدف Genesis Engine إلى العمل كـ **مختبر بديل**: إذا أعدنا تشغيل تاريخ الأرض 1000 مرة بنفس القوانين الفيزيائية، فكم من الحضارات ستشبه حضارتنا؟

📖 **اقرأ الرؤية الكاملة**: [`FUTURE-VISION.md`](FUTURE-VISION.md) — 4 ركائز، خارطة طريق من 4 موجات، معايير النجاح، مراجع علمية.

---

## EMERGENCE SIM v2.0 — ZERO PRE-SCRIPT (بدون سيناريو مسبق)

**القوانين الفيزيائية فقط** مبرمجة مسبقًا. يجب أن **تنبثق** اللغة والأدوات والحضارة وتشكيل التضاريس من العملاء — وليس مهامًا مكتوبة مسبقًا.

البيان الكامل: **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| الطبقة | المحتوى |
|--------|---------|
| **L0** فيزياء | ديناميكا حرارية، جاذبية، هيدرولوجيا، تآكل |
| **L1** عالم | Genesis، مناخ، أحياء، موارد |
| **L2** بيولوجيا | DNA 256-D، أيض، انتقاء |
| **L3** إدراك | إدراك محلي، مرونة (هدف NEAT) |
| **L4** حضارة | تجارة، بناء ناشئ، سياسة، كلام |

**المراقبة:** `make earth-console` → http://127.0.0.1:8090/ · مؤشرات: `/api/emergence_metrics`

كل شيء ينبثق من `Simulation.step()` — بلا خط أنابيب منسق. راجع [`PROJECT-STATUS.md`](PROJECT-STATUS.md).

---

## حالة المشروع

| المحور | الحالة | التفاصيل |
|--------|--------|----------|
| المراحل 0–2 (حياة، مجتمع) | ✅ | إدراك، تكاثر، معجم |
| المرحلة 4 (انبثاق حضاري) | ✅ | زراعة، كتابة، سياسة، معادن |
| المرحلة 5 (Genesis-α) | ⏳ | تشغيل طويل 10k سنة محاكاة |
| **Waves 16–41** (عالم واقعي) | ✅ | Genesis → مناخ → مستوطنات → عرض → غلاف جوي → مراقبون |
| **واقعية الأرض (عالمية)** | **~76 %** | متوسط 7 أبعاد → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (هدف **80 %**) |

**الاختبارات:** `pytest runtime/tests` — **152** اختبارًا · smokes **p72–p87** في `make validate-all`.

ملخص: **[`PROJECT-STATUS.md`](PROJECT-STATUS.md)** · قائمة العمل: **[`NEXT-SPRINT.md`](NEXT-SPRINT.md)**.

> **ملاحظة:** وثائق قديمة ذكرت **68 %** أو **74 %** أو **80 %** كدرجة عالمية. **~76 %** هو المتوسط الموحد؛ **80 %** هو الهدف أو درجة المناخ فقط — راجع خارطة الطريق.

---

## ✨ ما الذي يعمل اليوم

| القدرة | الحالة | العرض |
|---|---|---|
| 🌍 **تضاريس مرتبطة بالأرض** (Copernicus DEM + ESA WorldCover) | ✅ | معدل إصابة 100% من AWS Open Data، في أي مكان على الأرض |
| 🌲 **تعاقب نباتي** (Markov بـ 5 حالات، 100+ سنة محاكاة) | ✅ | مرج → أحراش → غابة فتية → غابة ناضجة → غابة قديمة |
| 🌊 **هيدرولوجيا** (تجميع تدفق D8 + اتحاد L1 للمياه) | ✅ | اكتشاف البحيرات/الأنهار، 8% من ليمان = محيط |
| 🦌 **حيوانات Lotka-Volterra** (ديناميكا الغزلان/الذئاب/الأسماك) | ✅ | توازن مستقر بين المفترس والفريسة |
| 🏹 **الصيد** (`ActionKind.HUNT`، 800 كيلو كالوري/غزال) | ✅ | العملاء يجمعون ويصطادون |
| 🐾 **مسارات ناشئة** (آثار الأقدام تعزز قابلية المشي) | ✅ | +0.3 قابلية مشي على المسارات المتكررة |
| 📅 **تقويم حقيقي** (فصول الأرض + ليل/نهار) | ✅ | سنة/يوم/ساعة متزامنة |
| 🧬 **جينوم 256 جين** + 8 مراحل حياة | ✅ | تقاطع + طفرة 1e-4 + كفاءة معرفية |
| 👥 **ديموغرافيا متعددة الأجيال** | ✅ | **23 جيل** ملاحظ في 5 آلاف نبضة |
| 🗣️ **لغة بدائية ناشئة** | ✅ | 95 ألف نطق / 5 آلاف نبضة |
| 🛠️ **اختراع عضوي** (مصنوعات مركبة) | ✅ | `clay_stone_contain`، `flint_stone_grind`... |
| 🏘️ **البناء** (HEARTH، BUILD، متعدد الثقافات) | ✅ | 1 HEARTH مكتمل في 5 آلاف نبضة |
| ⚡ **تسريع الوقت x10/x100/x1000** | ✅ | تسريع **38× / 84×** مقاس، الحتمية محفوظة |
| 🦠 **أوبئة SIR** | ✅ | `infectious_until` + نصف قطر النقل |
| 👁️ **Earth Console** (كرة أرضية، iso 2.5D، صوت العملاء) | ✅ | http://127.0.0.1:8090/ · SSE · `/api/audio` · `/api/languages` |
| 👁️ **لوحة قيادة وضع الإله** (قديم) | ✅ | HTTP `/api/state`، `/api/realism_state`، `/api/demography` |
| 💾 **حفظ / تحميل / تفرع** | ✅ | مكتبة عوالم، تنسيق مفتوح |
| 📤 **تصدير GIS** | ✅ | GeoTIFF (12 طبقة)، PNG خرائطي، OBJ مجسم ارتفاع، JSON |
| 🔬 **الموجة 1: قاعدة معرفة الفيزياء + الكيمياء** | ✅ | 43 عنصرًا، 54 طاقة ربط، البرونز قابل للتركيب |

---

## 🌐 مرتبط بالأرض الحقيقية

يقوم Genesis Engine **بتحميل بيانات Copernicus DEM + ESA WorldCover مباشرة عبر AWS Open Data** (بدون بيانات اعتماد، بدون تنزيل، بثّ عبر `/vsis3` rasterio). تم التحقق من صحته على 4 قارات:

| المنطقة | خط العرض / خط الطول | إصابات L1 | المنطقة الحيوية السائدة | الميزة |
|---|---|---|---|---|
| 🇨🇭 **لوزان** | 46.51 / 6.63 | 480/480 | GARRIGUE 60% | بحيرة ليمان 10.8% |
| 🇪🇬 **الصحراء** | 25.70 / 29.00 | 453/453 | PRAIRIE 100% | صحراء مسطحة |
| 🇧🇷 **الأمازون** | -3.11 / -60.02 | 485/485 | GARRIGUE 89% | غابة استوائية |
| 🇮🇸 **ريكيافيك** | 64.14 / -21.94 | 468/468 | GARRIGUE 72% | شبه قطبي ساحلي |

---

## 🏗️ بنية طبقية

```
┌─ المرحلة 5cd      : عملاء PIANO، البناء، الاختراع، الغلاف الجوي، اللغة
├─ Reality Engine   : هيدرولوجيا + حيوانات + مسارات + فصول + أمراض           ⭐
├─ L2 Sim-Lift      : تعاقب نباتي + تعرية + ميل + قابلية مشي + بحيرة
├─ L1 Earth-Seed    : Copernicus DEM GLO-30 + ESA WorldCover 10m (عبر /vsis3 AWS)
└─ Procedural       : مناطق Whittaker الحيوية (احتياطي حتمي)
```

للحصول على نظرة عامة كاملة على الطبقات المنطقية السبع، راجع [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx).

---

## 🚀 البدء السريع

### المتطلبات

- **Python 3.13+** (تم اختباره على 3.14 Windows)
- **rasterio + pyproj** لوضع الارتباط بالأرض (وإلا الاحتياطي الإجرائي)
- **اتصال بالإنترنت** (فقط لـ Copernicus DEM + ESA WorldCover، وإلا وضع عدم الاتصال)

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine
pip install numpy rasterio pyproj
```

### مرحباً، يا عالم — 30 ثانية

```python
from engine.world_builder import WorldBuilder

# بناء عالم في لوزان، الضفة الشمالية لبحيرة ليمان
world = (WorldBuilder("hello_lausanne")
         .anchor(46.510, 6.633)   # Lausanne-Ouchy
         .size_km(2.0)
         .founders(20)
         .max_agents(1000)
         .with_realism()
         .build())

world.run(2000)
print(world.summary())
```

### المراقبة المباشرة (لوحة قيادة وضع الإله)

```bash
python runtime/scripts/p4_leman_live.py --port 8765
# ثم افتح http://localhost:8765/god_view_v2.html
```

### عرض متعدد المناطق

```bash
python runtime/scripts/multi_region_demo.py
# يولّد 4 عوالم (لوزان + الصحراء + الأمازون + ريكيافيك)
```

### التصدير لـ QGIS / ArcGIS / Mapbox / Blender

```python
from engine.world_export import export_geotiff, export_png_map

export_geotiff(world, "height", "out/dem.tif")
export_png_map(world, "out/map.png")
```

### حفظ / تحميل / تفرع

```python
from engine.world_library import save_world, load_world, branch_world

save_world(world, name="experiment_42")
world2 = load_world("experiment_42")
branch_world("experiment_42", "fork_with_catastrophe")
```

### تسريع الوقت لمراقبة الألفية

```python
world.set_time_warp("x100")
world.run(10_000)
```

---

## 🆚 المقارنة مع أدوات 2026

| القدرة | World Machine | Gaea | NVIDIA Earth-2 | Project Sid | **Genesis Engine** |
|---|---|---|---|---|---|
| DEM مرتبط بالأرض | ❌ | ❌ | ✅ | ❌ | **✅** |
| حضارة متعددة الأجيال | ❌ | ❌ | ❌ | ✅ | **✅ 23 جيل** |
| حيوانات Lotka-Volterra | ❌ | ❌ | ❌ | ❌ | **✅** |
| مسارات ناشئة | ❌ | ❌ | ❌ | ❌ | **✅** |
| فصول متزامنة مع الأرض | ❌ | ❌ | ✅ | ❌ | **✅** |
| وباء SIR | ❌ | ❌ | ❌ | ❌ | **✅** |
| لوحة قيادة مباشرة | ❌ | ❌ | جزئي | ✅ | **✅** |
| حفظ/تحميل/تفرع | ✅ | ✅ | جزئي | جزئي | **✅** |
| تصدير GeoTIFF | ✅ | ✅ | ✅ | ❌ | **✅** |
| حتمية كاملة على مستوى البت | جزئي | جزئي | جزئي | جزئي | **✅** |
| مفتوح المصدر محلي | ❌ | ❌ | ❌ | جزئي | **✅ (AGPL-3)** |

Genesis Engine هو **الأداة الوحيدة** لعام 2026 التي تجمع بين **جغرافيا كوكبية حقيقية** + **حضارة حية** + **استمرارية** + **تصدير GIS قياسي** في مكدّس مفتوح المصدر بنسبة 100% وحتمي.

---

## 🗺️ خارطة الطريق

- **المرحلة 0** — الأساسات (طبقة ECS، monorepo، قابلية الملاحظة) — ✅ الهيكل
- **المرحلة 1** — MVP الحياة (دورة معرفية، موت بيولوجي) — ✅
- **المرحلة 2** — MVP المجتمع (تكاثر، ذاكرة، معجم) — ✅
- **المرحلة 3** — MVP الحضارة (بناء، مقايضة، حرف، صراعات) — 🟡 جزئي
- **المرحلة 4** — انبثاق الحضارة (زراعة، كتابة، دولة) — ⏳
- **المرحلة 5** — Genesis-α عام (2 مؤسس، 10 سنوات حقيقية = 10000 سنة محاكاة) — ⏳

راجع [`NEXT-SPRINT.md`](NEXT-SPRINT.md) لقائمة الأولويات الحية.

---

## 🎲 الحتمية

Genesis Engine **حتمي على مستوى البت** عبر جميع الأنظمة الفرعية عبر `engine.core.prf_rng`. نفس `(seed, region, config)` → نفس العالم، نفس المسار الحضاري، نفس الاختراعات.

> لا `random.random()`. لا `np.random` بدون بذرة. لا `time.time()` في المنطق.

---

## 🤝 كيف تساهم

**Genesis Engine هو مشروع بحثي مفتوح المصدر في الحياة الاصطناعية.** أنت مرحب بك سواء كنت:

- 🧪 **باحث·ة** (alife، أنظمة معقدة، نمذجة قائمة على العملاء)
- 💻 **مهندس·ة** (Python، NumPy، محاكاة، تحسين الأداء)
- 🎨 **منشئ·ة** (رسم 3D، واجهة لوحة القيادة، تصور البيانات)
- 🌍 **جغرافي·ة / جيولوجي·ة** (التحقق من بيانات الأرض L1)
- 📜 **لغوي·ة / أنثروبولوجي·ة** (انبثاق اللغة، الديناميكيات الاجتماعية)
- 🤖 **مهندس·ة ML / LLM** (Phase 5 LLM cognition tier-2)
- 📖 **أخلاقي·ة** (مجلس الأخلاقيات الخارجي — راجع [ETHICS.md](ETHICS.md))

### في 4 خطوات

```bash
# 1. Fork + استنساخ
git clone https://github.com/<your-handle>/genesis-engine.git
cd genesis-engine

# 2. إنشاء فرع
git checkout -b feature/my-contribution

# 3. تشغيل الاختبارات الدخانية
cd runtime
python scripts/p0_smoke.py
python scripts/p12_integration_full.py

# 4. التزام + دفع + PR
git commit -am "feat: وصف موجز بصيغة الأمر"
git push origin feature/my-contribution
# افتح Pull Request على GitHub
```

### اصطلاحات الكود

- **Python 3.13+**، PEP 8، تلميحات الأنواع موصى بها ولكنها ليست مطلوبة.
- **الحتمية إلزامية**: لا `random.*` ولا `np.random.*` بدون بذرة. استخدم `engine.core.prf_rng(seed, namespace, params)`.
- **قاعدة عدم إعادة الكتابة**: تفضيل التوسعة المعيارية على إعادة كتابة الملفات الموجودة.
- **اختبارات دخانية**: يجب على كل نظام فرعي جديد تسليم سكريبت `runtime/scripts/pN_<name>_smoke.py` مع UTF-8 stdout إجباري.

راجع [CONTRIBUTING.md](CONTRIBUTING.md) للحصول على الدليل الكامل.

---

## 🛡️ الأخلاقيات والأمان

- [`ETHICS.md`](ETHICS.md) — الوضع الأخلاقي للعملاء، حدود "المعاناة" المحاكاة، مجلس الأخلاقيات الخارجي
- [`SECURITY.md`](SECURITY.md) — نموذج التهديد، PQC، الإبلاغ عن الثغرات الأمنية
- **الصور الرمزية البشرية**: الموافقة الصريحة، علامة مائية مشفرة، الحق في النسيان GDPR

---

## التوثيق

| مستند | الدور |
|-------|------|
| [`docs/README.md`](docs/README.md) | فهرس التوثيق |
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | **واقعية الأرض ~76 %** (مصدر الحقيقة الوحيد) |
| [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) | مراقب الأرض المباشر |
| [`PROJECT-STATUS.md`](PROJECT-STATUS.md) | ملخص للمساهمين |
| [`ROADMAP.md`](ROADMAP.md) | مراحل المنتج 0–5 |

---

## 📜 الترخيص

[AGPL-3.0](LICENSE) — راجع `Genesis_Engine_Architecture_v1.0.docx` §30.

يمكنك استخدام وتعديل وإعادة توزيع بحرية. إذا قمت باستضافة Genesis Engine كخدمة (SaaS)، فيجب عليك إتاحة الكود المصدري المعدل للمستخدمين.

---

## 🙏 الاعتمادات

تم تصميمه وصيانته من قبل [Micka Delcato](https://github.com/Micka420-collab).
البنية مكتوبة في مايو 2026. الكود الأساسي بلغة Python 3.13+ وNumPy.

---

</div>

<div align="center">

*"بناء كون رقمي دائم، قابل للتوسع، آمن، تولد فيه عملاء ذكاء اصطناعي مستقلين حقًا، يتطورون، يتكاثرون، يصوغون تاريخهم الخاص، ويسمحون بالملاحظة العلمية للحضارات الاصطناعية الناشئة."*

[⬆ العودة إلى الأعلى](#-genesis-engine-محرّك-التكوين)

</div>
