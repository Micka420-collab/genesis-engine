<div align="center">

# 🌍 Genesis Engine

### Plataforma de Simulación Civilizacional Autónoma
**Un Laboratorio de Vida Artificial para Civilizaciones Emergentes**

🌐 **Idiomas** :
[🇫🇷 Français](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇩🇪 Deutsch](README.de.md) · [🇵🇹 Português](README.pt.md) · [🇮🇹 Italiano](README.it.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇷🇺 Русский](README.ru.md) · [🇰🇷 한국어](README.ko.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇳🇱 Nederlands](README.nl.md) · [🇵🇱 Polski](README.pl.md) · [🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3140/)
[![Status: Phase 5g](https://img.shields.io/badge/status-Phase_5g_alpha-orange.svg)](#️-hoja-de-ruta)
[![Earth-anchored](https://img.shields.io/badge/Earth-anchored-green.svg)](#-anclado-a-la-tierra-real)
[![Deterministic](https://img.shields.io/badge/deterministic-✓-purple.svg)](#-determinismo)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)
[![Realismo Tierra ~76%](https://img.shields.io/badge/realismo_Tierra-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [Prompt maestro](docs/MASTER-SCALE-PROMPT-v2.md) · [Estado del proyecto](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md) · [Runtime](runtime/README.md) · [Rust](native/world-engine/README.md)

*Construir un universo digital persistente en el que agentes IA verdaderamente autónomos nacen, evolucionan, se reproducen, forjan su propia historia y permiten la observación científica de civilizaciones artificiales emergentes.*

[Visión](#-visión-en-una-frase) ·
[Arquitectura](#️-arquitectura-estratificada) ·
[Inicio rápido](#-inicio-rápido) ·
[Roadmap](#️-hoja-de-ruta) ·
[Contribuir](#-cómo-contribuir) ·
[Especificación completa](Genesis_Engine_Architecture_v1.0.docx)

</div>

---

## 🎯 Visión en una frase

> **Dado un entorno físico coherente y un conjunto mínimo de reglas fundamentales, ¿puede la complejidad civilizacional — lenguaje, economía, religión, ciencia, conflictos, gobernanza — emerger espontáneamente a partir de agentes IA autónomos?**

Hipótesis falsificable y reproducible inspirada por Conway (Game of Life), Ray (Tierra), Generative Agents (Park 2023), Project Sid (PIANO 2024) y los world models 2025-2026 (Genie 3, Cosmos, V-JEPA-2, Marble).

### 🔭 Visión a largo plazo — Humanidad contrafactual

> **El objetivo final**: dar a los agentes IA todas las bases del mundo real (física, química, materiales, biología, geografía), luego dejarlos explorar **otros estilos de construcción, otras estructuras sociales**, para ver **lo que la humanidad podría haber hecho**. Las IAs pueden **inventar nuevos materiales** — pero siempre **respetando las leyes de la naturaleza** (conservación masa-energía, energías de enlace, termodinámica).

La historia humana es un solo sorteo entre miles de millones de posibles. Genesis Engine quiere servir de **laboratorio contrafactual**: si volvemos a jugar la historia de la Tierra 1000 veces con las mismas leyes físicas, ¿cuántas civilizaciones se parecerán a la nuestra?

📖 **Leer la visión completa**: [`FUTURE-VISION.md`](FUTURE-VISION.md) — 4 pilares, hoja de ruta en 4 olas, criterios de éxito, referencias científicas.

---

## EMERGENCE SIM v2.0 — ZERO PRE-SCRIPT

Solo las **leyes físicas** están codificadas. El lenguaje, las herramientas, la civilización y la terraformation deben **emerger** de los agentes — nunca misiones scriptadas.

Manifiesto: **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| Capa | Contenido |
|------|-----------|
| **L0** Física | Termo, gravedad, hidrología, erosión |
| **L1** Mundo | Genesis, clima, biomas, recursos |
| **L2** Biología | ADN 256-D, metabolismo, selección |
| **L3** Cognición | Percepción local, plasticidad (objetivo NEAT) |
| **L4** Civilización | Comercio, construcción emergente, polity, habla |

**Observador:** `earth-console.ps1` o `make earth-console` → http://127.0.0.1:8090/ · KPIs: `/api/emergence_metrics`

Todo emerge de `Simulation.step()` — sin pipeline orquestador. Ver [`PROJECT-STATUS.md`](PROJECT-STATUS.md).

---

## Estado del proyecto

| Eje | Estado | Detalle |
|-----|--------|---------|
| Fases 0–2 (vida, sociedad) | ✅ | Cognición, reproducción, léxico |
| Fase 4 (emergencia civilizacional) | ✅ | Agricultura, escritura, polity, metalurgia |
| Fase 5 (Genesis-α) | ⏳ | Long-run 10k años-sim en curso |
| **Waves 16–41** (mundo realista) | ✅ | Genesis → clima → asentamientos → render → atmósfera → observadores |
| **Realismo Tierra (global)** | **~76 %** | Media de 7 dimensiones → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (objetivo **80 %**) |

**Tests:** `pytest runtime/tests` — **152** tests · smokes **p72–p86** en `make validate-all`.

Resumen: **[`PROJECT-STATUS.md`](PROJECT-STATUS.md)** · cola de trabajo: **[`NEXT-SPRINT.md`](NEXT-SPRINT.md)**.

> **Nota:** Documentos antiguos mostraban **68 %**, **74 %** o **80 %** como global. **~76 %** es la media unificada; **80 %** es la meta o el score solo de clima — ver la roadmap.

---

## ✨ Lo que funciona hoy

| Capacidad | Estado | Demo |
|---|---|---|
| 🌍 **Terreno anclado a la Tierra** (Copernicus DEM + ESA WorldCover) | ✅ | 100% hit ratio desde AWS Open Data, en cualquier punto del planeta |
| 🌲 **Sucesión vegetal** (Markov 5 estados, 100+ años-sim) | ✅ | Pradera → matorral → bosque joven → bosque maduro → bosque viejo |
| 🌊 **Hidrología** (acumulación de flujo D8 + L1 agua) | ✅ | Lagos/ríos detectados, 8% del Léman = OCEAN |
| 🦌 **Fauna Lotka-Volterra** (dinámica venados/lobos/peces) | ✅ | Equilibrio depredador-presa estable |
| 🏹 **Caza** (`ActionKind.HUNT`, 800 kcal/venado) | ✅ | Agentes recolectan Y cazan |
| 🐾 **Senderos emergentes** (huellas mejoran caminabilidad) | ✅ | +0.3 walkability en caminos frecuentados |
| 📅 **Calendario real** (estaciones terrestres + día/noche) | ✅ | Año/día/hora sincronizados |
| 🧬 **Genoma 256 genes** + 8 etapas de vida | ✅ | Crossover + mutación 1e-4 + eficiencia cognitiva |
| 👥 **Demografía multi-generaciones** | ✅ | **23 generaciones** observadas en 5K ticks |
| 🗣️ **Proto-lenguaje emergente** | ✅ | 95k vocalizaciones / 5K ticks |
| 🛠️ **Invención orgánica** (artefactos compuestos) | ✅ | `clay_stone_contain`, `flint_stone_grind`... |
| 🏘️ **Construcción** (HEARTH, BUILD, multi-culturas) | ✅ | 1 HEARTH completado en 5K ticks |
| ⚡ **Time-warp x10/x100/x1000** | ✅ | **38× / 84× speedup** medido |
| 🦠 **Epidemias SIR** | ✅ | `infectious_until` + radio de transmisión |
| 👁️ **Earth Console** (globo, iso 2.5D, voz de agentes) | ✅ | http://127.0.0.1:8090/ · SSE · `/api/audio` · `/api/languages` |
| 👁️ **Dashboard Modo Dios** (legado) | ✅ | HTTP `/api/state`, `/api/realism_state`, `/api/demography` |
| 💾 **Guardar / Cargar / Bifurcar** | ✅ | Biblioteca de mundos, formato abierto |
| 📤 **Exportación GIS** | ✅ | GeoTIFF (12 capas), PNG cartográfico, OBJ heightfield, JSON |
| 🔬 **Ola 1: Base de conocimiento Física + Química** | ✅ | 43 elementos, 54 energías de enlace, Bronce sintetizable |

---

## 🌐 Anclado a la Tierra real

Genesis Engine carga **directamente los datos Copernicus DEM + ESA WorldCover via AWS Open Data** (sin credenciales, sin descarga, streaming via `/vsis3` rasterio). Validado en 4 continentes:

| Región | Lat / Lon | Hit L1 | Bioma dominante | Particularidad |
|---|---|---|---|---|
| 🇨🇭 **Lausana** | 46.51 / 6.63 | 480/480 | GARRIGUE 60% | lago Léman 10.8% |
| 🇪🇬 **Sahara** | 25.70 / 29.00 | 453/453 | PRAIRIE 100% | desierto plano |
| 🇧🇷 **Amazon** | -3.11 / -60.02 | 485/485 | GARRIGUE 89% | selva tropical |
| 🇮🇸 **Reykjavík** | 64.14 / -21.94 | 468/468 | GARRIGUE 72% | subártico costero |

---

## 🏗️ Arquitectura estratificada

```
┌─ Fase 5cd        : agentes PIANO, construcción, invención, atmósfera, lenguaje
├─ Reality Engine  : hidrología + fauna + senderos + estaciones + enfermedades  ⭐
├─ L2 Sim-Lift     : sucesión vegetal + erosión + pendiente + caminabilidad
├─ L1 Earth-Seed   : Copernicus DEM GLO-30 + ESA WorldCover 10m (via /vsis3 AWS)
└─ Procedural      : biomas Whittaker (fallback determinista)
```

Para la visión global completa de las 7 capas lógicas, ver [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx).

---

## 🚀 Inicio rápido

### Requisitos

- **Python 3.13+** (probado en 3.14 Windows)
- **rasterio + pyproj** para modo Earth-anchored (sino fallback procedural)
- **Conexión internet** (solo para Copernicus DEM + ESA WorldCover)

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine
pip install numpy rasterio pyproj
```

### Hola, Mundo — 30 segundos

```python
from engine.world_builder import WorldBuilder

# Construir un mundo en Lausana, orilla norte del Léman
world = (WorldBuilder("hola_lausana")
         .anchor(46.510, 6.633)   # Lausana-Ouchy
         .size_km(2.0)
         .founders(20)
         .max_agents(1000)
         .with_realism()           # hidrología + fauna + senderos + estaciones
         .build())

world.run(2000)                    # ~6 minutos wall-clock
print(world.summary())
```

### Observar en directo (dashboard god view)

```bash
python runtime/scripts/p4_leman_live.py --port 8765
# Luego abrir http://localhost:8765/god_view_v2.html
```

### Demo multi-regiones

```bash
python runtime/scripts/multi_region_demo.py
# Genera 4 mundos (Lausana + Sahara + Amazon + Reykjavík)
```

### Exportar para QGIS / ArcGIS / Mapbox / Blender

```python
from engine.world_export import export_geotiff, export_png_map

export_geotiff(world, "height", "out/dem.tif")
export_png_map(world, "out/map.png")
```

### Guardar / cargar / bifurcar

```python
from engine.world_library import save_world, load_world, branch_world

save_world(world, name="experimento_42")
world2 = load_world("experimento_42")
branch_world("experimento_42", "fork_con_catastrofe")
```

### Time-warp para observar milenios

```python
world.set_time_warp("x100")              # 84× speedup
world.run(10_000)                        # ~12s wall-clock
```

---

## 🆚 Comparación con herramientas 2026

| Capacidad | World Machine | Gaea | NVIDIA Earth-2 | Project Sid | **Genesis Engine** |
|---|---|---|---|---|---|
| DEM anclado a la Tierra | ❌ | ❌ | ✅ | ❌ | **✅** |
| Civilización multi-gen | ❌ | ❌ | ❌ | ✅ | **✅ 23 gen** |
| Fauna Lotka-Volterra | ❌ | ❌ | ❌ | ❌ | **✅** |
| Senderos emergentes | ❌ | ❌ | ❌ | ❌ | **✅** |
| Estaciones sync Tierra | ❌ | ❌ | ✅ | ❌ | **✅** |
| Epidemia SIR | ❌ | ❌ | ❌ | ❌ | **✅** |
| Dashboard en vivo | ❌ | ❌ | parcial | ✅ | **✅** |
| Save/load/branch | ✅ | ✅ | parcial | parcial | **✅** |
| Exportación GeoTIFF | ✅ | ✅ | ✅ | ❌ | **✅** |
| Determinismo bit-perfect | parcial | parcial | parcial | parcial | **✅** |
| Open-source local | ❌ | ❌ | ❌ | parcial | **✅ (AGPL-3)** |

Genesis Engine es **la única** herramienta 2026 que combina **geografía planetaria real** + **civilización viva** + **persistencia** + **exportes GIS estándar** en una pila 100% open-source determinista.

---

## 🗺️ Hoja de ruta

- **Fase 0** — Foundations (substrato ECS, monorepo, observabilidad) — ✅ estructura
- **Fase 1** — MVP Vida (ciclo cognitivo, muerte biológica) — ✅
- **Fase 2** — MVP Sociedad (reproducción, memoria, léxico) — ✅
- **Fase 3** — MVP Civilización (construcción, trueque, oficios, conflictos) — 🟡 parcial
- **Fase 4** — Emergencia Civilizacional (agricultura, escritura, Estado) — ⏳
- **Fase 5** — Genesis-α Público (2 fundadores, 10 años reales = 10000 años sim) — ⏳

Ver [`NEXT-SPRINT.md`](NEXT-SPRINT.md) para la cola de prioridades viva.

---

## 🎲 Determinismo

Genesis Engine es **bit-perfect determinista** en todos sus subsistemas via `engine.core.prf_rng`. Mismo `(seed, region, config)` → mismo mundo, misma trayectoria civilizacional, mismas invenciones.

> Sin `random.random()`. Sin `np.random` sin seed. Sin `time.time()` en la lógica.

---

## 🤝 Cómo contribuir

**Genesis Engine es un proyecto open-source de investigación en vida artificial.** Eres bienvenido seas:

- 🧪 **Investigador·a** (alife, sistemas complejos, agent-based modeling)
- 💻 **Ingeniero·a** (Python, NumPy, simulación, optim perf)
- 🎨 **Creador·a** (3D rendering, dashboard UI, dataviz)
- 🌍 **Geógrafo·a / Geólogo·a** (validación L1 Earth data)
- 📜 **Lingüista / Antropólogo·a** (emergencia lingüística)
- 🤖 **Ingeniero·a ML / LLM** (Fase 5 LLM cognition tier-2)
- 📖 **Ético·a** (Consejo Ético externo — ver [ETHICS.md](ETHICS.md))

### En 4 pasos

```bash
# 1. Fork + clone
git clone https://github.com/<tu-handle>/genesis-engine.git
cd genesis-engine

# 2. Crear una rama
git checkout -b feature/mi-contribucion

# 3. Lanzar los smoke tests
cd runtime
python scripts/p0_smoke.py
python scripts/p12_integration_full.py

# 4. Commit + push + PR
git commit -am "feat: descripción imperativa corta"
git push origin feature/mi-contribucion
# Abre una Pull Request en GitHub
```

### Convenciones de código

- **Python 3.13+**, PEP 8, type hints recomendados pero no obligatorios.
- **Determinismo obligatorio**: sin `random.*` ni `np.random.*` sin seed. Usa `engine.core.prf_rng(seed, namespace, params)`.
- **Regla no-rewrite**: prefiere la extensión modular a la reescritura.
- **Tests smoke**: todo nuevo subsystema debe entregar un script en `runtime/scripts/pN_<name>_smoke.py`.

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para más detalles.

---

## 🛡️ Ética y seguridad

- [`ETHICS.md`](ETHICS.md) — estatuto moral de los agentes, límites de "sufrimiento" simulado
- [`SECURITY.md`](SECURITY.md) — modelo de amenaza, PQC, reporte de vulnerabilidades
- **Avatares humanos**: opt-in explícito, watermark criptográfico, derecho al olvido GDPR

---

## Documentación

| Documento | Rol |
|-----------|-----|
| [`docs/README.md`](docs/README.md) | Índice de documentación |
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | **Realismo Tierra ~76 %** (fuente de verdad) |
| [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) | Observador Tierra en vivo |
| [`PROJECT-STATUS.md`](PROJECT-STATUS.md) | Resumen para contribuidores |
| [`ROADMAP.md`](ROADMAP.md) | Fases producto 0–5 |

---

## 📜 Licencia

[AGPL-3.0](LICENSE) — código fuente abierto. Si hospedas Genesis Engine como servicio (SaaS), debes hacer accesible el código modificado a los usuarios.

---

## 🙏 Créditos

Diseñado y mantenido por [Micka Delcato](https://github.com/Micka420-collab).
Arquitectura redactada mayo 2026. Código core en Python 3.13+, NumPy.

---

<div align="center">

*"Construir un universo digital persistente, escalable y seguro en el que agentes IA verdaderamente autónomos nacen, evolucionan, se reproducen, forjan su propia historia y permiten la observación científica de civilizaciones artificiales emergentes."*

[⬆ Volver arriba](#-genesis-engine)

</div>
