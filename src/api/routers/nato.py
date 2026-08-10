"""NATO export download endpoints."""
from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.api.schemas import PipelineRunSummary
from src.core.config import get_settings

logger = structlog.get_logger(__name__)

router = APIRouter()

# MIME types for NATO export formats
_MIME_XML     = "application/xml"
_MIME_BINARY  = "application/octet-stream"
_MIME_GEOJSON = "application/geo+json"


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


def _check_file(path: str, label: str) -> Path:
    """Validate that an export file path exists and is readable."""
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"{label} file not found at '{path}'.")
    if not p.is_file():
        raise HTTPException(status_code=500, detail=f"'{path}' is not a regular file.")
    return p


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/{run_id}/metgm",
    response_class=FileResponse,
    summary="Download STANAG 6015 METGM XML export",
)
async def download_metgm(run_id: str) -> FileResponse:
    """
    Download the STANAG 6015 (AMETOCP-4) METGM XML file for the given run.

    The XML is validated against the embedded METGM XSD during compilation.
    The response Content-Disposition header triggers browser download.

    Raises 404 if the run or its METGM export does not exist.
    """
    summary = _load_summary(run_id)
    if summary.metgm_export is None:
        raise HTTPException(
            status_code=422,
            detail=f"Run '{run_id}' has no METGM export.",
        )

    xml_path = _check_file(summary.metgm_export.xml_path, "METGM XML")
    filename = xml_path.name

    logger.info("nato.metgm_download", run_id=run_id, path=str(xml_path))
    return FileResponse(
        path=str(xml_path),
        media_type=_MIME_XML,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{run_id}/nodef1",
    response_class=FileResponse,
    summary="Download STANAG 1317 NODEF-1 binary export",
)
async def download_nodef1(run_id: str) -> FileResponse:
    """
    Download the STANAG 1317 NODEF-1 ocean data binary file for the given run.

    Each record in the binary file contains a CRC-32 integrity checksum.
    The response Content-Disposition header triggers browser download.

    Raises 404 if the run or its NODEF-1 export does not exist.
    """
    summary = _load_summary(run_id)
    if summary.nodef1_export is None:
        raise HTTPException(
            status_code=422,
            detail=f"Run '{run_id}' has no NODEF-1 export.",
        )

    bin_path = _check_file(summary.nodef1_export.binary_path, "NODEF-1 binary")
    filename = bin_path.name

    logger.info("nato.nodef1_download", run_id=run_id, path=str(bin_path))
    return FileResponse(
        path=str(bin_path),
        media_type=_MIME_BINARY,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{run_id}/app6",
    response_class=FileResponse,
    summary="Download APP-6D GeoJSON symbology export",
)
async def download_app6(run_id: str) -> FileResponse:
    """
    Download the APP-6D / MIL-STD-2525D GeoJSON FeatureCollection for the given run.

    Features include drift corridor polygon, asset markers, ramp alerts, and CVI alerts,
    each annotated with a SIDC (Symbol Identification Code).

    Raises 404 if the run or its APP-6 export does not exist.
    """
    summary = _load_summary(run_id)
    if summary.app6_export is None:
        raise HTTPException(
            status_code=422,
            detail=f"Run '{run_id}' has no APP-6 export.",
        )

    geojson_path = _check_file(summary.app6_export.geojson_path, "APP-6 GeoJSON")
    filename = geojson_path.name

    logger.info("nato.app6_download", run_id=run_id, path=str(geojson_path))
    return FileResponse(
        path=str(geojson_path),
        media_type=_MIME_GEOJSON,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
