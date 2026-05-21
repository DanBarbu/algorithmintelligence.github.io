"""Lagrangian drift trajectory API endpoints."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException
from fastapi.responses import JSONResponse

from src.api.schemas import DriftCorridorResult, PipelineRunSummary
from src.core.config import get_settings

logger = structlog.get_logger(__name__)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_summary(run_id: str) -> PipelineRunSummary:
    """Load a PipelineRunSummary by run_id from the output directory."""
    settings = get_settings()
    summary_path = settings.data_output_dir / f"{run_id}_summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    try:
        return PipelineRunSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse summary: {exc}") from exc


async def _run_drift_bg(
    origin: list[float],
    leeway_pct: float,
    seed: int,
) -> None:
    """Background task: run a drift-only pipeline pass."""
    try:
        from src.core.pipeline import run_pipeline

        settings = get_settings()
        await run_pipeline(
            origin=tuple(origin),  # type: ignore[arg-type]
            bounding_box=[
                origin[0] - 5.0,
                origin[1] - 5.0,
                origin[0] + 5.0,
                origin[1] + 5.0,
            ],
            leeway_pct=leeway_pct,
            seed=seed,
        )
    except Exception as exc:
        logger.exception("drift_bg.error", error=str(exc))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/{run_id}",
    response_model=DriftCorridorResult,
    summary="Get drift corridor result for a run",
)
async def get_drift(run_id: str) -> DriftCorridorResult:
    """
    Return the ``DriftCorridorResult`` for the given ``run_id``.

    Reads from the persisted summary JSON in the output directory.

    Raises 404 if the run does not exist.
    Raises 422 if the run completed without drift data (e.g. pipeline failed).
    """
    summary = _load_summary(run_id)
    if summary.drift is None:
        raise HTTPException(
            status_code=422,
            detail=f"Run '{run_id}' has no drift result (pipeline may have failed).",
        )
    return summary.drift


@router.get(
    "/{run_id}/geojson",
    summary="Get raw GeoJSON drift corridor polygon",
)
async def get_drift_geojson(run_id: str) -> JSONResponse:
    """
    Return the raw GeoJSON Polygon representing the convex-hull drift corridor.

    The polygon is in RFC 7946 format with coordinates as [longitude, latitude].
    """
    summary = _load_summary(run_id)
    if summary.drift is None:
        raise HTTPException(
            status_code=422,
            detail=f"Run '{run_id}' has no drift corridor.",
        )

    geojson: dict[str, Any] = {
        "type": "Feature",
        "geometry": summary.drift.corridor_geojson,
        "properties": {
            "run_id": run_id,
            "area_km2": summary.drift.corridor_area_km2,
            "n_particles": summary.drift.n_particles,
            "leeway_pct": summary.drift.leeway_pct,
            "forecast_hours": summary.drift.forecast_hours,
            "centroid": summary.drift.centroid,
            "origin": summary.drift.origin,
        },
    }
    return JSONResponse(content=geojson, media_type="application/geo+json")


@router.post(
    "/run",
    status_code=202,
    summary="Trigger a drift simulation",
)
async def trigger_drift_run(
    background_tasks: BackgroundTasks,
    origin: list[float] = Body(..., examples={"default": {"value": [14.5, 36.8]}}),
    leeway_pct: float = Body(default=2.5, ge=1.0, le=5.0),
    seed: int = Body(default=42),
) -> dict[str, Any]:
    """
    Trigger a Lagrangian drift simulation in the background.

    The simulation runs a full pipeline pass and writes the result to the output
    directory. Poll ``GET /api/v1/runs`` for completion status.

    Body
    ----
    origin:
        [lon, lat] of the drifting object's last GPS fix.
    leeway_pct:
        Wind leeway percentage (1.0–5.0).
    seed:
        RNG seed for deterministic simulation.
    """
    if len(origin) != 2:
        raise HTTPException(status_code=422, detail="origin must be [lon, lat] (2 elements).")

    background_tasks.add_task(_run_drift_bg, origin=origin, leeway_pct=leeway_pct, seed=seed)

    logger.info("drift.trigger", origin=origin, leeway_pct=leeway_pct, seed=seed)
    return {
        "status": "accepted",
        "message": "Drift simulation queued. Poll GET /api/v1/runs for results.",
    }
