"""
Integration test: full pipeline run on synthetic sample data.
Uses AIR_GAP_MODE=true with pre-generated synthetic NetCDF in data/samples/.
No internet access required.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from src.api.schemas import PipelineRunSummary


# ── Shared pipeline parameters ────────────────────────────────────────────────

_ORIGIN = (14.5, 36.8)
_BBOX = [10.0, 30.0, 20.0, 40.0]
_LEEWAY = 2.5
_SEED = 42


@pytest.fixture(scope="module")
def pipeline_summary(tmp_path_factory) -> PipelineRunSummary:
    """
    Run the full pipeline once and return the summary.

    Scoped to *module* so we only pay the pipeline cost once and share the
    result across all tests in this module.
    """
    import os

    from src.core.config import Settings, get_settings
    from src.core.pipeline import run_pipeline

    # Override settings for this integration test
    base = tmp_path_factory.mktemp("pipeline_integration")
    os.environ["AIR_GAP_MODE"] = "true"
    os.environ["SEED"] = str(_SEED)
    os.environ["LOG_LEVEL"] = "WARNING"
    os.environ["DATA_OUTPUT_DIR"] = str(base / "output")
    os.environ["DATA_INPUT_DIR"] = str(base / "input")
    os.environ["DATA_SAMPLES_DIR"] = str(base / "samples")

    # Clear the settings cache so our env vars take effect
    get_settings.cache_clear()

    settings = get_settings()
    settings.ensure_dirs()

    summary = asyncio.run(
        run_pipeline(
            origin=_ORIGIN,
            bounding_box=_BBOX,
            leeway_pct=_LEEWAY,
            seed=_SEED,
        )
    )
    return summary


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPipelineCompletes:
    """NFR-2: pipeline must complete in under 180 seconds."""

    def test_pipeline_completes_under_180_seconds(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert full pipeline wall-clock duration is less than 180 seconds."""
        duration = pipeline_summary.duration_seconds
        assert duration < 180.0, (
            f"NFR-2 violated: pipeline took {duration:.1f}s "
            f"(limit 180s). Check for I/O bottlenecks or excessive computation."
        )

    def test_pipeline_success_flag(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert the pipeline reported success (no unhandled exception)."""
        assert pipeline_summary.success, (
            f"Pipeline failed: {pipeline_summary.error_message}"
        )

    def test_pipeline_under_three_minutes_property(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert the convenience property returns True."""
        assert pipeline_summary.under_three_minutes


class TestPipelineOutputFiles:
    """Assert all four required output files are created."""

    def test_pipeline_produces_summary_json(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert the pipeline summary JSON file exists on disk."""
        from src.core.config import get_settings

        settings = get_settings()
        summary_path = settings.data_output_dir / f"{pipeline_summary.run_id}_summary.json"
        assert summary_path.exists(), f"Summary JSON not found: {summary_path}"
        assert summary_path.stat().st_size > 0

    def test_pipeline_produces_metgm_xml(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert METGM XML file was created and is non-empty."""
        assert pipeline_summary.metgm_export is not None, "metgm_export is None"
        xml_path = Path(pipeline_summary.metgm_export.xml_path)
        assert xml_path.exists(), f"METGM XML not found: {xml_path}"
        assert xml_path.stat().st_size > 0
        assert xml_path.suffix == ".xml"

    def test_pipeline_produces_nodef1_bin(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert NODEF-1 binary file was created and is non-empty."""
        assert pipeline_summary.nodef1_export is not None, "nodef1_export is None"
        bin_path = Path(pipeline_summary.nodef1_export.binary_path)
        assert bin_path.exists(), f"NODEF-1 binary not found: {bin_path}"
        assert bin_path.stat().st_size > 0

    def test_pipeline_produces_app6_geojson(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert APP-6 GeoJSON file was created and is non-empty."""
        assert pipeline_summary.app6_export is not None, "app6_export is None"
        geojson_path = Path(pipeline_summary.app6_export.geojson_path)
        assert geojson_path.exists(), f"APP-6 GeoJSON not found: {geojson_path}"
        assert geojson_path.stat().st_size > 0

    def test_pipeline_produces_all_output_files(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert summary, METGM, NODEF-1, and APP-6 files all exist in a single test."""
        from src.core.config import get_settings

        settings = get_settings()
        run_id = pipeline_summary.run_id

        expected = [
            settings.data_output_dir / f"{run_id}_summary.json",
        ]
        if pipeline_summary.metgm_export:
            expected.append(Path(pipeline_summary.metgm_export.xml_path))
        if pipeline_summary.nodef1_export:
            expected.append(Path(pipeline_summary.nodef1_export.binary_path))
        if pipeline_summary.app6_export:
            expected.append(Path(pipeline_summary.app6_export.geojson_path))

        missing = [str(p) for p in expected if not p.exists()]
        assert not missing, f"Missing output files:\n" + "\n".join(missing)


class TestPipelineDeterminism:
    """NFR-3: fixed seed must produce identical drift corridor coordinates."""

    def test_pipeline_deterministic(self, tmp_path: Path) -> None:
        """Two pipeline runs with the same seed must produce identical drift corridors."""
        import os

        from src.core.config import get_settings
        from src.core.pipeline import run_pipeline

        base1 = tmp_path / "run1"
        base2 = tmp_path / "run2"

        def _run(output_dir: Path) -> PipelineRunSummary:
            os.environ["DATA_OUTPUT_DIR"] = str(output_dir)
            get_settings.cache_clear()
            s = get_settings()
            s.ensure_dirs()
            return asyncio.run(
                run_pipeline(
                    origin=_ORIGIN,
                    bounding_box=_BBOX,
                    leeway_pct=_LEEWAY,
                    seed=_SEED,
                )
            )

        summary1 = _run(base1)
        summary2 = _run(base2)

        assert summary1.drift is not None, "Run 1 produced no drift result"
        assert summary2.drift is not None, "Run 2 produced no drift result"

        coords1 = summary1.drift.corridor_geojson.get("coordinates", [])
        coords2 = summary2.drift.corridor_geojson.get("coordinates", [])

        assert coords1 == coords2, (
            "Drift corridor coordinates differ between runs with the same seed. "
            f"Run 1 centroid: {summary1.drift.centroid}, "
            f"Run 2 centroid: {summary2.drift.centroid}"
        )

        assert summary1.drift.centroid == summary2.drift.centroid, (
            f"Drift centroids differ: {summary1.drift.centroid} vs {summary2.drift.centroid}"
        )


class TestPipelineSummarySchema:
    """Assert the summary JSON is valid and parseable to PipelineRunSummary."""

    def test_pipeline_summary_json_parseable(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert the written summary JSON parses back to a PipelineRunSummary."""
        from src.core.config import get_settings

        settings = get_settings()
        summary_path = settings.data_output_dir / f"{pipeline_summary.run_id}_summary.json"

        assert summary_path.exists(), f"Summary file missing: {summary_path}"

        raw_json = summary_path.read_text(encoding="utf-8")

        # Must not raise
        parsed = PipelineRunSummary.model_validate_json(raw_json)

        assert parsed.run_id == pipeline_summary.run_id
        assert parsed.success == pipeline_summary.success
        assert parsed.duration_seconds == pipeline_summary.duration_seconds

    def test_summary_has_required_fields(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert the summary has all mandatory top-level fields populated."""
        assert pipeline_summary.run_id, "run_id is empty"
        assert pipeline_summary.started_at is not None
        assert pipeline_summary.completed_at is not None
        assert pipeline_summary.duration_seconds >= 0.0

    def test_summary_drift_has_corridor(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert the drift corridor is present and has valid GeoJSON structure."""
        drift = pipeline_summary.drift
        assert drift is not None, "No drift result in summary"
        assert drift.corridor_geojson.get("type") in ("Polygon", "MultiPolygon"), (
            f"Unexpected corridor GeoJSON type: {drift.corridor_geojson.get('type')}"
        )
        assert drift.corridor_area_km2 >= 0.0
        assert len(drift.centroid) == 2
        assert drift.n_particles >= 10

    def test_summary_cvi_alerts_present(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert at least one CVI alert was generated (3 assets → 3 alerts min)."""
        assert len(pipeline_summary.cvi_alerts) >= 1, "Expected at least one CVI alert"

    def test_summary_price_forecast_valid(self, pipeline_summary: PipelineRunSummary) -> None:
        """Assert the price forecast has consistent interval/price list lengths."""
        pf = pipeline_summary.price_forecast
        assert pf is not None, "No price forecast in summary"
        assert len(pf.forecast_intervals) == len(pf.forecast_prices_eur_mwh)
        assert len(pf.forecast_intervals) == len(pf.negative_pricing_flags)
        assert len(pf.forecast_intervals) >= 1
