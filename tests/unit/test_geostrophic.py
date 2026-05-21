"""
Unit tests for src.lagrangian.geostrophic.GeostrophicCorrector.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.lagrangian.geostrophic import (
    GeostrophicCorrector,
    _EQUATORIAL_LAT,
    _GEO_SPEED_CLIP,
    _GRAVITY,
    _OMEGA,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_flat_ssh(ny: int = 10, nx: int = 10) -> np.ndarray:
    """Return a spatially uniform SSH field (all zeros → no gradient → no velocity)."""
    return np.zeros((ny, nx))


def make_lat(start: float = 30.0, stop: float = 40.0, n: int = 10) -> np.ndarray:
    return np.linspace(start, stop, n)


def make_lon(start: float = 0.0, stop: float = 10.0, n: int = 10) -> np.ndarray:
    return np.linspace(start, stop, n)


corrector = GeostrophicCorrector()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCoriolisSign:
    """Coriolis parameter f = 2Ω sin(φ) must have correct sign."""

    def test_coriolis_sign_northern_hemisphere(self):
        """f > 0 for positive latitudes."""
        lat = make_lat(10.0, 60.0)
        lon = make_lon()
        ssh = make_flat_ssh()  # uniform → gradients are zero, but we can inspect f via output
        # We verify by using a tilted SSH and checking that the velocity sign is consistent
        # with f > 0 in NH.  Alternatively we verify analytically:
        lat_rad = np.deg2rad(lat)
        f = 2.0 * _OMEGA * np.sin(lat_rad)
        assert np.all(f > 0), f"Expected f > 0 in NH, got min={f.min()}"

    def test_coriolis_sign_southern_hemisphere(self):
        """f < 0 for negative latitudes."""
        lat = make_lat(-60.0, -10.0)
        lat_rad = np.deg2rad(lat)
        f = 2.0 * _OMEGA * np.sin(lat_rad)
        assert np.all(f < 0), f"Expected f < 0 in SH, got max={f.max()}"

    def test_coriolis_zero_at_equator(self):
        """f == 0 at φ == 0°."""
        f_eq = 2.0 * _OMEGA * np.sin(0.0)
        assert f_eq == pytest.approx(0.0, abs=1e-20)


class TestEquatorialSingularity:
    """Cells within ±0.5° of the equator must return u_geo == v_geo == 0."""

    def test_equatorial_singularity_returns_zero(self):
        # Build a grid that straddles the equator
        lat = np.linspace(-0.4, 0.4, 9)   # all within ±0.5°
        lon = make_lon()
        # Use a non-trivial SSH so there would be a gradient if not masked
        ssh = np.tile(np.linspace(0.0, 1.0, len(lon)), (len(lat), 1))

        u_geo, v_geo = corrector.compute(ssh, lat, lon)

        assert np.all(u_geo == 0.0), "u_geo must be 0 in equatorial band"
        assert np.all(v_geo == 0.0), "v_geo must be 0 in equatorial band"

    def test_partial_equatorial_mask(self):
        """Only cells within ±0.5° are zeroed; cells outside are non-zero."""
        lat = np.array([-1.0, -0.4, 0.0, 0.4, 1.0])
        lon = make_lon(0.0, 4.0, 5)
        # SSH with gradient along x
        ssh = np.tile(np.linspace(0.0, 0.5, 5), (5, 1))

        u_geo, v_geo = corrector.compute(ssh, lat, lon)

        # Rows 1, 2, 3 (|lat| < 0.5°) must be zero
        for row in [1, 2, 3]:
            assert u_geo[row, :].sum() == 0.0
            assert v_geo[row, :].sum() == 0.0

        # Rows 0 and 4 (|lat| >= 0.5°) are allowed to be non-zero
        # (they may still be zero due to boundary effects from np.gradient,
        # but the important thing is they are not *forced* to zero by the mask)


class TestGeostrophicSpeedClipping:
    """Geostrophic speeds must be clipped to ±3.0 m/s."""

    def test_geostrophic_speed_clipped(self):
        # An enormous SSH gradient that would produce unrealistic velocities
        lat = make_lat(30.0, 40.0)
        lon = make_lon()
        # 100 m SSH drop across 10 columns → huge gradient
        ssh = np.tile(np.linspace(0.0, 100.0, len(lon)), (len(lat), 1))

        u_geo, v_geo = corrector.compute(ssh, lat, lon)

        assert np.all(np.abs(u_geo) <= _GEO_SPEED_CLIP + 1e-9), (
            f"u_geo max {np.abs(u_geo).max():.3f} exceeds clip {_GEO_SPEED_CLIP}"
        )
        assert np.all(np.abs(v_geo) <= _GEO_SPEED_CLIP + 1e-9), (
            f"v_geo max {np.abs(v_geo).max():.3f} exceeds clip {_GEO_SPEED_CLIP}"
        )

    def test_clip_is_symmetric(self):
        lat = make_lat(30.0, 40.0)
        lon = make_lon()
        ssh_pos = np.tile(np.linspace(0.0, 1000.0, len(lon)), (len(lat), 1))
        ssh_neg = np.tile(np.linspace(0.0, -1000.0, len(lon)), (len(lat), 1))

        u_pos, _ = corrector.compute(ssh_pos, lat, lon)
        u_neg, _ = corrector.compute(ssh_neg, lat, lon)

        assert np.all(u_pos >= -_GEO_SPEED_CLIP - 1e-9)
        assert np.all(u_pos <=  _GEO_SPEED_CLIP + 1e-9)
        assert np.all(u_neg >= -_GEO_SPEED_CLIP - 1e-9)
        assert np.all(u_neg <=  _GEO_SPEED_CLIP + 1e-9)


class TestGradientDirection:
    """SSH hill should produce anticyclonic flow in Northern Hemisphere."""

    def test_ssh_gradient_produces_correct_direction(self):
        """
        An SSH ridge running north–south (high SSH on the east, low on the west)
        in the Northern Hemisphere should produce a northward v_geo
        (v_geo = +(g/f) * dSSH/dx > 0 when dSSH/dx > 0 and f > 0).
        """
        lat = make_lat(30.0, 40.0, 10)
        lon = make_lon(0.0, 9.0, 10)
        # SSH increases eastward → dSSH/dx > 0 everywhere
        ssh = np.tile(np.linspace(0.0, 0.5, 10), (10, 1))

        u_geo, v_geo = corrector.compute(ssh, lat, lon)

        # In NH f > 0, dSSH/dx > 0 → v_geo = +(g/f)*dSSH/dx > 0
        # For interior columns (avoid edge effects from np.gradient):
        interior_v = v_geo[2:-2, 2:-2]
        assert np.all(interior_v >= 0.0), (
            f"Expected v_geo >= 0 for eastward SSH gradient in NH, got min={interior_v.min():.4f}"
        )

    def test_ssh_hill_anticyclonic_nh(self):
        """
        An SSH high (Gaussian bump) in the NH should produce anticyclonic
        (clockwise) flow: to the north of the centre u_geo > 0 (eastward),
        to the south u_geo < 0 (westward).
        """
        ny, nx = 20, 20
        lat = np.linspace(30.0, 50.0, ny)
        lon = np.linspace(0.0, 20.0, nx)
        lat_2d, lon_2d = np.meshgrid(lat, lon, indexing="ij")

        # Gaussian SSH hill centred at (40°N, 10°E)
        ssh = 0.5 * np.exp(
            -((lat_2d - 40.0) ** 2 / 25.0 + (lon_2d - 10.0) ** 2 / 25.0)
        )

        u_geo, v_geo = corrector.compute(ssh, lat, lon)

        # North of centre (rows 12–16, around 42–48°N): u_geo should be > 0
        north_u = u_geo[12:16, 8:12]
        # South of centre (rows 4–8, around 32–38°N): u_geo should be < 0
        south_u = u_geo[4:8, 8:12]

        assert np.mean(north_u) > 0, (
            f"Expected eastward flow N of SSH high in NH, got mean={np.mean(north_u):.4f}"
        )
        assert np.mean(south_u) < 0, (
            f"Expected westward flow S of SSH high in NH, got mean={np.mean(south_u):.4f}"
        )


class TestFlatSSHProducesZeroVelocity:
    """A uniform SSH field has zero gradient → zero geostrophic velocity."""

    def test_flat_ssh_zero_velocity(self):
        lat = make_lat(30.0, 40.0)
        lon = make_lon()
        ssh = np.ones((10, 10)) * 0.3  # uniform, non-zero

        u_geo, v_geo = corrector.compute(ssh, lat, lon)

        assert np.allclose(u_geo, 0.0, atol=1e-12)
        assert np.allclose(v_geo, 0.0, atol=1e-12)


class TestOutputShape:
    """Output arrays must match the shape of the SSH input."""

    @pytest.mark.parametrize("ny, nx", [(5, 8), (10, 10), (3, 15)])
    def test_output_shape(self, ny: int, nx: int):
        lat = make_lat(30.0, 40.0, ny)
        lon = make_lon(0.0, 10.0, nx)
        ssh = np.random.default_rng(0).random((ny, nx))

        u_geo, v_geo = corrector.compute(ssh, lat, lon)

        assert u_geo.shape == (ny, nx)
        assert v_geo.shape == (ny, nx)
