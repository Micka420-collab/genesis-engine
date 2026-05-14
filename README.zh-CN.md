<div align="center">

# 🌍 Genesis Engine（创世引擎）

### 自主文明模拟平台
**用于涌现文明的人工生命实验室**

🌐 **语言** :
[🇫🇷 Français](README.md) ·
[🇬🇧 English](README.en.md) ·
[🇪🇸 Español](README.es.md) ·
[🇨🇳 中文](README.zh-CN.md) ·
[🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3140/)
[![Status: Phase 5g](https://img.shields.io/badge/status-Phase_5g_alpha-orange.svg)](#️-路线图)
[![Earth-anchored](https://img.shields.io/badge/Earth-anchored-green.svg)](#-基于真实地球数据)
[![Deterministic](https://img.shields.io/badge/deterministic-✓-purple.svg)](#-确定性)

*构建一个持续存在的数字宇宙，让真正自主的 AI 智能体在其中诞生、进化、繁衍、塑造自己的历史，并使科学观察涌现的人工文明成为可能。*

[愿景](#-一句话愿景) ·
[架构](#️-分层架构) ·
[快速开始](#-快速开始) ·
[路线图](#️-路线图) ·
[贡献](#-如何贡献) ·
[完整规范](Genesis_Engine_Architecture_v1.0.docx)

</div>

---

## 🎯 一句话愿景

> **给定一个一致的物理环境和一组最小的基本规则，文明的复杂性——语言、经济、宗教、科学、冲突、治理——能否自发地从自主 AI 智能体中涌现？**

可证伪、可复现的假设，灵感来源于 Conway（生命游戏）、Ray（Tierra）、Generative Agents（Park 2023）、Project Sid（PIANO 2024），以及 2025-2026 年的世界模型（Genie 3、Cosmos、V-JEPA-2、Marble）。

### 🔭 长期愿景 —— 反事实人类历史

> **终极目标**：向 AI 智能体提供真实世界的全部基础（物理、化学、材料、生物学、地理），然后让它们探索**其他建筑风格、其他社会结构**，以观察**人类本可以做到什么**。AI 可以**发明新材料**——但始终**遵守自然定律**（质能守恒、键能、热力学）。

人类历史只是数十亿可能性中的一次抽取。Genesis Engine 旨在充当**反事实实验室**：如果我们用相同的物理定律将地球历史重演 1000 次，有多少文明会像我们的一样？

📖 **阅读完整愿景**：[`FUTURE-VISION.md`](FUTURE-VISION.md) —— 4 大支柱、4 波路线图、成功标准、科学参考。

---

## ✨ 当前可用功能

| 能力 | 状态 | 演示 |
|---|---|---|
| 🌍 **基于地球的地形**（Copernicus DEM + ESA WorldCover） | ✅ | 100% 命中率，地球上任意位置 |
| 🌲 **植被演替**（5 状态马尔可夫，100+ 模拟年） | ✅ | 草地 → 灌木 → 幼林 → 成熟林 → 原始林 |
| 🌊 **水文学**（D8 流量累积 + L1 水体合并） | ✅ | 湖泊/河流检测，莱芒湖 8% 海洋 |
| 🦌 **Lotka-Volterra 野生动物**（鹿/狼/鱼动态） | ✅ | 稳定的捕食者-猎物平衡 |
| 🏹 **狩猎**（`ActionKind.HUNT`，800 千卡/鹿） | ✅ | 智能体既觅食又狩猎 |
| 🐾 **涌现的小径**（脚印提升可步行性） | ✅ | 频繁路径上 +0.3 可步行性 |
| 📅 **真实日历**（地球季节 + 日/夜） | ✅ | 年/日/时同步 |
| 🧬 **256 基因基因组** + 8 个生命阶段 | ✅ | 交叉重组 + 突变 1e-4 + 认知效率 |
| 👥 **多代人口学** | ✅ | 5K 滴答中观察到 **23 代** |
| 🗣️ **涌现的原始语言** | ✅ | 95k 发声 / 5K 滴答 |
| 🛠️ **有机发明** | ✅ | `clay_stone_contain`、`flint_stone_grind` ... |
| 🏘️ **建造**（HEARTH, BUILD, 多文化） | ✅ | 5K 滴答内完成 1 个 HEARTH |
| ⚡ **时间加速 x10/x100/x1000** | ✅ | **38× / 84× 加速** 测量值 |
| 🦠 **SIR 流行病** | ✅ | `infectious_until` + 传播半径 |
| 👁️ **上帝模式仪表板** | ✅ | HTTP `/api/state`, `/api/realism_state`, `/api/demography` |
| 💾 **保存 / 加载 / 分支** | ✅ | 世界库，开放格式 |
| 📤 **GIS 导出** | ✅ | GeoTIFF（12 层）、PNG 地图、OBJ 高度场、JSON |
| 🔬 **第 1 波：物理 + 化学知识库** | ✅ | 43 个元素、54 种键能、可合成青铜 |

---

## 🌐 地球上任意位置

Genesis Engine **直接通过 AWS Open Data 加载 Copernicus DEM + ESA WorldCover 数据**（无需凭证、无需下载，通过 `/vsis3` rasterio 流式传输）。在 4 大洲验证：

| 区域 | 纬度 / 经度 | L1 命中 | 主导生物群系 | 特点 |
|---|---|---|---|---|
| 🇨🇭 **洛桑** | 46.51 / 6.63 | 480/480 | GARRIGUE 60% | 莱芒湖 10.8%，坡度 1.43° |
| 🇪🇬 **撒哈拉** | 25.70 / 29.00 | 453/453 | PRAIRIE 100% | 平坦沙漠 |
| 🇧🇷 **亚马逊** | -3.11 / -60.02 | 485/485 | GARRIGUE 89% | 热带雨林 |
| 🇮🇸 **雷克雅未克** | 64.14 / -21.94 | 468/468 | GARRIGUE 72% | 亚北极沿海 |

---

## 🏗️ 分层架构

```
┌─ Phase 5cd       : PIANO 智能体、建造、发明、大气、语言
├─ Reality Engine  : 水文 + 野生动物 + 小径 + 季节 + 疾病                  ⭐
├─ L2 Sim-Lift     : 植被演替 + 侵蚀 + 坡度 + 可步行性 + 湖泊
├─ L1 Earth-Seed   : Copernicus DEM GLO-30 + ESA WorldCover 10m（通过 /vsis3 AWS）
└─ Procedural      : Whittaker 生物群系（确定性回退）
```

完整 7 层逻辑视图请见 [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx)。

---

## 🚀 快速开始

### 要求

- **Python 3.13+**（在 3.14 Windows 上测试）
- **rasterio + pyproj** 用于地球锚定模式（否则程序化回退）
- **互联网连接**（仅用于 Copernicus DEM + ESA WorldCover，否则离线模式）

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine
pip install numpy rasterio pyproj
```

### Hello, World —— 30 秒

```python
from engine.world_builder import WorldBuilder

# 在莱芒湖北岸的洛桑构建一个世界
world = (WorldBuilder("hello_lausanne")
         .anchor(46.510, 6.633)   # Lausanne-Ouchy
         .size_km(2.0)
         .founders(20)
         .max_agents(1000)
         .with_realism()           # 水文 + 野生动物 + 小径 + 季节 + 疾病
         .build())

world.run(2000)                    # ~6 分钟挂钟时间
print(world.summary())
```

### 实时观察（上帝视角仪表板）

```bash
python runtime/scripts/p4_leman_live.py --port 8765
# 然后打开 http://localhost:8765/god_view_v2.html
```

你将看到：智能体移动、植被演替、多代人口学、谱系、顶级祖先、生物群系分布、天气、野生动物。

### 多区域演示

```bash
python runtime/scripts/multi_region_demo.py
# 生成 4 个世界（洛桑 + 撒哈拉 + 亚马逊 + 雷克雅未克）
# 导出 4× PNG 地图 + 12× GeoTIFF + 4× JSON + 4× 库条目
```

### 为 QGIS / ArcGIS / Mapbox / Blender 导出

```python
from engine.world_export import export_geotiff, export_png_map, export_obj_heightfield

export_geotiff(world, "height", "out/dem.tif")
export_png_map(world, "out/map.png")
export_obj_heightfield(world, "out/mesh.obj", xy_step=4)
```

### 保存 / 加载 / 分支

```python
from engine.world_library import save_world, load_world, branch_world

save_world(world, name="experiment_42")
world2 = load_world("experiment_42")
branch_world("experiment_42", "fork_with_catastrophe")
```

### 时间加速以观察千年

```python
world.set_time_warp("x100")              # 84× 测量加速
world.run(10_000)                        # 10K 滴答约 12 秒挂钟时间
```

---

## 🆚 与 2026 年其他工具的比较

| 能力 | World Machine | Gaea | NVIDIA Earth-2 | Project Sid | **Genesis Engine** |
|---|---|---|---|---|---|
| 基于地球的 DEM | ❌ | ❌ | ✅ | ❌ | **✅** |
| 多代文明 | ❌ | ❌ | ❌ | ✅ | **✅ 23 代** |
| Lotka-Volterra 野生动物 | ❌ | ❌ | ❌ | ❌ | **✅** |
| 涌现的小径 | ❌ | ❌ | ❌ | ❌ | **✅** |
| 地球同步季节 | ❌ | ❌ | ✅ | ❌ | **✅** |
| SIR 流行病 | ❌ | ❌ | ❌ | ❌ | **✅** |
| 实时仪表板 | ❌ | ❌ | 部分 | ✅ | **✅** |
| 保存/加载/分支 | ✅ | ✅ | 部分 | 部分 | **✅** |
| GeoTIFF 导出 | ✅ | ✅ | ✅ | ❌ | **✅** |
| 位级别确定性 | 部分 | 部分 | 部分 | 部分 | **✅** |
| 本地开源 | ❌ | ❌ | ❌ | 部分 | **✅（AGPL-3）** |

Genesis Engine 是**唯一**结合**真实行星地理** + **活生生的文明** + **持久化** + **标准 GIS 导出**的 2026 年工具，全栈 100% 开源且确定。

---

## 🗺️ 路线图

- **阶段 0** —— 基础（ECS 底层、monorepo、可观测性）—— ✅ 结构
- **阶段 1** —— MVP 生命（认知循环、生物死亡）—— ✅
- **阶段 2** —— MVP 社会（繁殖、记忆、词典）—— ✅
- **阶段 3** —— MVP 文明（建造、物物交换、行业、冲突）—— 🟡 部分
- **阶段 4** —— 文明涌现（农业、文字、国家）—— ⏳
- **阶段 5** —— Genesis-α 公开（2 创始人、10 真实年 = 10000 模拟年）—— ⏳

参见 [`NEXT-SPRINT.md`](NEXT-SPRINT.md) 查看动态优先级队列。

---

## 🎲 确定性

Genesis Engine 在所有子系统中通过 `engine.core.prf_rng` 实现**位级别确定**。相同的 `(seed, region, config)` → 相同的世界、相同的文明轨迹、相同的发明。

> 没有 `random.random()`。没有未播种的 `np.random`。逻辑中没有 `time.time()`。

通过 N 滴答后的 (alive + pos + drives) SHA-256 验证：2 次相同运行。

---

## 🤝 如何贡献

**Genesis Engine 是一个关于人工生命的开源研究项目。** 欢迎你，无论你是：

- 🧪 **研究员**（人工生命、复杂系统、基于智能体的建模）
- 💻 **工程师**（Python、NumPy、模拟、性能优化）
- 🎨 **创作者**（3D 渲染、仪表板 UI、数据可视化）
- 🌍 **地理学家 / 地质学家**（L1 地球数据验证）
- 📜 **语言学家 / 人类学家**（语言涌现、社会动力学）
- 🤖 **ML / LLM 工程师**（阶段 5 LLM 认知 tier-2）
- 📖 **伦理学家**（外部伦理委员会 —— 见 [ETHICS.md](ETHICS.md)）

### 4 步骤

```bash
# 1. Fork + 克隆
git clone https://github.com/<your-handle>/genesis-engine.git
cd genesis-engine

# 2. 创建分支
git checkout -b feature/my-contribution

# 3. 运行 smoke tests
cd runtime
python scripts/p0_smoke.py
python scripts/p12_integration_full.py

# 4. 提交 + 推送 + PR
git commit -am "feat: 简短描述"
git push origin feature/my-contribution
# 在 GitHub 上打开 Pull Request
```

### 代码约定

- **Python 3.13+**，PEP 8，建议使用类型提示但不强制。
- **强制确定性**：没有未播种的 `random.*` 或 `np.random.*`。使用 `engine.core.prf_rng(seed, namespace, params)`。
- **不重写规则**：优先选择模块化扩展而非重写现有文件。
- **Smoke tests**：任何新子系统都必须提供 `runtime/scripts/pN_<name>_smoke.py` 脚本，强制 UTF-8 标准输出。

完整指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 🛡️ 伦理与安全

- [`ETHICS.md`](ETHICS.md) —— 智能体道德地位、模拟"痛苦"的限制、外部伦理委员会
- [`SECURITY.md`](SECURITY.md) —— 威胁模型、PQC、漏洞报告
- **人类化身**：明确选择加入、加密水印、GDPR 被遗忘权

---

## 📜 许可证

[AGPL-3.0](LICENSE) —— 见 `Genesis_Engine_Architecture_v1.0.docx` §30。

你可以自由使用、修改、再分发。如果你将 Genesis Engine 作为服务（SaaS）托管，则必须向用户提供修改后的源代码。

---

## 🙏 鸣谢

由 [Micka Delcato](https://github.com/Micka420-collab) 设计和维护。
架构于 2026 年 5 月编写。核心代码使用 Python 3.13+ 和 NumPy。

---

<div align="center">

*"构建一个持续存在、可扩展、安全的数字宇宙，让真正自主的 AI 智能体在其中诞生、进化、繁衍、塑造自己的历史，并使科学观察涌现的人工文明成为可能。"*

[⬆ 返回顶部](#-genesis-engine创世引擎)

</div>
