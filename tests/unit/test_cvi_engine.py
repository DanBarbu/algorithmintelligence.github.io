"""
Unit tests for src.wesf.cvi_engine.CVIEngine.

Tests cover the full scoring range, severity mapping, contributing factors,
and attack-surface window duration.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.api.schemas import AlertSeverity, AssetLocation
from src.wesf.cvi_engine import _ATTACK_WINDOW_HOURS, CVIEngine

# ---------------------------------------------------------------------------
# Shared fixtures / constants
# ---------------------------------------------------------------------------

EVENT_TIME = datetime(2026, 1, 15, 14, 0, 0, tzinfo=UTC)

INVERTER_ASSET = AssetLocation(
    asset_id="INV-007",
    lat=51.5,
    lon=7.2,
    asset_type="INVERTER",
    rated_mw=2.0,
)

TURBINE_ASSET = AssetLocation(
    asset_id="WT-099",
    lat=53.0,
    lon=8.5,
    asset_type="WIND_TURBINE",
    rated_mw=5.0,
)

SOLAR_ASSET = AssetLocation(
    asset_id="PV-042",
    lat=48.0,
    lon=11.0,
    asset_type="SOLAR_PV",
    rated_mw=10.0,
)


def make_engine(**kwargs) -> CVIEngine:
    return CVIEngine(run_id="test-cvi-run", ingest_run_id="test-ingest", **kwargs)


# ---------------------------------------------------------------------------
# test_low_weather_low_stress_low_cvi
# ---------------------------------------------------------------------------

class TestLowCVI:
    def test_low_weather_low_stress_low_cvi(self):
        """All benign inputs → CVI < 35 (LOW severity)."""
        engine = make_engine()
        alert = engine.score(
            asset=TURBINE_ASSET,
            weather_wind_ms=5.0,
            weather_anomaly_score=0.0,   # no anomaly
            grid_stress_mw=0.0,          # no stress
            monitoring_quality=1.0,      # full visibility
            event_time=EVENT_TIME,
        )
        assert alert.cvi_score < 35.0, f"Expected CVI < 35, got {alert.cvi_score}"
        assert alert.severity == AlertSeverity.LOW

    def test_zero_inputs_produces_minimal_cvi(self):
        """With weather=0 and stress=0 and full monitoring, CVI driven only by exposure."""
        engine = make_engine()
        alert = engine.score(
            asset=TURBINE_ASSET,
            weather_wind_ms=0.0,
            weather_anomaly_score=0.0,
            grid_stress_mw=0.0,
            monitoring_quality=1.0,
            event_time=EVENT_TIME,
        )
        # exposure_score = 70 for WIND_TURBINE → CVI = 0.25 * 70 = 17.5
        assert alert.cvi_score == pytest.approx(17.5, abs=0.1)


# ---------------------------------------------------------------------------
# test_extreme_weather_high_stress_blind_monitoring_critical
# ---------------------------------------------------------------------------

class TestCriticalCVI:
    def test_extreme_weather_high_stress_blind_monitoring_critical(self):
        """Worst-case inputs → CVI > 75, severity CRITICAL."""
        engine = make_engine()
        alert = engine.score(
            asset=INVERTER_ASSET,
            weather_wind_ms=35.0,
            weather_anomaly_score=10.0,   # maximum anomaly
            grid_stress_mw=500.0,         # full scale stress
            monitoring_quality=0.0,       # completely blind
            event_time=EVENT_TIME,
        )
        assert alert.cvi_score > 75.0, f"Expected CVI > 75, got {alert.cvi_score}"
        assert alert.severity == AlertSeverity.CRITICAL

    def test_perfect_worst_case_inverter_score_is_100(self):
        """Max inputs on INVERTER → CVI == 100."""
        engine = make_engine()
        alert = engine.score(
            asset=INVERTER_ASSET,
            weather_wind_ms=50.0,
            weather_anomaly_score=10.0,
            grid_stress_mw=1_000_000.0,   # way above full scale → clamped at 100
            monitoring_quality=0.0,
            event_time=EVENT_TIME,
        )
        # weather=100, exposure=100, stress=100, visibility=100 → CVI=100
        assert alert.cvi_score == pytest.approx(100.0, abs=0.01)


# ---------------------------------------------------------------------------
# test_inverter_scores_higher_than_turbine
# ---------------------------------------------------------------------------

class TestExposureOrdering:
    def test_inverter_scores_higher_than_turbine(self):
        """Same weather/stress/monitoring; INVERTER CVI > WIND_TURBINE CVI."""
        engine = make_engine()
        shared_kwargs = dict(
            weather_wind_ms=20.0,
            weather_anomaly_score=7.0,
            grid_stress_mw=250.0,
            monitoring_quality=0.5,
            event_time=EVENT_TIME,
        )
        inv_alert = engine.score(asset=INVERTER_ASSET, **shared_kwargs)
        wt_alert = engine.score(asset=TURBINE_ASSET, **shared_kwargs)

        assert inv_alert.cvi_score > wt_alert.cvi_score, (
            f"INVERTER ({inv_alert.cvi_score:.2f}) should > WIND_TURBINE ({wt_alert.cvi_score:.2f})"
        )

    def test_exposure_delta_equals_25_percent_of_30(self):
        """
        CVI delta between INVERTER (exposure=100) and WIND_TURBINE (exposure=70)
        equals 0.25 * (100 - 70) = 7.5 points, all else being equal.
        """
        engine = make_engine()
        shared_kwargs = dict(
            weather_wind_ms=0.0,
            weather_anomaly_score=0.0,
            grid_stress_mw=0.0,
            monitoring_quality=1.0,
            event_time=EVENT_TIME,
        )
        inv_score = engine.score(asset=INVERTER_ASSET, **shared_kwargs).cvi_score
        wt_score = engine.score(asset=TURBINE_ASSET, **shared_kwargs).cvi_score

        assert inv_score - wt_score == pytest.approx(7.5, abs=0.01)


# ---------------------------------------------------------------------------
# test_cvi_score_range_bounded
# ---------------------------------------------------------------------------

class TestCVIBounds:
    @pytest.mark.parametrize(
        "anomaly,stress,quality",
        [
            (0.0, 0.0, 1.0),
            (5.0, 250.0, 0.5),
            (10.0, 500.0, 0.0),
            (10.0, 0.0, 1.0),
            (0.0, 500.0, 0.0),
        ],
    )
    def test_cvi_score_range_bounded(self, anomaly, stress, quality):
        """CVI always ∈ [0, 100] regardless of inputs."""
        engine = make_engine()
        alert = engine.score(
            asset=INVERTER_ASSET,
            weather_wind_ms=anomaly * 3.0,
            weather_anomaly_score=anomaly,
            grid_stress_mw=stress,
            monitoring_quality=quality,
            event_time=EVENT_TIME,
        )
        assert 0.0 <= alert.cvi_score <= 100.0, (
            f"CVI out of [0,100]: {alert.cvi_score}"
        )

    def test_cvi_clamps_overshooting_stress(self):
        """grid_stress_mw >> 500 → stress_score still capped at 100."""
        engine = make_engine()
        alert = engine.score(
            asset=TURBINE_ASSET,
            weather_wind_ms=0.0,
            weather_anomaly_score=0.0,
            grid_stress_mw=999_999.0,
            monitoring_quality=1.0,
            event_time=EVENT_TIME,
        )
        assert alert.cvi_score <= 100.0


# ---------------------------------------------------------------------------
# test_contributing_factors_populated
# ---------------------------------------------------------------------------

class TestContributingFactors:
    def test_contributing_factors_populated(self):
        """CVI > 35 → contributing_factors list is non-empty."""
        engine = make_engine()
        alert = engine.score(
            asset=INVERTER_ASSET,
            weather_wind_ms=20.0,
            weather_anomaly_score=8.0,
            grid_stress_mw=300.0,
            monitoring_quality=0.3,
            event_time=EVENT_TIME,
        )
        assert alert.cvi_score > 35.0, "Pre-condition failed: CVI should exceed 35"
        assert len(alert.contributing_factors) > 0, "Expected non-empty contributing_factors"

    def test_contributing_factors_empty_for_minimal_inputs(self):
        """Pure exposure-only scenario (no weather/stress/visibility) → factors for exposure only."""
        engine = make_engine()
        alert = engine.score(
            asset=TURBINE_ASSET,
            weather_wind_ms=0.0,
            weather_anomaly_score=0.0,
            grid_stress_mw=0.0,
            monitoring_quality=1.0,
            event_time=EVENT_TIME,
        )
        # Exposure factor is always added; others may be absent
        assert isinstance(alert.contributing_factors, list)

    def test_contributing_factors_are_strings(self):
        """Each factor must be a non-empty string."""
        engine = make_engine()
        alert = engine.score(
            asset=INVERTER_ASSET,
            weather_wind_ms=30.0,
            weather_anomaly_score=9.0,
            grid_stress_mw=400.0,
            monitoring_quality=0.1,
            event_time=EVENT_TIME,
        )
        for factor in alert.contributing_factors:
            assert isinstance(factor, str) and len(factor) > 0


# ---------------------------------------------------------------------------
# test_attack_surface_window_duration_four_hours
# ---------------------------------------------------------------------------

class TestAttackSurfaceWindow:
    def test_attack_surface_window_duration_four_hours(self):
        """attack_surface_window_end - start == 4 hours for CRITICAL events."""
        engine = make_engine()
        alert = engine.score(
            asset=INVERTER_ASSET,
            weather_wind_ms=35.0,
            weather_anomaly_score=10.0,
            grid_stress_mw=500.0,
            monitoring_quality=0.0,
            event_time=EVENT_TIME,
        )
        assert alert.severity == AlertSeverity.CRITICAL, "Pre-condition: expected CRITICAL"
        duration = alert.attack_surface_window_end - alert.attack_surface_window_start
        assert duration == timedelta(hours=4), (
            f"Expected 4h window, got {duration}"
        )

    def test_attack_surface_window_duration_constant_across_severities(self):
        """Window duration is always 4h (constant regardless of severity)."""
        engine = make_engine()
        for anomaly_score in (0.0, 3.0, 7.0, 10.0):
            alert = engine.score(
                asset=INVERTER_ASSET,
                weather_wind_ms=anomaly_score * 3.0,
                weather_anomaly_score=anomaly_score,
                grid_stress_mw=anomaly_score * 50.0,
                monitoring_quality=max(0.0, 1.0 - anomaly_score / 10.0),
                event_time=EVENT_TIME,
            )
            duration = alert.attack_surface_window_end - alert.attack_surface_window_start
            assert duration == timedelta(hours=_ATTACK_WINDOW_HOURS), (
                f"Window duration wrong for anomaly_score={anomaly_score}: {duration}"
            )

    def test_attack_window_start_equals_event_time(self):
        """Window start matches the event_time passed in."""
        engine = make_engine()
        alert = engine.score(
            asset=INVERTER_ASSET,
            weather_wind_ms=30.0,
            weather_anomaly_score=10.0,
            grid_stress_mw=500.0,
            monitoring_quality=0.0,
            event_time=EVENT_TIME,
        )
        assert alert.attack_surface_window_start == EVENT_TIME


# ---------------------------------------------------------------------------
# Severity thresholds
# ---------------------------------------------------------------------------

class TestSeverityThresholds:
    @pytest.mark.parametrize(
        "anomaly,stress,quality,expected_severity",
        [
            # Low: CVI ~ 17.5 (only exposure, minimal everything else)
            (0.0, 0.0, 1.0, AlertSeverity.LOW),
            # Medium: moderate anomaly + exposure for WIND_TURBINE
            (4.0, 100.0, 0.8, AlertSeverity.MEDIUM),
            # Critical: full blast
            (10.0, 500.0, 0.0, AlertSeverity.CRITICAL),
        ],
    )
    def test_severity_thresholds(self, anomaly, stress, quality, expected_severity):
        engine = make_engine()
        alert = engine.score(
            asset=INVERTER_ASSET if expected_severity == AlertSeverity.CRITICAL else TURBINE_ASSET,
            weather_wind_ms=anomaly * 3.0,
            weather_anomaly_score=anomaly,
            grid_stress_mw=stress,
            monitoring_quality=quality,
            event_time=EVENT_TIME,
        )
        assert alert.severity == expected_severity, (
            f"For anomaly={anomaly}, stress={stress}, quality={quality}: "
            f"expected {expected_severity}, got {alert.severity} (CVI={alert.cvi_score:.2f})"
        )


# ---------------------------------------------------------------------------
# SIEM JSON
# ---------------------------------------------------------------------------

class TestSIEMJSON:
    REQUIRED_KEYS = {
        "event_type", "severity", "asset_id", "cvi_score",
        "attack_surface_window_start", "attack_surface_window_end",
        "recommended_action", "contributing_factors", "source",
    }

    def test_siem_json_has_required_fields(self):
        engine = make_engine()
        alert = engine.score(
            asset=INVERTER_ASSET,
            weather_wind_ms=25.0,
            weather_anomaly_score=8.0,
            grid_stress_mw=300.0,
            monitoring_quality=0.2,
            event_time=EVENT_TIME,
        )
        for key in self.REQUIRED_KEYS:
            assert key in alert.siem_json, f"Missing SIEM key: {key!r}"

    def test_siem_json_source(self):
        engine = make_engine()
        alert = engine.score(
            asset=INVERTER_ASSET,
            weather_wind_ms=25.0,
            weather_anomaly_score=8.0,
            grid_stress_mw=300.0,
            monitoring_quality=0.2,
            event_time=EVENT_TIME,
        )
        assert alert.siem_json["source"] == "METOC_WESF_CVI"


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------

class TestBatchScoring:
    def test_batch_score_returns_same_length_as_assets(self):
        engine = make_engine()
        assets = [INVERTER_ASSET, TURBINE_ASSET, SOLAR_ASSET]
        results = engine.batch_score(
            assets=assets,
            weather_wind_ms_list=[10.0, 20.0, 5.0],
            weather_anomaly_scores=[5.0, 8.0, 2.0],
            grid_stress_mw_list=[100.0, 400.0, 50.0],
            monitoring_quality_list=[0.8, 0.3, 1.0],
            event_time=EVENT_TIME,
        )
        assert len(results) == 3

    def test_batch_score_asset_ids_preserved(self):
        engine = make_engine()
        assets = [INVERTER_ASSET, TURBINE_ASSET]
        results = engine.batch_score(
            assets=assets,
            weather_wind_ms_list=[10.0, 10.0],
            weather_anomaly_scores=[5.0, 5.0],
            grid_stress_mw_list=[100.0, 100.0],
            monitoring_quality_list=[0.5, 0.5],
            event_time=EVENT_TIME,
        )
        result_ids = [r.asset.asset_id for r in results]
        assert result_ids == ["INV-007", "WT-099"]

    def test_batch_score_mismatched_lengths_raises(self):
        engine = make_engine()
        with pytest.raises(ValueError, match="same length"):
            engine.batch_score(
                assets=[INVERTER_ASSET, TURBINE_ASSET],
                weather_wind_ms_list=[10.0],  # wrong length
                weather_anomaly_scores=[5.0, 5.0],
                grid_stress_mw_list=[100.0, 100.0],
                monitoring_quality_list=[0.5, 0.5],
            )
