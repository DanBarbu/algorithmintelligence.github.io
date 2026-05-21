# Project METOC-Lagrangian — Agent Onboarding

## Project Mission
Produce a NATO-compliant, air-gap-ready Lagrangian drift and energy
security forecasting platform. See `METOC_LAGRANGIAN_SCRUM_PLAN.md`
for the full Scrum Master plan, sprint roadmap, and agent charters.

## Repository Layout
```
src/
  ingestion/      # Agent Alpha — AIFS, GraphCast, CMEMS, air-gap watcher
  lagrangian/     # Agent Beta  — OpenDrift subclass, Monte Carlo, corridors
  wesf/           # Agent Gamma — ramp forecaster, CVI engine, price model
  nato/           # Agent Delta — METGM / NODEF-1 serializers, APP-6
  api/            # Agent Eta   — FastAPI endpoints, Pydantic routers
  core/           # Agent Epsilon — pipeline orchestrator, config, logging
tests/
  unit/           # Agent Zeta — ≥85% coverage target
  integration/    # Agent Zeta — full pipeline + air-gap isolation test
data/
  samples/        # Small NetCDF/GRIB2 fixtures for CI (committed)
  input/          # Air-gap staging folder (gitignored)
  output/         # STANAG exports (gitignored)
```

## Critical Rules for All Agents
1. **Schema ownership:** `src/api/schemas.py` is owned by Agent Epsilon.
   All agents import from it; none may modify it without a PR reviewed
   by the Scrum Master.
2. **No runtime network calls in air-gap mode.** Always check
   `get_settings().air_gap_mode` before any HTTP request.
3. **Reproducibility:** All random state must use
   `np.random.default_rng(get_settings().seed)`.
4. **No `print()`.** Use `structlog.get_logger(__name__)`.
5. **Run tests before committing:**
   `pytest tests/ --cov=src/YOUR_MODULE --cov-fail-under=85`

## Running Tests
```bash
pip install -e ".[dev]"
pytest tests/ --cov=src --cov-report=term-missing
```

## Running the Pipeline (local sample data)
```bash
AIR_GAP_MODE=true SEED=42 python -m src.core.pipeline \
  --input data/samples/ \
  --origin "14.5,36.8" \
  --leeway 2.5
```

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

## Commit Message Convention
```
feat(ingestion): add CMEMS async client with retry logic
fix(lagrangian): correct geostrophic sign convention
test(wesf): add CVI unit tests for high-severity scenario
docs(nato): add STANAG 6015 field mapping table
chore(docker): lock requirements for air-gap deployment
```

## Key Open-Source Dependencies
- **OpenDrift** `github.com/OpenDrift/opendrift` — Lagrangian particle tracking
- **Xarray** `pydata/xarray` — gridded data arrays
- **cfgrib** `ecmwf/cfgrib` — GRIB2 decoding
- **copernicusmarine** `mercator-ocean/copernicus-marine-toolbox` — CMEMS API
- **Darts** `unit8co/darts` — deep learning time-series (NBEATS price model)
- **Shapely** `shapely/shapely` — convex hull corridor geometry
- **FastAPI** `tiangolo/fastapi` — REST API layer
