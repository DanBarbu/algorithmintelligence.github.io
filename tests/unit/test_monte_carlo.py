"""
Unit tests for src.lagrangian.monte_carlo.MonteCarloEnsemble.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.api.schemas import ParticleTrack
from src.lagrangian.monte_carlo import MonteCarloEnsemble

# ── Shared fixtures & helpers ─────────────────────────────────────────────────

ORIGIN_LON = 5.0
ORIGIN_LAT = 55.0
DEFAULT_KWARGS = dict(
    origin_lon=ORIGIN_LON,
    origin_lat=ORIGIN_LAT,
    u_current=0.1,
    v_current=0.05,
    u_wind=5.0,
    v_wind=2.0,
    u_geo=0.02,
    v_geo=0.01,
    leeway_pct=2.5,
    dt_hours=1.0,
    n_steps=24,
)


def _run_ensemble(seed: int = 42, n_particles: int = 100, **overrides) -> list[ParticleTrack]:
    kwargs = dict(DEFAULT_KWARGS)
    kwargs.update(overrides)
    ens = MonteCarloEnsemble(n_particles=n_particles, seed=seed)
    return ens.run(**kwargs)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDeterministicSeedReproducibility:
    """Running with the same seed twice must produce bit-for-bit identical results."""

    def test_deterministic_seed_reproducibility(self):
        tracks_a = _run_ensemble(seed=42)
        tracks_b = _run_ensemble(seed=42)

        assert len(tracks_a) == len(tracks_b)
        for ta, tb in zip(tracks_a, tracks_b):
            assert ta.particle_id == tb.particle_id
            assert ta.final_position == tb.final_position
            assert len(ta.positions) == len(tb.positions)
            for pos_a, pos_b in zip(ta.positions, tb.positions):
                assert pos_a[0] == pytest.approx(pos_b[0], rel=1e-12)
                assert pos_a[1] == pytest.approx(pos_b[1], rel=1e-12)


class TestParticleCount:
    """len(tracks) must equal n_particles exactly."""

    @pytest.mark.parametrize("n", [10, 50, 100, 200])
    def test_particle_count(self, n: int):
        tracks = _run_ensemble(n_particles=n)
        assert len(tracks) == n

    def test_particle_ids_are_sequential(self):
        tracks = _run_ensemble(n_particles=20)
        ids = [t.particle_id for t in tracks]
        assert ids == list(range(20))


class TestParticleTrackLength:
    """Each track must contain exactly n_steps positions."""

    @pytest.mark.parametrize("n_steps", [1, 6, 12, 24, 48])
    def test_particle_track_length(self, n_steps: int):
        tracks = _run_ensemble(n_steps=n_steps)
        for track in tracks:
            assert len(track.positions) == n_steps, (
                f"particle {track.particle_id}: expected {n_steps} steps, "
                f"got {len(track.positions)}"
            )

    def test_final_position_matches_last_step(self):
        tracks = _run_ensemble(n_steps=24)
        for track in tracks:
            assert track.final_position == track.positions[-1]


class TestNoiseSpreadIncreasesVariance:
    """Ensemble standard deviation of final positions must be > 0."""

    def test_noise_spread_increases_variance(self):
        tracks = _run_ensemble(n_particles=100, n_steps=24)
        final_lons = np.array([t.final_position[0] for t in tracks])
        final_lats = np.array([t.final_position[1] for t in tracks])

        assert np.std(final_lons) > 0.0, "All final longitudes are identical — noise is broken"
        assert np.std(final_lats) > 0.0, "All final latitudes are identical — noise is broken"

    def test_variance_grows_with_sigma(self):
        """Higher noise → larger spread."""
        def _run_with_sigma(current_sigma: float, wind_sigma: float) -> list:
            ens = MonteCarloEnsemble(
                n_particles=100,
                seed=42,
                current_sigma=current_sigma,
                wind_sigma=wind_sigma,
            )
            return ens.run(**DEFAULT_KWARGS)

        low_sigma_tracks  = _run_with_sigma(current_sigma=0.001, wind_sigma=0.01)
        high_sigma_tracks = _run_with_sigma(current_sigma=0.5,   wind_sigma=5.0)

        std_low  = np.std([t.final_position[0] for t in low_sigma_tracks])
        std_high = np.std([t.final_position[0] for t in high_sigma_tracks])

        assert std_high > std_low, "Higher σ should produce wider ensemble spread"


class TestDifferentSeedsDifferentResults:
    """Different seeds must produce measurably different particle paths."""

    def test_different_seeds_produce_different_results(self):
        tracks_42 = _run_ensemble(seed=42,  n_particles=10)
        tracks_99 = _run_ensemble(seed=99,  n_particles=10)

        # At least one track must differ in final position
        any_different = any(
            ta.final_position != tb.final_position
            for ta, tb in zip(tracks_42, tracks_99)
        )
        assert any_different, "Seeds 42 and 99 produced identical tracks — RNG seeding is broken"


class TestLeewayEffect:
    """Higher leeway_pct must shift the ensemble mean in the downwind direction."""

    def test_leeway_effect(self):
        # Use a strong, pure-eastward wind so the leeway shift is unambiguous.
        kwargs = dict(
            DEFAULT_KWARGS,
            u_current=0.0,
            v_current=0.0,
            u_geo=0.0,
            v_geo=0.0,
            u_wind=10.0,  # strong eastward wind
            v_wind=0.0,
            n_steps=24,
        )

        low_tracks  = _run_ensemble(n_particles=200, leeway_pct=1.0, **{k: v for k, v in kwargs.items() if k != 'leeway_pct'})
        high_tracks = _run_ensemble(n_particles=200, leeway_pct=5.0, **{k: v for k, v in kwargs.items() if k != 'leeway_pct'})

        # Helper to compute per-run kwargs with explicit leeway_pct
        def _run_with_leeway(leeway_pct: float) -> list[ParticleTrack]:
            ens = MonteCarloEnsemble(n_particles=200, seed=42)
            return ens.run(
                origin_lon=ORIGIN_LON,
                origin_lat=ORIGIN_LAT,
                u_current=0.0,
                v_current=0.0,
                u_wind=10.0,
                v_wind=0.0,
                u_geo=0.0,
                v_geo=0.0,
                leeway_pct=leeway_pct,
                dt_hours=1.0,
                n_steps=24,
            )

        low_tracks  = _run_with_leeway(1.0)
        high_tracks = _run_with_leeway(5.0)

        mean_lon_low  = np.mean([t.final_position[0] for t in low_tracks])
        mean_lon_high = np.mean([t.final_position[0] for t in high_tracks])

        # Wind is eastward → high leeway drifts further east (higher longitude)
        assert mean_lon_high > mean_lon_low, (
            f"High leeway ({mean_lon_high:.6f}) should be east of low leeway ({mean_lon_low:.6f})"
        )


class TestEdgeCases:
    """Edge cases and input validation."""

    def test_n_particles_below_minimum_raises(self):
        with pytest.raises(ValueError, match="n_particles"):
            MonteCarloEnsemble(n_particles=5)

    def test_invalid_leeway_pct_raises(self):
        ens = MonteCarloEnsemble(n_particles=10, seed=0)
        with pytest.raises(ValueError, match="leeway_pct"):
            ens.run(**{**DEFAULT_KWARGS, "leeway_pct": 0.5})

    def test_invalid_leeway_pct_high_raises(self):
        ens = MonteCarloEnsemble(n_particles=10, seed=0)
        with pytest.raises(ValueError, match="leeway_pct"):
            ens.run(**{**DEFAULT_KWARGS, "leeway_pct": 6.0})

    def test_single_step(self):
        tracks = _run_ensemble(n_steps=1)
        for t in tracks:
            assert len(t.positions) == 1
            assert t.final_position == t.positions[0]

    def test_positions_are_valid_coordinates(self):
        tracks = _run_ensemble(n_particles=50, n_steps=24)
        for track in tracks:
            for lon, lat in track.positions:
                # Should stay in plausible ocean range for short drift
                assert -360 <= lon <= 360, f"Longitude {lon} out of range"
                assert -90 <= lat <= 90, f"Latitude {lat} out of range"
