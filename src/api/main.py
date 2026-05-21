"""
METOC-Lagrangian REST API.
FastAPI application exposing drift, WESF, and NATO endpoints.
Auto-generated OpenAPI docs available at /docs.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import structlog
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.api.routers import drift, nato, wesf
from src.api.schemas import PipelineRunSummary
from src.core.config import get_settings
from src.core.logging_config import configure_logging

logger = structlog.get_logger(__name__)

# ── Application factory ───────────────────────────────────────────────────────

app = FastAPI(
    title="METOC-Lagrangian API",
    version="0.1.0",
    description=(
        "NATO-compliant Lagrangian drift & energy-security forecasting platform. "
        "Provides drift corridor simulation, WESF ramp/CVI analysis, and NATO export endpoints."
    ),
    contact={
        "name": "Algorithm Intelligence",
        "url": "https://algorithmintelligence.github.io",
    },
    license_info={"name": "MIT"},
)

# ── Include routers ───────────────────────────────────────────────────────────

app.include_router(drift.router, prefix="/api/v1/drift",  tags=["drift"])
app.include_router(wesf.router,  prefix="/api/v1/wesf",   tags=["wesf"])
app.include_router(nato.router,  prefix="/api/v1/nato",   tags=["nato"])

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_dirs()
    logger.info(
        "metoc_api.startup",
        air_gap_mode=settings.air_gap_mode,
        data_output_dir=str(settings.data_output_dir),
    )


# ── Core endpoints ────────────────────────────────────────────────────────────

@app.get("/health", summary="Health check", tags=["meta"])
async def health() -> dict[str, Any]:
    """Return service liveness status and runtime mode."""
    settings = get_settings()
    return {"status": "ok", "air_gap_mode": settings.air_gap_mode}


@app.get(
    "/api/v1/runs",
    response_model=list[PipelineRunSummary],
    summary="List all pipeline run summaries",
    tags=["meta"],
)
async def list_runs() -> list[PipelineRunSummary]:
    """
    Return all available PipelineRunSummary records found in the output directory.

    Summaries are loaded from ``{data_output_dir}/*_summary.json`` files.
    Returns an empty list if no runs have been completed yet.
    """
    settings = get_settings()
    summaries: list[PipelineRunSummary] = []

    for summary_file in sorted(settings.data_output_dir.glob("*_summary.json")):
        try:
            raw = summary_file.read_text(encoding="utf-8")
            summary = PipelineRunSummary.model_validate_json(raw)
            summaries.append(summary)
        except Exception as exc:
            logger.warning(
                "list_runs.parse_error",
                file=str(summary_file),
                error=str(exc),
            )

    logger.info("list_runs", count=len(summaries))
    return summaries


# ── Background pipeline trigger ───────────────────────────────────────────────

class _PipelineRunRequest:
    """Internal DTO for pipeline trigger requests."""

    def __init__(
        self,
        origin: list[float],
        bounding_box: list[float],
        leeway_pct: float = 2.5,
        seed: int = 42,
    ) -> None:
        self.origin = origin
        self.bounding_box = bounding_box
        self.leeway_pct = leeway_pct
        self.seed = seed


async def _run_pipeline_bg(
    origin: list[float],
    bounding_box: list[float],
    leeway_pct: float,
    seed: int,
) -> None:
    """Background task wrapper — runs the pipeline and logs on error."""
    try:
        from src.core.pipeline import run_pipeline  # deferred to avoid circular import

        await run_pipeline(
            origin=tuple(origin),  # type: ignore[arg-type]
            bounding_box=bounding_box,
            leeway_pct=leeway_pct,
            seed=seed,
        )
    except Exception as exc:
        logger.exception("pipeline.background_run_error", error=str(exc))


@app.post(
    "/api/v1/pipeline/run",
    summary="Trigger a pipeline run asynchronously",
    status_code=202,
    tags=["meta"],
)
async def trigger_pipeline_run(
    background_tasks: BackgroundTasks,
    origin_lon: float = 14.5,
    origin_lat: float = 36.8,
    leeway_pct: float = 2.5,
    seed: int = 42,
    bbox: str = "10.0,30.0,20.0,40.0",
) -> dict[str, Any]:
    """
    Trigger a full pipeline run in the background.

    Returns immediately with a ``run_id`` that can be polled via ``GET /api/v1/runs``.

    Parameters
    ----------
    origin_lon, origin_lat:
        Last known GPS fix of the object.
    leeway_pct:
        Wind leeway percentage.
    seed:
        RNG seed for reproducibility.
    bbox:
        Bounding box as ``"lon_min,lat_min,lon_max,lat_max"``.
    """
    try:
        bounding_box = [float(x.strip()) for x in bbox.split(",")]
        if len(bounding_box) != 4:
            raise ValueError("Expected 4 values")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid bbox: {exc}") from exc

    import uuid as _uuid
    run_id = str(_uuid.uuid4())

    background_tasks.add_task(
        _run_pipeline_bg,
        origin=[origin_lon, origin_lat],
        bounding_box=bounding_box,
        leeway_pct=leeway_pct,
        seed=seed,
    )

    logger.info(
        "pipeline.trigger",
        origin=[origin_lon, origin_lat],
        leeway_pct=leeway_pct,
        seed=seed,
    )

    return {
        "status": "accepted",
        "run_id": run_id,
        "message": "Pipeline run queued. Poll GET /api/v1/runs for results.",
    }
