"""
Unit tests for src.lagrangian.buoy_model.BuoyLeewayModel.

All tests exercise the numpy fallback solver path (OpenDrift not installed in CI).
The class is fully testable without OpenDrift because the import is guarded.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.lagrangian.buoy_model import OPENDRIFT_AVAILABLE, BuoyLeewayModel


class TestBuoyLeewayModelInit:
    """Constructor validation and attribute initialisation."""

    def test_default_construction(self):
        """Default parameters create a valid model."""
        model = BuoyLeewayModel()
        assert model.leeway_pct == 2.5
        assert model.cross_section_m2 == 0.1
        assert model.seed is not None

    def test_custom_parameters(self):
        """Custom leeway and cross-section stored correctly."""
        model = BuoyLeewayModel(leeway_pct=3.0, cross_section_m2=0.5, seed=99)
        assert model.leeway_pct == 3.0
        assert model.cross_section_m2 == 0.5
        assert model.seed == 99

    def test_leeway_boundary_low(self):
        """Minimum valid leeway (1.0 %) accepted."""
        model = BuoyLeewayModel(leeway_pct=1.0, seed=1)
        assert model.leeway_pct == 1.0

    def test_leeway_boundary_high(self):
        """Maximum valid leeway (5.0 %) accepted."""
        model = BuoyLeewayModel(leeway_pct=5.0, seed=1)
        assert model.leeway_pct == 5.0

    def test_leeway_too_low_raises(self):
        """leeway_pct < 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="leeway_pct"):
            BuoyLeewayModel(leeway_pct=0.5)

    def test_leeway_too_high_raises(self):
        """leeway_pct > 5.0 raises ValueError."""
        with pytest.raises(ValueError, match="leeway_pct"):
            BuoyLeewayModel(leeway_pct=5.1)

    def test_seed_none_uses_settings_seed(self):
        """seed=None falls back to get_settings().seed (42 by default)."""
        model = BuoyLeewayModel(seed=None)
        assert isinstance(model.seed, int)

    def test_rng_is_seeded(self):
        """Two models with the same seed produce the same RNG state."""
        m1 = BuoyLeewayModel(seed=42)
        m2 = BuoyLeewayModel(seed=42)
        # Draw one sample from each; should be identical
        v1 = m1._rng.standard_normal()
        v2 = m2._rng.standard_normal()
        assert v1 == v2

    def test_opendrift_flag_is_bool(self):
        """OPENDRIFT_AVAILABLE is a boolean (True if installed, False otherwise)."""
        assert isinstance(OPENDRIFT_AVAILABLE, bool)


class TestConfigureLeeway:
    """Tests for the configure_leeway() method."""

    def test_leeway_scales_wind_scalar(self):
        """Scalar wind → leeway = leeway_pct/100 * wind."""
        model = BuoyLeewayModel(leeway_pct=2.0, seed=0)
        lu, lv = model.configure_leeway(
            wind_u=np.array([10.0]),
            wind_v=np.array([5.0]),
        )
        assert np.isclose(lu[0], 0.02 * 10.0)
        assert np.isclose(lv[0], 0.02 * 5.0)

    def test_leeway_scales_wind_array(self):
        """2D wind array → element-wise leeway scaling."""
        model = BuoyLeewayModel(leeway_pct=5.0, seed=0)
        wind_u = np.array([[4.0, 8.0], [2.0, 6.0]])
        wind_v = np.zeros_like(wind_u)
        lu, lv = model.configure_leeway(wind_u, wind_v)
        expected_u = 0.05 * wind_u
        assert np.allclose(lu, expected_u)
        assert np.allclose(lv, 0.0)

    def test_leeway_output_shape_matches_input(self):
        """Output shape equals input shape."""
        model = BuoyLeewayModel(leeway_pct=1.0, seed=0)
        shape = (3, 4)
        wu = np.random.default_rng(0).standard_normal(shape)
        wv = np.random.default_rng(1).standard_normal(shape)
        lu, lv = model.configure_leeway(wu, wv)
        assert lu.shape == shape
        assert lv.shape == shape

    def test_leeway_zero_wind_gives_zero_leeway(self):
        """Zero wind → zero leeway."""
        model = BuoyLeewayModel(leeway_pct=3.0, seed=0)
        lu, lv = model.configure_leeway(np.zeros(5), np.zeros(5))
        assert np.all(lu == 0.0)
        assert np.all(lv == 0.0)

    def test_leeway_negative_wind(self):
        """Negative wind components produce negative leeway."""
        model = BuoyLeewayModel(leeway_pct=2.5, seed=0)
        lu, lv = model.configure_leeway(
            np.array([-10.0]),
            np.array([-5.0]),
        )
        assert lu[0] < 0.0
        assert lv[0] < 0.0

    def test_different_leeway_pct_gives_different_output(self):
        """Higher leeway_pct → larger leeway magnitude."""
        wu = np.array([10.0])
        wv = np.array([10.0])
        m_low = BuoyLeewayModel(leeway_pct=1.0, seed=0)
        m_high = BuoyLeewayModel(leeway_pct=5.0, seed=0)
        lu_low, _ = m_low.configure_leeway(wu, wv)
        lu_high, _ = m_high.configure_leeway(wu, wv)
        assert lu_high[0] > lu_low[0]


class TestRunFallback:
    """Tests for the numpy Euler-integration fallback solver."""

    def test_returns_lists(self):
        """run_fallback returns (list[float], list[float])."""
        model = BuoyLeewayModel(seed=0)
        n = 5
        u = np.ones(n) * 0.5
        v = np.zeros(n)
        lons, lats = model.run_fallback(14.5, 36.8, u, v, dt_seconds=3600.0)
        assert isinstance(lons, list)
        assert isinstance(lats, list)

    def test_output_length_matches_timesteps(self):
        """One position per timestep (not including origin)."""
        model = BuoyLeewayModel(seed=0)
        n = 24
        u = np.random.default_rng(1).standard_normal(n)
        v = np.random.default_rng(2).standard_normal(n)
        lons, lats = model.run_fallback(14.5, 36.8, u, v, dt_seconds=3600.0)
        assert len(lons) == n
        assert len(lats) == n

    def test_zero_velocity_stays_at_origin(self):
        """Zero velocity → all positions equal origin."""
        model = BuoyLeewayModel(seed=0)
        n = 10
        lons, lats = model.run_fallback(
            14.5, 36.8,
            np.zeros(n), np.zeros(n),
            dt_seconds=3600.0,
        )
        assert all(np.isclose(lon, 14.5) for lon in lons)
        assert all(np.isclose(lat, 36.8) for lat in lats)

    def test_positive_u_moves_east(self):
        """Eastward current → longitude increases monotonically."""
        model = BuoyLeewayModel(seed=0)
        n = 6
        lons, _ = model.run_fallback(
            14.5, 36.8,
            np.ones(n) * 1.0,  # 1 m/s east
            np.zeros(n),
            dt_seconds=3600.0,
        )
        for i in range(1, n):
            assert lons[i] > lons[i - 1], "Expected eastward monotonic drift"

    def test_positive_v_moves_north(self):
        """Northward current → latitude increases monotonically."""
        model = BuoyLeewayModel(seed=0)
        n = 6
        _, lats = model.run_fallback(
            14.5, 36.8,
            np.zeros(n),
            np.ones(n) * 1.0,  # 1 m/s north
            dt_seconds=3600.0,
        )
        for i in range(1, n):
            assert lats[i] > lats[i - 1], "Expected northward monotonic drift"

    def test_positions_are_floats(self):
        """All returned positions are Python floats."""
        model = BuoyLeewayModel(seed=0)
        lons, lats = model.run_fallback(0.0, 0.0, np.array([0.1]), np.array([0.1]), 3600.0)
        assert all(isinstance(v, float) for v in lons)
        assert all(isinstance(v, float) for v in lats)

    def test_determinism_with_same_inputs(self):
        """Same inputs → identical outputs (no stochastic elements in fallback)."""
        model = BuoyLeewayModel(seed=42)
        u = np.array([0.2, -0.1, 0.3])
        v = np.array([0.1, 0.2, -0.1])
        lons1, lats1 = model.run_fallback(14.0, 37.0, u, v, 3600.0)
        lons2, lats2 = model.run_fallback(14.0, 37.0, u, v, 3600.0)
        assert lons1 == lons2
        assert lats1 == lats2
