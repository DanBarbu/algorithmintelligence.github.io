"""
Unit tests for src.lagrangian.drift_corridor.DriftCorridor.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from src.api.schemas import DriftCorridorResult, ParticleTrack
from src.lagrangian.drift_corridor import DriftCorridor
from src.lagrangian.monte_carlo import MonteCarloEnsemble


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_track(pid: int, positions: list[list[float]]) -> ParticleTrack:
    return ParticleTrack(
        particle_id=pid,
        positions=positions,
        final_position=positions[-1],
    )


def _make_spread_tracks(n: int = 50, spread: float = 1.0) -> list[ParticleTrack]:
    """Return n tracks whose final positions are spread over a ±spread° box."""
    rng = np.random.default_rng(0)
    tracks = []
    for pid in range(n):
        lon = 5.0 + rng.uniform(-spread, spread)
        lat = 55.0 + rng.uniform(-spread, spread)
        # 24 intermediate positions (arbitrary) ending at (lon, lat)
        positions = [[5.0, 55.0]] * 23 + [[lon, lat]]
        tracks.append(_make_track(pid, positions))
    return tracks


corridor_builder = DriftCorridor()


def _build(tracks: list[ParticleTrack], **kwargs) -> DriftCorridorResult:
    return corridor_builder.build(
        tracks,
        forecast_hours=24,
        run_id="test-run-id",
        ingest_run_id="ingest-run-id",
        origin=[5.0, 55.0],
        leeway_pct=2.5,
        seed=42,
        timestep_hours=1.0,
        compute_time_seconds=0.5,
        **kwargs,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGeoJSONPolygonType:
    """The corridor_geojson field must always be a GeoJSON Polygon."""

    def test_geojson_polygon_type(self):
        tracks = _make_spread_tracks(n=50, spread=1.0)
        result = _build(tracks)
        assert result.corridor_geojson["type"] == "Polygon", (
            f"Expected 'Polygon', got '{result.corridor_geojson['type']}'"
        )

    def test_geojson_has_coordinates_key(self):
        tracks = _make_spread_tracks(n=30)
        result = _build(tracks)
        assert "coordinates" in result.corridor_geojson

    def test_geojson_ring_is_closed(self):
        """GeoJSON Polygon exterior ring must start and end at the same point."""
        tracks = _make_spread_tracks(n=30)
        result = _build(tracks)
        ring = result.corridor_geojson["coordinates"][0]
        assert ring[0] == ring[-1], "Exterior ring must be closed (first == last)"


class TestCorridorAreaPositive:
    """Corridor area must be strictly positive for a non-degenerate particle cloud."""

    def test_corridor_area_positive(self):
        tracks = _make_spread_tracks(n=50, spread=1.0)
        result = _build(tracks)
        assert result.corridor_area_km2 > 0.0, (
            f"Expected positive area, got {result.corridor_area_km2}"
        )

    def test_larger_spread_larger_area(self):
        """Wider particle spread → larger corridor area."""
        tracks_narrow = _make_spread_tracks(n=100, spread=0.1)
        tracks_wide   = _make_spread_tracks(n=100, spread=2.0)

        result_narrow = _build(tracks_narrow)
        result_wide   = _build(tracks_wide)

        assert result_wide.corridor_area_km2 > result_narrow.corridor_area_km2, (
            f"Wide spread ({result_wide.corridor_area_km2:.2f} km²) should be larger "
            f"than narrow ({result_narrow.corridor_area_km2:.2f} km²)"
        )

    def test_area_units_are_reasonable(self):
        """For a ~1° × 1° spread at 55°N, area should be in the hundreds of km²."""
        tracks = _make_spread_tracks(n=200, spread=1.0)
        result = _build(tracks)
        # Very loose bounds: should be between 1 km² and 100,000 km²
        assert 1.0 < result.corridor_area_km2 < 100_000.0, (
            f"Corridor area {result.corridor_area_km2:.2f} km² seems unreasonable"
        )


class TestCentroidWithinBoundingBox:
    """The centroid must lie inside the bounding box of the particle spread."""

    def test_centroid_within_bounding_box(self):
        tracks = _make_spread_tracks(n=50, spread=1.0)
        result = _build(tracks)

        final_lons = [t.final_position[0] for t in tracks]
        final_lats = [t.final_position[1] for t in tracks]

        lon_min, lon_max = min(final_lons), max(final_lons)
        lat_min, lat_max = min(final_lats), max(final_lats)

        c_lon, c_lat = result.centroid

        assert lon_min <= c_lon <= lon_max, (
            f"Centroid lon {c_lon:.4f} outside [{lon_min:.4f}, {lon_max:.4f}]"
        )
        assert lat_min <= c_lat <= lat_max, (
            f"Centroid lat {c_lat:.4f} outside [{lat_min:.4f}, {lat_max:.4f}]"
        )

    def test_centroid_list_length(self):
        tracks = _make_spread_tracks(n=20)
        result = _build(tracks)
        assert len(result.centroid) == 2


class TestSingleParticleDegradesGracefully:
    """
    Degenerate geometry cases — DriftCorridorResult requires n_particles >= 10,
    so we use 10 tracks whose *final positions* are all coincident or co-linear.
    The corridor builder must handle the resulting Point / LineString hull without
    crashing and must always return a GeoJSON Polygon.
    """

    def test_single_particle_degenerates_gracefully(self):
        """
        10 particles all ending at the same point → Point hull internally,
        but corridor_geojson must be a Polygon (buffered).
        """
        # All 10 particles share the same final position
        tracks = [
            _make_track(pid, [[5.0, 55.0]] * 23 + [[5.1, 55.1]])
            for pid in range(10)
        ]
        # Should not raise
        result = _build(tracks)

        assert result.corridor_geojson["type"] == "Polygon"
        assert result.corridor_area_km2 >= 0.0
        assert len(result.centroid) == 2

    def test_coincident_particles_no_crash(self):
        """All 10 particles at exactly the same position → degenerate Point hull."""
        pos = [5.0, 55.0]
        tracks = [
            _make_track(pid, [[5.0, 55.0]] * 23 + [pos])
            for pid in range(10)
        ]
        result = _build(tracks)
        assert result.corridor_geojson["type"] == "Polygon"

    def test_two_coincident_particles(self):
        """
        10 particles all coincident — the convex hull degenerates to a Point.
        After buffering the result must still be a valid Polygon.
        """
        pos = [5.2, 55.3]
        tracks = [
            _make_track(pid, [[5.0, 55.0]] * 23 + [pos])
            for pid in range(10)
        ]
        result = _build(tracks)
        assert result.corridor_geojson["type"] == "Polygon"


class TestMetadataPassThrough:
    """Metadata fields must be copied faithfully into the result."""

    def test_run_id_preserved(self):
        tracks = _make_spread_tracks(n=20)
        result = _build(tracks)
        assert result.run_id == "test-run-id"

    def test_n_particles_matches(self):
        n = 37
        tracks = _make_spread_tracks(n=n)
        result = _build(tracks)
        assert result.n_particles == n

    def test_forecast_hours_preserved(self):
        tracks = _make_spread_tracks(n=20)
        result = corridor_builder.build(
            tracks,
            forecast_hours=48,
            run_id="r",
            ingest_run_id="i",
            origin=[5.0, 55.0],
            leeway_pct=2.5,
            seed=42,
            timestep_hours=1.0,
            compute_time_seconds=0.0,
        )
        assert result.forecast_hours == 48


class TestEndToEndWithMonteCarlo:
    """Integration smoke-test: run a full ensemble and build the corridor."""

    def test_full_pipeline_no_crash(self):
        ens = MonteCarloEnsemble(n_particles=50, seed=42)
        tracks = ens.run(
            origin_lon=5.0,
            origin_lat=55.0,
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

        result = corridor_builder.build(
            tracks,
            forecast_hours=24,
            run_id="smoke-test",
            ingest_run_id="ingest-123",
            origin=[5.0, 55.0],
            leeway_pct=2.5,
            seed=42,
            timestep_hours=1.0,
            compute_time_seconds=0.1,
        )

        assert isinstance(result, DriftCorridorResult)
        assert result.corridor_geojson["type"] == "Polygon"
        assert result.corridor_area_km2 >= 0.0
        assert len(result.particle_tracks) == 50
