# METOC-Lagrangian Platform
## Scrum Master Multi-Agent Build Plan v1.0
**Date:** May 2026 | **Classification:** NATO UNCLASSIFIED // OPEN SOURCE
**Branch:** `claude/metoc-lagrangian-platform-XYLxL`

---

## 1. Repository Structure (Target State)

```
metoc-lagrangian/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                   # pytest + schema validation
│   │   ├── air-gap-test.yml         # Docker offline integration test
│   │   └── docker-publish.yml       # Container registry push
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.lock            # Pinned pip freeze (air-gap ready)
├── data/
│   ├── input/                       # Air-gap staging folder (NetCDF/GRIB2)
│   ├── output/                      # STANAG exports, GeoJSON corridors
│   └── samples/                     # Small test fixtures (CI)
├── src/
│   ├── ingestion/
│   │   ├── aifs_client.py           # ECMWF AIFS GRIB2 pull
│   │   ├── graphcast_client.py      # Google GraphCast/GenCast NetCDF pull
│   │   ├── cmems_client.py          # Copernicus Marine API client
│   │   ├── local_watcher.py         # Air-gap folder listener (asyncio)
│   │   └── grid_harmonizer.py       # Xarray resampling + mesh unification
│   ├── lagrangian/
│   │   ├── buoy_model.py            # OpenDrift subclass + leeway config
│   │   ├── geostrophic.py           # SSH-gradient geostrophic corrections
│   │   ├── monte_carlo.py           # 100-particle Gaussian noise ensemble
│   │   └── drift_corridor.py        # Convex hull polygon builder (Shapely)
│   ├── wesf/
│   │   ├── ramp_forecaster.py       # Wind cut-out + solar drop detector
│   │   ├── cvi_engine.py            # Cyber Vulnerability Index matrix
│   │   └── price_model.py           # Deep learning EPEX SPOT forecaster
│   ├── nato/
│   │   ├── metgm_compiler.py        # STANAG 6015 / AMETOCP-4 serializer
│   │   ├── nodef1_exporter.py       # STANAG 1317 binary formatter
│   │   └── app6_symbology.py        # APP-6 / MIL-STD-2525 GeoJSON builder
│   ├── api/
│   │   ├── main.py                  # FastAPI REST entrypoint
│   │   ├── routers/
│   │   │   ├── drift.py
│   │   │   ├── wesf.py
│   │   │   └── nato.py
│   │   └── schemas.py               # Pydantic I/O models
│   └── core/
│       ├── config.py                # Pydantic Settings (env-var driven)
│       ├── logging.py               # Structured JSON logging
│       └── pipeline.py              # Orchestration entry point
├── tests/
│   ├── unit/
│   │   ├── test_grid_harmonizer.py
│   │   ├── test_monte_carlo.py
│   │   ├── test_cvi_engine.py
│   │   ├── test_metgm_compiler.py
│   │   └── test_nodef1_exporter.py
│   ├── integration/
│   │   ├── test_pipeline_local.py   # Full run on sample data
│   │   └── test_air_gap.py          # No-network isolation test
│   └── conftest.py
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_drift_visualization.ipynb
│   └── 03_wesf_analysis.ipynb
├── docs/
│   ├── architecture.md
│   ├── api_reference.md
│   ├── air_gap_deployment.md
│   └── stanag_compliance.md
├── CLAUDE.md                        # Agent onboarding context
├── pyproject.toml
└── README.md
```

---

## 2. Open-Source Technology Stack

| Layer | Library / Tool | GitHub / Source | Version Pin |
|---|---|---|---|
| Lagrangian Drift Core | **OpenDrift** | `github.com/OpenDrift/opendrift` | `≥1.11` |
| Gridded Data I/O | **Xarray** + **netCDF4** | `pydata/xarray` | `≥2024.6` |
| GRIB2 Decoding | **cfgrib** + **eccodes** | `ecmwf/cfgrib` | `≥0.9.12` |
| CMEMS API Client | **copernicusmarine** | `mercator-ocean/copernicus-marine-toolbox` | `≥1.3` |
| AI Model Runner | **ai-models** (ECMWF) | `ecmwf-lab/ai-models` | `≥0.7` |
| Geometry / Corridors | **Shapely** | `shapely/shapely` | `≥2.0` |
| Geospatial Transform | **pyproj** + **GDAL** | `OSGeo/GDAL` | `≥3.9` |
| Deep Learning (Price) | **PyTorch** + **Darts** | `unit8co/darts` | `≥0.30` |
| ML Utilities | **scikit-learn** | `scikit-learn/scikit-learn` | `≥1.5` |
| REST API | **FastAPI** + **Uvicorn** | `tiangolo/fastapi` | `≥0.115` |
| Data Validation | **Pydantic v2** | `pydantic/pydantic` | `≥2.7` |
| Map Server (OGC) | **GeoServer** (Docker) | `geoserver/docker` | `2.25` |
| STANAG Binary I/O | **struct** (stdlib) + **lxml** | Python stdlib | — |
| Async HTTP | **httpx** + **asyncio** | `encode/httpx` | `≥0.27` |
| Containerization | **Docker** + **Compose** | `docker/compose` | `≥2.27` |
| Testing | **pytest** + **pytest-asyncio** | `pytest-dev/pytest` | `≥8.2` |
| Coverage | **coverage.py** | `nedbat/coveragepy` | `≥7.5` |
| Structured Logging | **structlog** | `hynek/structlog` | `≥24.1` |
| Config Management | **python-dotenv** + Pydantic Settings | — | — |
| Async Task Queue | **Celery** + **Redis** (optional) | `celery/celery` | `≥5.4` |

---

## 3. Multi-Agent Team Architecture

The Scrum Master deploys **7 specialized AI agents** in parallel across overlapping sprints. Each agent owns a vertical slice of the codebase and communicates through shared interfaces defined in `src/api/schemas.py`.

```
┌─────────────────────────────────────────────────────────────┐
│                    SCRUM MASTER (Human)                     │
│       Sprint Planning · Backlog Grooming · DoD Review       │
└────────┬──────────┬──────────┬──────────┬──────────┬────────┘
         │          │          │          │          │
         ▼          ▼          ▼          ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │ AGENT α │ │ AGENT β │ │ AGENT γ │ │ AGENT δ │ │ AGENT ε │
   │ Ingest  │ │ Physics │ │  WESF   │ │  NATO   │ │  MLOps  │
   └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
                                                         │
                                    ┌────────────────────┘
                                    ▼
                              ┌─────────┐ ┌─────────┐
                              │ AGENT ζ │ │ AGENT η │
                              │   QA    │ │  Viz/UI │
                              └─────────┘ └─────────┘
```

### Agent Charters

#### 🔵 Agent Alpha — Data Ingestion Specialist
**Prompt Persona:** *"You are a Senior Geospatial Data Engineer specializing in NWP and ocean data pipelines."*
- **Owns:** `src/ingestion/`, `data/input/`, `docker/` partial
- **Mission:** Build all data acquisition clients + the grid harmonizer
- **Key Interfaces to Produce:**
  - `IngestResult` Pydantic model (standardized xarray Dataset wrapper)
  - Air-gap watcher async loop publishing to shared queue

#### 🟢 Agent Beta — Lagrangian Physics Engine
**Prompt Persona:** *"You are a Physical Oceanographer and Scientific Python developer with deep knowledge of OpenDrift."*
- **Owns:** `src/lagrangian/`
- **Mission:** Subclass OpenDrift, build Monte Carlo ensemble, compute drift corridors
- **Key Interfaces to Produce:**
  - `DriftCorridorResult` (GeoJSON FeatureCollection + particle tracks)
  - Deterministic seed support for post-mission audit reproducibility

#### 🟡 Agent Gamma — WESF Analysis Engine
**Prompt Persona:** *"You are a quantitative analyst specializing in energy markets, renewable generation physics, and operational technology cybersecurity."*
- **Owns:** `src/wesf/`
- **Mission:** Build ramp forecaster, CVI matrix, and deep learning price model
- **Key Interfaces to Produce:**
  - `RampAlertPayload` (turbine cut-out zones + solar irradiance drops)
  - `CVIAlert` (risk score + attack surface window + SIEM JSON)
  - `PriceForecast` (EPEX SPOT time-series + negative pricing flags)

#### 🔴 Agent Delta — NATO Standards Engineer
**Prompt Persona:** *"You are a military interoperability engineer specializing in NATO STANAG data standards and military symbology."*
- **Owns:** `src/nato/`, `docs/stanag_compliance.md`
- **Mission:** Implement METGM, NODEF-1 binary serializers, and APP-6 GeoJSON
- **Key Interfaces to Produce:**
  - METGM XML + binary byte stream serializer (STANAG 6015)
  - NODEF-1 struct-packed binary exporter (STANAG 1317)
  - APP-6 symbol URI mapper for drift corridors and energy hazard boundaries

#### 🟣 Agent Epsilon — MLOps & DevOps Engineer
**Prompt Persona:** *"You are a Senior MLOps engineer specializing in air-gapped containerized deployment and Python dependency management."*
- **Owns:** `docker/`, `.github/workflows/`, `pyproject.toml`, `src/core/`
- **Mission:** Build Docker multi-stage image, lock all dependencies, CI/CD pipelines, air-gap validation test
- **Key Deliverables:**
  - `Dockerfile` with multi-stage build (builder + slim runtime)
  - `requirements.lock` — fully resolved offline-installable package set
  - GitHub Actions CI: lint → test → schema-validate → air-gap-simulate

#### ⚪ Agent Zeta — QA & Test Engineer
**Prompt Persona:** *"You are a Senior Test Engineer specializing in scientific computing validation and military standards compliance testing."*
- **Owns:** `tests/`
- **Mission:** Achieve ≥85% test coverage, write integration tests, schema validators
- **Key Deliverables:**
  - Unit tests for all mathematical transforms (grid harmonizer, Monte Carlo, CVI)
  - NATO schema validation test suite (METGM XML parser check, NODEF-1 struct unpack)
  - Air-gap integration test (network-disabled Docker run with pre-staged files)

#### 🟠 Agent Eta — Frontend & Visualization Engineer
**Prompt Persona:** *"You are a full-stack engineer specializing in geospatial web visualization using Leaflet.js and military map overlays."*
- **Owns:** `src/api/`, `notebooks/`, static UI assets
- **Mission:** FastAPI REST endpoints, GeoServer OGC config, interactive Jupyter notebooks
- **Key Deliverables:**
  - `/api/v1/drift/{run_id}` → GeoJSON drift corridor endpoint
  - `/api/v1/wesf/{run_id}` → WESF alert payloads
  - Leaflet.js dashboard with APP-6 icon overlays
  - Three Jupyter notebooks for operator walkthrough

---

## 4. Sprint Roadmap (6 × 2-Week Sprints)

### ──── SPRINT 1 (Weeks 1-2): Foundation & Ingestion Scaffolding ────

**Goal:** Repository skeleton running in CI; CMEMS and AIFS clients returning validated xarray Datasets.

| Story | Agent | Points | Acceptance Criteria |
|---|---|---|---|
| S1-01: Repo init + CLAUDE.md + pyproject.toml | ε | 3 | `pip install -e .` succeeds; CI runs |
| S1-02: Docker multi-stage Dockerfile skeleton | ε | 5 | `docker build` succeeds; `pytest` runs inside container |
| S1-03: ECMWF AIFS GRIB2 async client | α | 8 | Returns `xr.Dataset` with `u10`, `v10`, `msl` variables |
| S1-04: Google GraphCast NetCDF client | α | 5 | Returns same schema as AIFS client (`IngestResult`) |
| S1-05: CMEMS surface current + SSH + Stokes client | α | 8 | Returns `uo`, `vo`, `zos`, `vsdx`, `vsdy` variables |
| S1-06: Air-gap local folder watcher (asyncio) | α | 5 | Picks up `.nc`/`.grib2` files and emits `IngestResult` |
| S1-07: `IngestResult` Pydantic schema | α/ε | 3 | Shared contract; all agents import from `schemas.py` |
| S1-08: Pydantic Settings + structured logging | ε | 3 | `LOG_LEVEL`, `SEED`, `AIR_GAP_MODE` env vars work |

**Sprint 1 Definition of Done:**
- [ ] `pytest tests/unit/` passes in GitHub Actions
- [ ] `docker build` succeeds and `pytest` runs inside container
- [ ] All 3 data sources return validated `IngestResult` objects against sample fixtures

---

### ──── SPRINT 2 (Weeks 3-4): Grid Harmonization & Data Validation ────

**Goal:** Mixed-resolution grids (0.25° atmo vs. 1/12° ocean) unified into one localized mesh. Air-gap watcher tested end-to-end.

| Story | Agent | Points | Acceptance Criteria |
|---|---|---|---|
| S2-01: Xarray bilinear resampling engine | α | 8 | Atmospheric 0.25° → ocean 1/12° interpolation < 2% error on test field |
| S2-02: Unified spatial mesh validator | α | 5 | Raises `GridMismatchError` with clear message on bad inputs |
| S2-03: Sample NetCDF/GRIB2 test fixtures (small bounding box) | ζ | 5 | <10 MB fixtures committed to `data/samples/` |
| S2-04: Unit tests for grid harmonizer | ζ | 8 | ≥90% coverage on `grid_harmonizer.py` |
| S2-05: Air-gap watcher integration test | ζ | 5 | Test drops file into `data/input/`, asserts `IngestResult` emitted |
| S2-06: CLAUDE.md agent onboarding guide | ε | 3 | Describes repo layout, env vars, how to run tests |
| S2-07: `requirements.lock` generation script | ε | 3 | `pip-compile` + offline wheel cache strategy documented |

**Sprint 2 DoD:**
- [ ] `test_grid_harmonizer.py` passes at ≥90% coverage
- [ ] Air-gap watcher integration test passes with network mocked off
- [ ] `requirements.lock` committed; Docker image builds offline

---

### ──── SPRINT 3 (Weeks 5-6): Lagrangian Drift Core ────

**Goal:** 100-particle Monte Carlo drift ensemble producing a valid 24-hour probabilistic corridor polygon.

| Story | Agent | Points | Acceptance Criteria |
|---|---|---|---|
| S3-01: OpenDrift `BuoyLeewayModel` subclass | β | 13 | Configurable leeway (1–5%), cross-section profile, wind/current forcing |
| S3-02: SSH gradient geostrophic correction | β | 8 | `geostrophic.py` returns corrected current vectors vs. raw SSH field |
| S3-03: 100-particle Gaussian noise ensemble | β | 8 | ±5 cm/s current noise, ±1.5 m/s wind noise; reproducible with fixed seed |
| S3-04: Convex hull corridor polygon builder | β | 5 | `Shapely.convex_hull` on 24-hr particle positions → GeoJSON `Polygon` |
| S3-05: `DriftCorridorResult` Pydantic schema | β/ε | 3 | Includes particle tracks array + corridor polygon + metadata |
| S3-06: Deterministic seed unit test | ζ | 5 | Two runs with same seed → byte-identical `DriftCorridorResult` |
| S3-07: Monte Carlo unit tests | ζ | 8 | ≥85% coverage; validates noise distribution, hull calculation |
| S3-08: Performance benchmark | ζ | 3 | 100-particle 24-hr run < 60 seconds on CI runner |

**Sprint 3 DoD:**
- [ ] `test_monte_carlo.py` passes at ≥85% coverage
- [ ] Deterministic reproducibility test passes
- [ ] Benchmark <60s on GitHub Actions runner (proxy for <3 min total system NFR)

---

### ──── SPRINT 4 (Weeks 7-8): WESF Analysis Module ────

**Goal:** Ramp forecaster, CVI matrix, and deep learning price model operational with validated alert outputs.

| Story | Agent | Points | Acceptance Criteria |
|---|---|---|---|
| S4-01: Wind turbine cut-out zone detector | γ | 8 | Flags locations where `wind_speed > 25 m/s` + safety threshold ramp |
| S4-02: Solar irradiance drop forecaster | γ | 8 | Maps cloud fraction + aerosol optical depth to GHI loss fraction |
| S4-03: `RampAlertPayload` schema + SIEM JSON | γ | 5 | Alert includes asset ID, GPS, severity, time window |
| S4-04: Cyber Vulnerability Index (CVI) engine | γ | 13 | Scores inverter risk 0–100 from weather severity × asset exposure heuristics |
| S4-05: `CVIAlert` schema + SIEM JSON formatter | γ | 5 | JSON output matches pre-agreed SIEM ingestion format |
| S4-06: EPEX SPOT data loader + feature engineering | γ | 5 | Loads historical CSV; engineers lag features, weather features |
| S4-07: Deep learning price forecaster (Darts NBEATS) | γ | 13 | MAE < 5 €/MWh on held-out validation set; negative pricing flags |
| S4-08: WESF unit tests | ζ | 8 | ≥85% coverage on `ramp_forecaster.py`, `cvi_engine.py`, `price_model.py` |

**Sprint 4 DoD:**
- [ ] All WESF unit tests pass at ≥85% coverage
- [ ] CVI scores validated against 3 synthetic weather scenarios
- [ ] Price model MAE documented in `docs/` with test data provenance

---

### ──── SPRINT 5 (Weeks 9-10): NATO Interoperability Layer ────

**Goal:** METGM and NODEF-1 files passing schema validation; APP-6 symbology rendering on GeoServer.

| Story | Agent | Points | Acceptance Criteria |
|---|---|---|---|
| S5-01: STANAG 6015 METGM XML builder | δ | 13 | XML validates against METGM XSD schema; contains grid + time metadata |
| S5-02: STANAG 6015 METGM binary serializer | δ | 8 | Byte-packed output parseable by reference decoder |
| S5-03: STANAG 1317 NODEF-1 binary exporter | δ | 13 | `struct.pack` layout matches NODEF-1 spec; round-trip test passes |
| S5-04: APP-6 GeoJSON symbology builder | δ | 8 | Drift corridors + WESF hazard boundaries rendered with correct SIDC codes |
| S5-05: METGM schema validation unit test | ζ | 5 | `lxml` validates exported XML; test must not require network |
| S5-06: NODEF-1 round-trip unit test | ζ | 5 | `pack → unpack` byte equality; float precision within 1e-6 |
| S5-07: GeoServer Docker service + WMS config | η | 8 | OGC WMS endpoint serves APP-6 styled layers; visible in Leaflet test |
| S5-08: STANAG compliance documentation | δ | 3 | `docs/stanag_compliance.md` with field mapping tables |

**Sprint 5 DoD:**
- [ ] METGM XML passes XSD validation in CI
- [ ] NODEF-1 round-trip unit test passes
- [ ] GeoServer WMS endpoint verified against Leaflet.js client in notebook

---

### ──── SPRINT 6 (Weeks 11-12): Integration, Hardening & Release ────

**Goal:** Full pipeline under 3 minutes; air-gap isolation test green; Docker image published; documentation complete.

| Story | Agent | Points | Acceptance Criteria |
|---|---|---|---|
| S6-01: Pipeline orchestrator (`core/pipeline.py`) | ε | 8 | Single entrypoint: ingest → drift → WESF → NATO export; timed |
| S6-02: FastAPI REST endpoints (drift + WESF + NATO) | η | 8 | OpenAPI schema auto-generated; all endpoints return correct schemas |
| S6-03: Leaflet.js operator dashboard | η | 8 | Displays drift corridor, cut-out zones, CVI heatmap, price curve |
| S6-04: Full pipeline integration test (local data) | ζ | 8 | End-to-end run on sample data < 3 minutes; all outputs valid |
| S6-05: Air-gap isolation integration test | ζ | 8 | Docker run with `--network none` + pre-staged files; green CI |
| S6-06: 85% coverage enforcement in CI | ζ | 5 | `coverage.py` gate in `ci.yml`; PR blocked if < 85% |
| S6-07: Docker image final lockdown + `requirements.lock` | ε | 8 | Builds offline from wheel cache; `pip check` passes inside container |
| S6-08: GitHub Actions: docker-publish workflow | ε | 5 | Tags `:latest` and `:vX.Y.Z` on main merge |
| S6-09: Jupyter notebooks (3 operator walkthroughs) | η | 5 | Notebooks execute top-to-bottom with sample data |
| S6-10: Full documentation suite | all | 5 | `README`, `architecture.md`, `api_reference.md`, `air_gap_deployment.md` |

**Sprint 6 DoD (= Project Definition of Done):**
- [ ] End-to-end pipeline < 3 minutes on benchmark hardware
- [ ] Air-gap isolation test passes in CI (`--network none`)
- [ ] Test coverage ≥ 85% across all custom modules
- [ ] METGM XML + NODEF-1 pass schema validation in CI
- [ ] Docker image tagged and documented for offline distribution
- [ ] OpenAPI docs auto-generated and committed to `docs/`

---

## 5. Detailed Agent Prompting Strategy

The Scrum Master launches each agent using the following prompt pattern to maximize consistency and reduce hallucination:

```markdown
### AGENT [ALPHA/BETA/...] SYSTEM PROMPT TEMPLATE

You are a [ROLE] working on Project METOC-Lagrangian.
Read `CLAUDE.md` first for project context and conventions.

**Your scope:** You own `src/[module]/` and `tests/unit/test_[module].py`.
**Do NOT modify** files outside your scope without Scrum Master approval.

**Shared contracts you must import (never redefine):**
- All Pydantic I/O schemas live in `src/api/schemas.py`
- All configuration in `src/core/config.py` via `get_settings()`
- All logging via `src/core/logging.py` — use `structlog.get_logger()`

**Your current task:**
[INSERT SPECIFIC STORY FROM BACKLOG]

**Definition of Done for this task:**
1. Code written and `pytest tests/unit/test_[module].py` passes
2. Coverage for your module ≥ 85% (`pytest --cov=src/[module]`)
3. `mypy src/[module]/` passes with no errors
4. No hardcoded credentials, IPs, or file paths — use Settings
5. Commit message format: `feat([module]): [description]`
```

---

## 6. Inter-Agent Data Contract (schemas.py)

All agents share these Pydantic models as the integration boundary:

```python
# src/api/schemas.py  (skeleton — Agent Epsilon writes the authoritative version)

from pydantic import BaseModel, Field
from typing import Optional
import datetime

class IngestResult(BaseModel):
    """Produced by Agent Alpha. Consumed by Beta, Gamma."""
    run_id: str
    timestamp: datetime.datetime
    bounding_box: list[float]          # [lon_min, lat_min, lon_max, lat_max]
    atmospheric_vars: list[str]        # e.g. ["u10", "v10", "msl"]
    ocean_vars: list[str]              # e.g. ["uo", "vo", "zos"]
    dataset_path: str                  # local path to harmonized NetCDF
    air_gap_mode: bool

class DriftCorridorResult(BaseModel):
    """Produced by Agent Beta. Consumed by Delta, Eta."""
    run_id: str
    origin: list[float]                # [lon, lat] last known GPS
    leeway_pct: float                  # 1.0 – 5.0
    seed: int
    particle_tracks: list[list[list[float]]]   # [particle][timestep][lon, lat]
    corridor_geojson: dict             # Shapely convex hull as GeoJSON Polygon
    forecast_hours: int = 24

class RampAlertPayload(BaseModel):
    """Produced by Agent Gamma (ramp_forecaster). Consumed by Delta, Eta."""
    run_id: str
    alert_type: str                    # "TURBINE_CUTOUT" | "SOLAR_DROP"
    asset_id: str
    location: list[float]              # [lon, lat]
    severity: str                      # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    time_window_utc: list[datetime.datetime]
    siem_json: dict

class CVIAlert(BaseModel):
    """Produced by Agent Gamma (cvi_engine). Consumed by Delta, Eta."""
    run_id: str
    asset_id: str
    cvi_score: float                   # 0.0 – 100.0
    weather_severity: str
    attack_surface_window_utc: list[datetime.datetime]
    recommended_action: str
    siem_json: dict

class PriceForecast(BaseModel):
    """Produced by Agent Gamma (price_model). Consumed by Eta."""
    run_id: str
    market: str                        # e.g. "EPEX_DE"
    forecast_intervals: list[datetime.datetime]
    forecast_prices_eur_mwh: list[float]
    negative_pricing_flags: list[bool]
    model_mae: Optional[float] = None
```

---

## 7. CLAUDE.md (Agent Onboarding File)

```markdown
# Project METOC-Lagrangian — Agent Onboarding

## Project Mission
Produce a NATO-compliant, air-gap-ready Lagrangian drift and energy 
security forecasting platform. See METOC_LAGRANGIAN_SCRUM_PLAN.md 
for full context.

## Critical Rules for All Agents
1. Never import from `src/ingestion/` in `src/nato/` or vice versa 
   — all data passes through `schemas.py` contracts.
2. Never call external URLs at runtime. Use `get_settings().air_gap_mode` 
   to switch between live API and local file-system modes.
3. All random state must use `np.random.default_rng(get_settings().seed)`.
4. Run `pytest --cov=src/YOUR_MODULE` before every commit.
5. Use `structlog.get_logger(__name__)` — never `print()`.

## Running Tests
    pip install -e ".[dev]"
    pytest tests/ --cov=src --cov-report=term-missing

## Running the Pipeline (local sample data)
    python -m src.core.pipeline \
      --input data/samples/ \
      --origin 14.5,36.8 \
      --leeway 2.5 \
      --seed 42

## Environment Variables
| Variable | Default | Description |
|---|---|---|
| `AIR_GAP_MODE` | `false` | Disables all outbound HTTP |
| `SEED` | `42` | Monte Carlo random seed |
| `LOG_LEVEL` | `INFO` | structlog level |
| `CMEMS_USERNAME` | — | Required in live mode |
| `CMEMS_PASSWORD` | — | Required in live mode |
| `DATA_INPUT_DIR` | `data/input/` | Air-gap staging folder |
| `DATA_OUTPUT_DIR` | `data/output/` | STANAG export folder |
```

---

## 8. CI/CD Pipeline Design

### `.github/workflows/ci.yml`
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[dev]"
      - run: mypy src/
      - run: pytest tests/unit/ --cov=src --cov-fail-under=85 -v
      - run: pytest tests/integration/test_pipeline_local.py -v

  nato-schema-validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit/test_metgm_compiler.py tests/unit/test_nodef1_exporter.py -v

  air-gap-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t metoc-lagrangian:test .
      - name: Run with network disabled
        run: |
          docker run --network none \
            -v $(pwd)/data/samples:/app/data/input:ro \
            -v /tmp/output:/app/data/output \
            -e AIR_GAP_MODE=true \
            -e SEED=42 \
            metoc-lagrangian:test \
            python -m src.core.pipeline --input /app/data/input
      - name: Validate outputs exist
        run: ls /tmp/output/*.xml /tmp/output/*.bin /tmp/output/*.geojson
```

---

## 9. Sprint Velocity & Risk Register

### Capacity Planning
| Agent | Sprint Capacity (pts) | Peak Parallel Stories |
|---|---|---|
| Alpha (Ingestion) | 25 | 3 |
| Beta (Physics) | 25 | 2 |
| Gamma (WESF) | 30 | 3 |
| Delta (NATO) | 25 | 2 |
| Epsilon (MLOps) | 20 | 2 |
| Zeta (QA) | 30 | 4 |
| Eta (Viz/API) | 20 | 2 |
| **TOTAL** | **175/sprint** | — |

### Risk Register

| Risk ID | Description | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | CMEMS API rate limits break ingest client | High | Medium | Implement exponential backoff + local cache; air-gap mode as fallback |
| R-02 | OpenDrift GPU dependencies incompatible with air-gap base image | Medium | High | Pin CPU-only OpenDrift variant; test Docker offline build in Sprint 1 |
| R-03 | STANAG 6015 XSD schema not publicly available | Medium | High | Use reference implementation parser for validation; contact MC-WG via liaison |
| R-04 | Deep learning price model MAE > 5 €/MWh on real data | Medium | Medium | Fallback to classical SARIMA model; document limitation in DoD |
| R-05 | 3-minute NFR not met on single-core CI runner | Low | Medium | Profile Monte Carlo loop; add Numba JIT compilation in Sprint 4 |
| R-06 | Agents produce conflicting `schemas.py` edits | High | High | **Epsilon owns `schemas.py` exclusively**; all changes via PR review |
| R-07 | CVI scoring algorithm challenged as non-deterministic | Low | Low | Document scoring formula in `docs/`; add unit test with fixed inputs |

---

## 10. Scrum Ceremonies Calendar

| Ceremony | Cadence | Duration | Participants |
|---|---|---|---|
| Sprint Planning | Every 2 weeks (Monday) | 2 hours | Scrum Master + all agents |
| Daily Standup | Daily (async prompt) | 15 min | Scrum Master reviews PR diffs |
| Sprint Review | Every 2 weeks (Friday) | 1 hour | Scrum Master + stakeholders |
| Retrospective | Every 2 weeks (Friday) | 30 min | Scrum Master + all agents |
| Backlog Grooming | Weekly (Wednesday) | 1 hour | Scrum Master + relevant agents |

### Daily Standup Async Prompt Template
```
STANDUP FOR [AGENT NAME] - [DATE]

1. What did you complete yesterday? (list commit hashes or PR numbers)
2. What are you working on today? (story ID from backlog)
3. Any blockers? (schema conflicts, missing data, unclear requirements)
4. Coverage status: [X]% (target ≥ 85%)
```

---

## 11. Quick-Start Commands for the Scrum Master

```bash
# 1. Bootstrap the project
git clone <repo> metoc-lagrangian && cd metoc-lagrangian
pip install -e ".[dev]"

# 2. Run full test suite
pytest tests/ --cov=src --cov-report=html -v

# 3. Run pipeline with sample data (air-gap mode)
AIR_GAP_MODE=true SEED=42 python -m src.core.pipeline \
  --input data/samples/ \
  --origin "14.5,36.8" \
  --leeway 2.5

# 4. Build and test Docker image offline
docker build -t metoc-lagrangian:dev .
docker run --network none \
  -v $(pwd)/data/samples:/app/data/input:ro \
  -e AIR_GAP_MODE=true SEED=42 \
  metoc-lagrangian:dev \
  python -m src.core.pipeline --input /app/data/input

# 5. Validate NATO exports
python -m src.nato.metgm_compiler --validate data/output/latest.metgm.xml
python -m src.nato.nodef1_exporter --roundtrip-test data/output/latest.nodef1.bin

# 6. Launch API server
uvicorn src.api.main:app --reload --port 8000
# → OpenAPI docs at http://localhost:8000/docs
```

---

*Document maintained by Scrum Master. Last updated: May 2026.*
*All agents must acknowledge CLAUDE.md before committing to their assigned modules.*
