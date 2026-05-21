"""
Unit tests for APP-6D / MIL-STD-2525D Tactical Symbology Builder.

Uses synthetic DriftCorridorResult, RampAlertPayload, and CVIAlert fixtures
to exercise all feature builders and the full export pipeline.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from src.api.schemas import (
    AlertSeverity,
    AlertType,
    AssetLocation,
    CVIAlert,
    DriftCorridorResult,
    ParticleTrack,
    RampAlertPayload,
)
from src.nato.app6_symbology import (
    _SIDC_CBRN_HAZARD,
    _SIDC_DRIFT_CORRIDOR,
    _SIDC_DRIFT_ORIGIN,
    _SIDC_HAZARD_AREA,
    App6Symbology,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def symbology() -> App6Symbology:
    """Return a default App6Symbology instance."""
    return App6Symbology()


@pytest.fixture()
def drift_result() -> DriftCorridorResult:
    """Minimal synthetic DriftCorridorResult for testing."""
    track = ParticleTrack(
        particle_id=0,
        positions=[[2.0, 51.0], [2.05, 51.05], [2.1, 51.1]],
        final_position=[2.1, 51.1],
    )
    return DriftCorridorResult(
        run_id="drift-test-run-001",
        ingest_run_id="ingest-001",
        origin=[2.0, 51.0],
        leeway_pct=2.5,
        seed=42,
        n_particles=10,
        timestep_hours=1.0,
        forecast_hours=3,
        particle_tracks=[track],
        corridor_geojson={
            "type": "Polygon",
            "coordinates": [
                [[2.0, 51.0], [2.1, 51.0], [2.1, 51.1], [2.0, 51.1], [2.0, 51.0]]
            ],
        },
        corridor_area_km2=100.0,
        centroid=[2.05, 51.05],
        compute_time_seconds=0.5,
    )


@pytest.fixture()
def turbine_alert() -> RampAlertPayload:
    """Synthetic TURBINE_CUTOUT ramp alert."""
    now = datetime.datetime.now(tz=datetime.UTC)
    return RampAlertPayload(
        run_id="ramp-run-001",
        ingest_run_id="ingest-001",
        alert_type=AlertType.TURBINE_CUTOUT,
        asset=AssetLocation(
            asset_id="turbine-A1",
            lon=3.5,
            lat=52.0,
            asset_type="WIND_TURBINE",
            rated_mw=5.0,
        ),
        severity=AlertSeverity.HIGH,
        trigger_value=26.0,
        threshold_value=25.0,
        unit="m/s",
        time_window_start=now,
        time_window_end=now + datetime.timedelta(hours=1),
        estimated_mw_loss=4.8,
    )


@pytest.fixture()
def solar_alert() -> RampAlertPayload:
    """Synthetic SOLAR_DROP ramp alert."""
    now = datetime.datetime.now(tz=datetime.UTC)
    return RampAlertPayload(
        run_id="ramp-run-002",
        ingest_run_id="ingest-001",
        alert_type=AlertType.SOLAR_DROP,
        asset=AssetLocation(
            asset_id="solar-B2",
            lon=4.0,
            lat=51.5,
            asset_type="SOLAR_PV",
            rated_mw=2.0,
        ),
        severity=AlertSeverity.MEDIUM,
        trigger_value=7.5,
        threshold_value=7.0,
        unit="oktas",
        time_window_start=now,
        time_window_end=now + datetime.timedelta(hours=2),
    )


@pytest.fixture()
def cvi_critical() -> CVIAlert:
    """Synthetic CRITICAL-severity CVIAlert."""
    now = datetime.datetime.now(tz=datetime.UTC)
    return CVIAlert(
        run_id="cvi-run-001",
        ingest_run_id="ingest-001",
        asset=AssetLocation(
            asset_id="inverter-C3",
            lon=3.0,
            lat=51.8,
            asset_type="INVERTER",
        ),
        cvi_score=82.0,
        severity=AlertSeverity.CRITICAL,
        weather_severity_score=7.5,
        contributing_factors=["high wind", "low irradiance"],
        attack_surface_window_start=now,
        attack_surface_window_end=now + datetime.timedelta(hours=6),
        recommended_action="Isolate inverter C3 from SCADA network.",
    )


@pytest.fixture()
def cvi_high() -> CVIAlert:
    """Synthetic HIGH-severity CVIAlert."""
    now = datetime.datetime.now(tz=datetime.UTC)
    return CVIAlert(
        run_id="cvi-run-002",
        ingest_run_id="ingest-001",
        asset=AssetLocation(
            asset_id="turbine-D4",
            lon=2.8,
            lat=51.6,
            asset_type="WIND_TURBINE",
        ),
        cvi_score=70.0,
        severity=AlertSeverity.HIGH,
        weather_severity_score=5.0,
        contributing_factors=["high wind"],
        attack_surface_window_start=now,
        attack_surface_window_end=now + datetime.timedelta(hours=3),
        recommended_action="Monitor turbine D4 SCADA traffic.",
    )


# ── Tests: build_drift_corridor ───────────────────────────────────────────────

class TestBuildDriftCorridor:
    """Tests for App6Symbology.build_drift_corridor()."""

    def test_drift_corridor_sidc_format(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
    ) -> None:
        """SIDC must be a string in the expected range of lengths (15–20 chars)."""
        feature = symbology.build_drift_corridor(drift_result)
        assert isinstance(feature.sidc, str)
        assert 15 <= len(feature.sidc) <= 20, (
            f"SIDC '{feature.sidc}' length {len(feature.sidc)} out of range [15, 20]"
        )

    def test_drift_corridor_sidc_value(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
    ) -> None:
        """Drift corridor SIDC must equal the area-of-interest code."""
        feature = symbology.build_drift_corridor(drift_result)
        assert feature.sidc == _SIDC_DRIFT_CORRIDOR

    def test_drift_corridor_is_polygon_geometry(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
    ) -> None:
        """Geometry type must be 'Polygon' (from corridor_geojson)."""
        feature = symbology.build_drift_corridor(drift_result)
        assert feature.geojson_geometry["type"] == "Polygon"

    def test_drift_corridor_properties_populated(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
    ) -> None:
        """Properties must include run_id, leeway_pct, corridor_area_km2, n_particles."""
        feature = symbology.build_drift_corridor(drift_result)
        props = feature.properties
        assert props["run_id"] == drift_result.run_id
        assert props["leeway_pct"] == drift_result.leeway_pct
        assert props["corridor_area_km2"] == drift_result.corridor_area_km2
        assert props["n_particles"] == drift_result.n_particles


# ── Tests: build_drift_origin ─────────────────────────────────────────────────

class TestBuildDriftOrigin:
    """Tests for App6Symbology.build_drift_origin()."""

    def test_drift_origin_is_point_geometry(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
    ) -> None:
        """Geometry type must be 'Point'."""
        feature = symbology.build_drift_origin(drift_result)
        assert feature.geojson_geometry["type"] == "Point"

    def test_drift_origin_coordinates_match(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
    ) -> None:
        """Point coordinates must match DriftCorridorResult.origin [lon, lat]."""
        feature = symbology.build_drift_origin(drift_result)
        coords = feature.geojson_geometry["coordinates"]
        assert coords[0] == drift_result.origin[0], "Longitude mismatch"
        assert coords[1] == drift_result.origin[1], "Latitude mismatch"

    def test_drift_origin_sidc(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
    ) -> None:
        """SIDC must equal the last-known-position marker code."""
        feature = symbology.build_drift_origin(drift_result)
        assert feature.sidc == _SIDC_DRIFT_ORIGIN


# ── Tests: build_ramp_alert_zone ─────────────────────────────────────────────

class TestBuildRampAlertZone:
    """Tests for App6Symbology.build_ramp_alert_zone()."""

    def test_ramp_alert_has_correct_sidc_for_turbine(
        self,
        symbology: App6Symbology,
        turbine_alert: RampAlertPayload,
    ) -> None:
        """TURBINE_CUTOUT alert → SIDC must contain 'ACMH' (hazard area)."""
        feature = symbology.build_ramp_alert_zone(turbine_alert)
        assert "ACMH" in feature.sidc, (
            f"Expected TURBINE_CUTOUT SIDC to contain 'ACMH', got '{feature.sidc}'"
        )

    def test_ramp_alert_turbine_sidc_value(
        self,
        symbology: App6Symbology,
        turbine_alert: RampAlertPayload,
    ) -> None:
        """TURBINE_CUTOUT SIDC must equal the canonical hazard-area code."""
        feature = symbology.build_ramp_alert_zone(turbine_alert)
        assert feature.sidc == _SIDC_HAZARD_AREA

    def test_ramp_alert_solar_sidc_contains_acmf(
        self,
        symbology: App6Symbology,
        solar_alert: RampAlertPayload,
    ) -> None:
        """SOLAR_DROP alert → SIDC must contain 'ACMF' (infrastructure)."""
        feature = symbology.build_ramp_alert_zone(solar_alert)
        assert "ACMF" in feature.sidc, (
            f"Expected SOLAR_DROP SIDC to contain 'ACMF', got '{feature.sidc}'"
        )

    def test_ramp_alert_is_point_geometry(
        self,
        symbology: App6Symbology,
        turbine_alert: RampAlertPayload,
    ) -> None:
        """Geometry must be a Point located at the asset coordinates."""
        feature = symbology.build_ramp_alert_zone(turbine_alert)
        geo = feature.geojson_geometry
        assert geo["type"] == "Point"
        assert geo["coordinates"][0] == turbine_alert.asset.lon
        assert geo["coordinates"][1] == turbine_alert.asset.lat

    def test_ramp_alert_has_radius_property(
        self,
        symbology: App6Symbology,
        turbine_alert: RampAlertPayload,
    ) -> None:
        """Feature properties must contain a 'radius_m' key for circle rendering."""
        feature = symbology.build_ramp_alert_zone(turbine_alert)
        assert "radius_m" in feature.properties, (
            "Expected 'radius_m' in feature.properties for circle display"
        )


# ── Tests: build_cvi_alert ────────────────────────────────────────────────────

class TestBuildCviAlert:
    """Tests for App6Symbology.build_cvi_alert()."""

    def test_cvi_critical_sidc(
        self,
        symbology: App6Symbology,
        cvi_critical: CVIAlert,
    ) -> None:
        """CRITICAL severity → SIDC must contain 'ACMC' (CBRN hazard)."""
        feature = symbology.build_cvi_alert(cvi_critical)
        assert "ACMC" in feature.sidc, (
            f"Expected CRITICAL CVI SIDC to contain 'ACMC', got '{feature.sidc}'"
        )

    def test_cvi_critical_sidc_value(
        self,
        symbology: App6Symbology,
        cvi_critical: CVIAlert,
    ) -> None:
        """CRITICAL severity SIDC must equal the canonical CBRN-hazard code."""
        feature = symbology.build_cvi_alert(cvi_critical)
        assert feature.sidc == _SIDC_CBRN_HAZARD

    def test_cvi_high_sidc_contains_acmh(
        self,
        symbology: App6Symbology,
        cvi_high: CVIAlert,
    ) -> None:
        """HIGH severity → SIDC must contain 'ACMH' (hazard area)."""
        feature = symbology.build_cvi_alert(cvi_high)
        assert "ACMH" in feature.sidc, (
            f"Expected HIGH CVI SIDC to contain 'ACMH', got '{feature.sidc}'"
        )

    def test_cvi_is_point_geometry(
        self,
        symbology: App6Symbology,
        cvi_critical: CVIAlert,
    ) -> None:
        """CVI alert geometry must be a Point at the asset location."""
        feature = symbology.build_cvi_alert(cvi_critical)
        geo = feature.geojson_geometry
        assert geo["type"] == "Point"
        assert geo["coordinates"][0] == cvi_critical.asset.lon
        assert geo["coordinates"][1] == cvi_critical.asset.lat

    def test_cvi_properties_include_score(
        self,
        symbology: App6Symbology,
        cvi_critical: CVIAlert,
    ) -> None:
        """Properties must carry the cvi_score and severity values."""
        feature = symbology.build_cvi_alert(cvi_critical)
        assert feature.properties["cvi_score"] == cvi_critical.cvi_score
        assert feature.properties["severity"] == cvi_critical.severity.value


# ── Tests: export ─────────────────────────────────────────────────────────────

class TestApp6Export:
    """Tests for App6Symbology.export() end-to-end."""

    def test_export_writes_geojson_file(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
        turbine_alert: RampAlertPayload,
        cvi_critical: CVIAlert,
        tmp_path: Path,
    ) -> None:
        """export() must write a valid GeoJSON FeatureCollection to disk."""
        result = symbology.export(
            drift=drift_result,
            ramp_alerts=[turbine_alert],
            cvi_alerts=[cvi_critical],
            run_id="export-test-001",
            output_dir=tmp_path,
        )

        out_path = Path(result.geojson_path)
        assert out_path.exists(), ".app6.geojson file not found"

        with out_path.open(encoding="utf-8") as fh:
            data = json.load(fh)

        assert data["type"] == "FeatureCollection", (
            f"Expected 'FeatureCollection', got '{data['type']}'"
        )

    def test_export_feature_count_correct(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
        turbine_alert: RampAlertPayload,
        cvi_critical: CVIAlert,
        tmp_path: Path,
    ) -> None:
        """
        1 drift (2 features: corridor + origin) + 1 ramp + 1 CVI = 4 features total.
        """
        result = symbology.export(
            drift=drift_result,
            ramp_alerts=[turbine_alert],
            cvi_alerts=[cvi_critical],
            run_id="export-test-002",
            output_dir=tmp_path,
        )
        assert result.feature_count == 4, (
            f"Expected 4 features, got {result.feature_count}"
        )

    def test_export_without_drift_has_fewer_features(
        self,
        symbology: App6Symbology,
        turbine_alert: RampAlertPayload,
        cvi_critical: CVIAlert,
        tmp_path: Path,
    ) -> None:
        """When drift=None, only ramp and CVI features are produced."""
        result = symbology.export(
            drift=None,
            ramp_alerts=[turbine_alert],
            cvi_alerts=[cvi_critical],
            run_id="export-test-003",
            output_dir=tmp_path,
        )
        assert result.feature_count == 2, (
            f"Expected 2 features (no drift), got {result.feature_count}"
        )

    def test_export_geojson_features_have_sidc(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
        turbine_alert: RampAlertPayload,
        cvi_critical: CVIAlert,
        tmp_path: Path,
    ) -> None:
        """Every feature in the GeoJSON file must have a 'sidc' property."""
        result = symbology.export(
            drift=drift_result,
            ramp_alerts=[turbine_alert],
            cvi_alerts=[cvi_critical],
            run_id="export-test-004",
            output_dir=tmp_path,
        )

        with open(result.geojson_path, encoding="utf-8") as fh:
            data = json.load(fh)

        for i, feat in enumerate(data["features"]):
            assert "sidc" in feat["properties"], (
                f"Feature {i} missing 'sidc' in properties"
            )

    def test_export_result_run_id_preserved(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
        tmp_path: Path,
    ) -> None:
        """App6ExportResult.run_id must match the run_id argument."""
        result = symbology.export(
            drift=drift_result,
            ramp_alerts=[],
            cvi_alerts=[],
            run_id="canonical-run-id",
            output_dir=tmp_path,
        )
        assert result.run_id == "canonical-run-id"

    def test_export_all_features_in_result_list(
        self,
        symbology: App6Symbology,
        drift_result: DriftCorridorResult,
        turbine_alert: RampAlertPayload,
        solar_alert: RampAlertPayload,
        cvi_critical: CVIAlert,
        cvi_high: CVIAlert,
        tmp_path: Path,
    ) -> None:
        """result.features list length must equal result.feature_count."""
        result = symbology.export(
            drift=drift_result,
            ramp_alerts=[turbine_alert, solar_alert],
            cvi_alerts=[cvi_critical, cvi_high],
            run_id="export-test-005",
            output_dir=tmp_path,
        )
        assert len(result.features) == result.feature_count
