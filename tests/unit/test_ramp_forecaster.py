"""
Unit tests for src.wesf.ramp_forecaster.RampForecaster.

All tests use synthetic 3×3 numpy grids — no real data, no I/O.
"""
from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from src.api.schemas import AlertSeverity, AlertType, AssetLocation
from src.wesf.ramp_forecaster import RampForecaster

# ---------------------------------------------------------------------------
# Shared test fixtures / helpers
# ---------------------------------------------------------------------------

# A minimal 3×3 latitude / longitude grid centred on 50°N, 10°E
LAT_GRID = np.array([49.0, 50.0, 51.0])
LON_GRID = np.array([9.0, 10.0, 11.0])

# One timestamp
TS_0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
TIMESTAMPS = [TS_0]

# Asset at the centre of the grid (exact grid point — interpolation trivial)
WIND_ASSET = AssetLocation(
    asset_id="WT-001",
    lat=50.0,
    lon=10.0,
    asset_type="WIND_TURBINE",
    rated_mw=5.0,
)

SOLAR_ASSET = AssetLocation(
    asset_id="PV-001",
    lat=50.0,
    lon=10.0,
    asset_type="SOLAR_PV",
    rated_mw=4.0,
)


def _make_uniform_grids(
    wind_speed: float = 0.0,
    cloud_oktas: float = 0.0,
    *,
    u_fraction: float = 1.0,  # wind_speed = u * u_fraction (v = 0 for simplicity)
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (u10, v10, cloud_fraction) uniform 3-D arrays of shape (1, 3, 3)."""
    u10 = np.full((1, 3, 3), wind_speed * u_fraction)
    v10 = np.zeros((1, 3, 3))
    cloud = np.full((1, 3, 3), cloud_oktas)
    return u10, v10, cloud


def make_forecaster(assets=None, **kwargs) -> RampForecaster:
    if assets is None:
        assets = [WIND_ASSET]
    return RampForecaster(
        assets,
        run_id="test-run",
        ingest_run_id="test-ingest",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# test_turbine_cutout_detected_above_threshold
# ---------------------------------------------------------------------------

class TestTurbineCutoutDetected:
    def test_turbine_cutout_detected_above_threshold(self):
        """wind_speed = 26 m/s → at least one TURBINE_CUTOUT alert."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=26.0)
        forecaster = make_forecaster([WIND_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        cutout_alerts = [a for a in alerts if a.alert_type == AlertType.TURBINE_CUTOUT]
        assert len(cutout_alerts) >= 1, "Expected at least one TURBINE_CUTOUT alert"
        assert cutout_alerts[0].asset.asset_id == "WT-001"

    def test_no_alert_below_threshold(self):
        """wind_speed = 15 m/s → no alerts of any kind."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=15.0)
        forecaster = make_forecaster([WIND_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        assert alerts == [], f"Expected no alerts for 15 m/s wind, got {len(alerts)}"

    def test_alert_exactly_at_threshold(self):
        """wind_speed == cutout_ms (25 m/s) → alert fires (>= not >)."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=25.0)
        forecaster = make_forecaster([WIND_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        cutout_alerts = [a for a in alerts if a.alert_type == AlertType.TURBINE_CUTOUT]
        assert len(cutout_alerts) >= 1


# ---------------------------------------------------------------------------
# test_solar_drop_detected_at_full_overcast
# ---------------------------------------------------------------------------

class TestSolarDrop:
    def test_solar_drop_detected_at_full_overcast(self):
        """cloud = 8 oktas → SOLAR_DROP alert."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=5.0, cloud_oktas=8.0)
        forecaster = make_forecaster([SOLAR_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        solar_alerts = [a for a in alerts if a.alert_type == AlertType.SOLAR_DROP]
        assert len(solar_alerts) >= 1, "Expected SOLAR_DROP alert at 8 oktas"
        assert solar_alerts[0].unit == "oktas"

    def test_no_solar_alert_below_threshold(self):
        """cloud = 6 oktas < 7 threshold → no SOLAR_DROP."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=5.0, cloud_oktas=6.0)
        forecaster = make_forecaster([SOLAR_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        solar_alerts = [a for a in alerts if a.alert_type == AlertType.SOLAR_DROP]
        assert solar_alerts == [], f"Expected no SOLAR_DROP for 6 oktas, got {len(solar_alerts)}"

    def test_solar_drop_at_threshold_7_oktas(self):
        """cloud = 7 oktas == threshold → alert fires."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=5.0, cloud_oktas=7.0)
        forecaster = make_forecaster([SOLAR_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        solar_alerts = [a for a in alerts if a.alert_type == AlertType.SOLAR_DROP]
        assert len(solar_alerts) >= 1


# ---------------------------------------------------------------------------
# test_severity_critical_above_28ms
# ---------------------------------------------------------------------------

class TestSeverityMapping:
    def test_severity_critical_above_28ms(self):
        """wind = 30 m/s → severity CRITICAL."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=30.0)
        forecaster = make_forecaster([WIND_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        cutout_alerts = [a for a in alerts if a.alert_type == AlertType.TURBINE_CUTOUT]
        assert len(cutout_alerts) >= 1
        assert cutout_alerts[0].severity == AlertSeverity.CRITICAL

    def test_severity_high_between_25_and_28ms(self):
        """wind = 26 m/s → severity HIGH."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=26.0)
        forecaster = make_forecaster([WIND_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        cutout_alerts = [a for a in alerts if a.alert_type == AlertType.TURBINE_CUTOUT]
        assert len(cutout_alerts) >= 1
        assert cutout_alerts[0].severity == AlertSeverity.HIGH

    def test_severity_high_at_exactly_28ms(self):
        """wind = 28 m/s (not > 28) → severity HIGH."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=28.0)
        forecaster = make_forecaster([WIND_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        cutout_alerts = [a for a in alerts if a.alert_type == AlertType.TURBINE_CUTOUT]
        assert len(cutout_alerts) >= 1
        assert cutout_alerts[0].severity == AlertSeverity.HIGH

    def test_solar_severity_medium_at_7_oktas(self):
        """cloud = 7 oktas → MEDIUM."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=5.0, cloud_oktas=7.0)
        forecaster = make_forecaster([SOLAR_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        solar_alerts = [a for a in alerts if a.alert_type == AlertType.SOLAR_DROP]
        assert len(solar_alerts) >= 1
        assert solar_alerts[0].severity == AlertSeverity.MEDIUM

    def test_solar_severity_high_at_8_oktas(self):
        """cloud = 8 oktas → HIGH."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=5.0, cloud_oktas=8.0)
        forecaster = make_forecaster([SOLAR_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        solar_alerts = [a for a in alerts if a.alert_type == AlertType.SOLAR_DROP]
        assert len(solar_alerts) >= 1
        assert solar_alerts[0].severity == AlertSeverity.HIGH


# ---------------------------------------------------------------------------
# test_mw_loss_estimated
# ---------------------------------------------------------------------------

class TestMWLoss:
    def test_mw_loss_estimated_cutout(self):
        """rated_mw = 5.0, cut-out → estimated_mw_loss == 5.0."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=26.0)
        asset = AssetLocation(
            asset_id="WT-002",
            lat=50.0,
            lon=10.0,
            asset_type="WIND_TURBINE",
            rated_mw=5.0,
        )
        forecaster = make_forecaster([asset])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        cutout_alerts = [a for a in alerts if a.alert_type == AlertType.TURBINE_CUTOUT]
        assert len(cutout_alerts) >= 1
        assert cutout_alerts[0].estimated_mw_loss == pytest.approx(5.0)

    def test_mw_loss_solar_drop_proportional(self):
        """rated_mw = 4.0, cloud = 8 oktas → mw_loss = 4.0 * 8/8 = 4.0."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=5.0, cloud_oktas=8.0)
        asset = AssetLocation(
            asset_id="PV-002",
            lat=50.0,
            lon=10.0,
            asset_type="SOLAR_PV",
            rated_mw=4.0,
        )
        forecaster = make_forecaster([asset])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        solar_alerts = [a for a in alerts if a.alert_type == AlertType.SOLAR_DROP]
        assert len(solar_alerts) >= 1
        assert solar_alerts[0].estimated_mw_loss == pytest.approx(4.0)

    def test_mw_loss_none_when_rated_mw_not_set(self):
        """No rated_mw on asset → estimated_mw_loss is None."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=26.0)
        asset = AssetLocation(
            asset_id="WT-003",
            lat=50.0,
            lon=10.0,
            asset_type="WIND_TURBINE",
            rated_mw=None,
        )
        forecaster = make_forecaster([asset])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        cutout_alerts = [a for a in alerts if a.alert_type == AlertType.TURBINE_CUTOUT]
        assert len(cutout_alerts) >= 1
        assert cutout_alerts[0].estimated_mw_loss is None


# ---------------------------------------------------------------------------
# test_siem_json_has_required_fields
# ---------------------------------------------------------------------------

class TestSIEMJSON:
    REQUIRED_KEYS = {"event_type", "asset_id", "severity", "timestamp", "source"}

    def test_siem_json_has_required_fields(self):
        """SIEM JSON dict contains all mandatory keys."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=26.0)
        forecaster = make_forecaster([WIND_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        assert alerts, "Need at least one alert for SIEM JSON check"
        siem = alerts[0].siem_json
        for key in self.REQUIRED_KEYS:
            assert key in siem, f"Missing SIEM key: {key!r}"

    def test_siem_json_source_is_wesf(self):
        """SIEM JSON source field equals 'WESF_RAMP_FORECASTER'."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=26.0)
        forecaster = make_forecaster([WIND_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        assert alerts[0].siem_json["source"] == "WESF_RAMP_FORECASTER"

    def test_siem_json_alert_type_matches_payload(self):
        """SIEM JSON alert_type matches the payload enum value."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=26.0)
        forecaster = make_forecaster([WIND_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        alert = alerts[0]
        assert alert.siem_json["alert_type"] == alert.alert_type.value


# ---------------------------------------------------------------------------
# Grid interpolation
# ---------------------------------------------------------------------------

class TestInterpolation:
    def test_interpolation_off_grid_point(self):
        """Asset between grid points still produces correct alert when threshold crossed."""
        # Asset at 50.5°N, 10.5°E — midpoint between grid nodes
        asset = AssetLocation(
            asset_id="WT-OFFGRID",
            lat=50.5,
            lon=10.5,
            asset_type="WIND_TURBINE",
            rated_mw=3.0,
        )
        u10 = np.full((1, 3, 3), 30.0)
        v10 = np.zeros((1, 3, 3))
        cloud = np.zeros((1, 3, 3))

        forecaster = make_forecaster([asset])
        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        assert len(alerts) >= 1
        assert alerts[0].alert_type == AlertType.TURBINE_CUTOUT

    def test_multiple_timestamps_generate_multiple_alerts(self):
        """3 timestamps with cut-out wind → 3 separate alerts."""
        ts_list = [
            datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 15, 11, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
        ]
        u10 = np.full((3, 3, 3), 26.0)
        v10 = np.zeros((3, 3, 3))
        cloud = np.zeros((3, 3, 3))

        forecaster = make_forecaster([WIND_ASSET])
        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, ts_list)

        cutout_alerts = [a for a in alerts if a.alert_type == AlertType.TURBINE_CUTOUT]
        assert len(cutout_alerts) == 3

    def test_multiple_assets_both_trigger(self):
        """Two assets in the field, both exceed threshold → two alerts."""
        asset1 = AssetLocation(
            asset_id="WT-A", lat=49.0, lon=9.0, asset_type="WIND_TURBINE", rated_mw=2.0
        )
        asset2 = AssetLocation(
            asset_id="WT-B", lat=51.0, lon=11.0, asset_type="WIND_TURBINE", rated_mw=2.0
        )
        u10, v10, cloud = _make_uniform_grids(wind_speed=26.0)

        forecaster = make_forecaster([asset1, asset2])
        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        cutout_ids = {a.asset.asset_id for a in alerts if a.alert_type == AlertType.TURBINE_CUTOUT}
        assert "WT-A" in cutout_ids
        assert "WT-B" in cutout_ids


# ---------------------------------------------------------------------------
# Time window integrity
# ---------------------------------------------------------------------------

class TestTimeWindow:
    def test_time_window_end_after_start(self):
        """time_window_end > time_window_start for every alert."""
        u10, v10, cloud = _make_uniform_grids(wind_speed=26.0)
        forecaster = make_forecaster([WIND_ASSET])

        alerts = forecaster.forecast(u10, v10, cloud, LAT_GRID, LON_GRID, TIMESTAMPS)

        for alert in alerts:
            assert alert.time_window_end > alert.time_window_start


# ---------------------------------------------------------------------------
# 2D input handling (single-timestep arrays without batch dimension)
# ---------------------------------------------------------------------------

class TestRampForecaster2DInput:
    """Tests for the 2D → 3D input expansion path (lines 134-143)."""

    def test_2d_wind_array_accepted(self):
        """2D (ny, nx) arrays (single timestep) are expanded and processed."""
        import datetime

        import numpy as np

        from src.api.schemas import AssetLocation
        from src.wesf.ramp_forecaster import RampForecaster

        lat = np.linspace(35.0, 38.0, 4)
        lon = np.linspace(13.0, 17.0, 4)
        # 2D arrays (no time dimension) — above cut-out threshold
        u10_2d = np.full((4, 4), 27.0, dtype=float)
        v10_2d = np.zeros((4, 4), dtype=float)
        cloud_2d = np.zeros((4, 4), dtype=float)

        assets = [AssetLocation(asset_id="T2D", lon=15.0, lat=36.5,
                                asset_type="WIND_TURBINE", rated_mw=5.0)]
        forecaster = RampForecaster(assets=assets)
        ts = [datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)]

        alerts = forecaster.forecast(u10_2d, v10_2d, cloud_2d, lat, lon, ts)
        # Should detect the cut-out with 2D input
        assert any(a.alert_type.value == "TURBINE_CUTOUT" for a in alerts)

    def test_2d_shape_mismatch_raises(self):
        """Mismatched first axis (timesteps vs arrays) raises ValueError."""
        import datetime

        import numpy as np

        from src.api.schemas import AssetLocation
        from src.wesf.ramp_forecaster import RampForecaster

        lat = np.linspace(35.0, 38.0, 4)
        lon = np.linspace(13.0, 17.0, 4)
        # 3D arrays with 2 timesteps, but only 1 timestamp provided
        u10_3d = np.ones((2, 4, 4), dtype=float) * 10.0
        v10_3d = np.zeros((2, 4, 4), dtype=float)
        cloud_3d = np.zeros((2, 4, 4), dtype=float)

        assets = [AssetLocation(asset_id="T3D", lon=15.0, lat=36.5,
                                asset_type="WIND_TURBINE", rated_mw=5.0)]
        forecaster = RampForecaster(assets=assets)
        ts = [datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)]  # only 1

        with pytest.raises(ValueError, match="u10 leading axis"):
            forecaster.forecast(u10_3d, v10_3d, cloud_3d, lat, lon, ts)
