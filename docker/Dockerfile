# ── Stage 1: Builder ──────────────────────────────────────────────────────────
# Installs all Python dependencies into /install so the runtime stage
# can copy them without a pip cache or build tools.
FROM python:3.11-slim AS builder

WORKDIR /build

# System build dependencies (needed for cfgrib, eccodes, netCDF4, pyproj)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libeccodes-dev \
    libhdf5-dev \
    libnetcdf-dev \
    libgeos-dev \
    libproj-dev \
    libffi-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first (layer-cache friendly)
COPY pyproject.toml ./

# Air-gap build mode: use pre-downloaded wheel files from /wheels
# Regular build mode: install from PyPI
ARG AIR_GAP_BUILD=false

RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "$AIR_GAP_BUILD" = "true" ]; then \
        pip install --no-index --find-links /wheels -r requirements.lock \
            --prefix=/install; \
    else \
        pip install --prefix=/install -e ".[dev]" 2>/dev/null || \
        pip install --prefix=/install \
            "fastapi>=0.115" \
            "uvicorn[standard]>=0.30" \
            "pydantic>=2.7" \
            "pydantic-settings>=2.3" \
            "python-dotenv>=1.0" \
            "structlog>=24.1" \
            "xarray>=2024.6" \
            "numpy>=1.26" \
            "pandas>=2.2" \
            "scipy>=1.13" \
            "shapely>=2.0" \
            "pyproj>=3.6" \
            "lxml>=5.2" \
            "httpx>=0.27" \
            "netCDF4>=1.7" \
            "pytest>=8.2" \
            "pytest-asyncio>=0.23" \
            "pytest-cov>=5.0" \
            "mypy>=1.10" \
            "ruff>=0.5"; \
    fi


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
# Slim production image — no build tools, only site-packages + src
FROM python:3.11-slim AS runtime

# Runtime system libraries (shared objects needed at execution time)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libeccodes0 \
    libhdf5-103 \
    libnetcdf19 \
    libgeos-c1v5 \
    libproj25 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy source code
COPY src/ ./src/
COPY pyproject.toml ./

# Create unprivileged runtime user
RUN useradd --no-create-home --shell /bin/false metoc && \
    mkdir -p data/input data/output data/samples && \
    chown -R metoc:metoc /app

USER metoc

# Environment defaults (can be overridden at runtime)
ENV AIR_GAP_MODE=false \
    SEED=42 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Persistent data volumes — mount host paths here in production
VOLUME ["/app/data/input", "/app/data/output"]

# REST API port
EXPOSE 8000

# Health check — polls the /health endpoint every 30 s
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default: run the pipeline orchestrator (batch mode)
# Override with: docker run ... uvicorn src.api.main:app --host 0.0.0.0 --port 8000
CMD ["python", "-m", "src.core.pipeline"]


# ── API target ────────────────────────────────────────────────────────────────
# Build with: docker build --target api -t metoc-api .
# Run with:   docker run -p 8000:8000 metoc-api
FROM runtime AS api
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
