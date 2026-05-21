"""Shared pytest fixtures for all test modules."""
from __future__ import annotations

import datetime
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.api.schemas import (
    AssetLocation,
    DriftCorridorResult,
    ParticleTrack,
)
from src.core.config import Settings

# ── Settings fixture ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def settings(tmp_path_factory) -> Settings:
    """Return a Settings instance with test-safe defaults (air-gap, seed=42)."""
    base = tmp_path_factory.mktemp("metoc_test_root")
    s = Settings(
        air_gap_mode=True,
        seed=42,
        log_level="WARNING",
        data_input_dir=base / "input",
        data_output_dir=base / "output",
        data_samples_dir=base / "samples",
        monte_carlo_particles=20,   # fast for tests
        forecast_hours=6,
    )
    s.ensure_dirs()
    return s


# ── Temporary output directory ────────────────────────────────────────────────

@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Return a fresh temporary directory for test outputs."""
    out = tmp_path / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ── Synthetic atmospheric dataset ─────────────────────────────────────────────

@pytest.fixture
def synthetic_atmo_dataset(tmp_path: Path) -> Path:
    """
    Create a minimal synthetic atmospheric xr.Dataset (u10, v10, msl).

    Grid: 5×5 lat/lon, 24 hourly timesteps.
    Saved as NetCDF to tmp_path.

    Returns
    -------
    Path to the saved NetCDF file.
    """
    rng = np.random.default_rng(42)
    lat = np.linspace(30.0, 40.0, 5)
    lon = np.linspace(10.0, 20.0, 5)
    now = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
    times = np.array(
        [np.datetime64(now + datetime.timedelta(hours=i)) for i in range(24)]
    )
    nt, ny, nx = 24, 5, 5
    shape = (nt, ny, nx)

    ds = xr.Dataset(
        {
            "u10": (["time", "lat", "lon"], rng.normal(5.0, 3.0, shape).astype("float32")),
            "v10": (["time", "lat", "lon"], rng.normal(2.0, 2.0, shape).astype("float32")),
            "msl": (["time", "lat", "lon"], rng.normal(101325.0, 500.0, shape).astype("float32")),
        },
        coords={"time": times, "lat": lat, "lon": lon},
        attrs={"Conventions": "CF-1.8", "source": "synthetic-atmo"},
    )

    out = tmp_path / "synthetic_atmo.nc"
    ds.to_netcdf(str(out), format="NETCDF4")
    return out


# ── Synthetic ocean dataset ────────────────────────────────────────────────────

@pytest.fixture
def synthetic_ocean_dataset(tmp_path: Path) -> Path:
    """
    Create a minimal synthetic ocean xr.Dataset (uo, vo, zos, vsdx, vsdy).

    Grid: 5×5 lat/lon, 24 hourly timesteps.
    Saved as NetCDF to tmp_path.

    Returns
    -------
    Path to the saved NetCDF file.
    """
    rng = np.random.default_rng(43)
    lat = np.linspace(30.0, 40.0, 5)
    lon = np.linspace(10.0, 20.0, 5)
    now = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
    times = np.array(
        [np.datetime64(now + datetime.timedelta(hours=i)) for i in range(24)]
    )
    nt, ny, nx = 24, 5, 5
    shape = (nt, ny, nx)

    ds = xr.Dataset(
        {
            "uo":   (["time", "lat", "lon"], rng.normal(0.1, 0.05, shape).astype("float32")),
            "vo":   (["time", "lat", "lon"], rng.normal(0.05, 0.05, shape).astype("float32")),
            "zos":  (["time", "lat", "lon"], rng.normal(0.0, 0.02, shape).astype("float32")),
            "vsdx": (["time", "lat", "lon"], rng.normal(0.02, 0.01, shape).astype("float32")),
            "vsdy": (["time", "lat", "lon"], rng.normal(0.01, 0.01, shape).astype("float32")),
        },
        coords={"time": times, "lat": lat, "lon": lon},
        attrs={"Conventions": "CF-1.8", "source": "synthetic-ocean"},
    )

    out = tmp_path / "synthetic_ocean.nc"
    ds.to_netcdf(str(out), format="NETCDF4")
    return out


# ── Synthetic harmonized dataset ──────────────────────────────────────────────

@pytest.fixture
def synthetic_harmonized_dataset(
    synthetic_atmo_dataset: Path,
    synthetic_ocean_dataset: Path,
    tmp_path: Path,
) -> Path:
    """
    Merge the synthetic atmospheric and ocean datasets into a single NetCDF.

    Returns
    -------
    Path to the merged NetCDF file.
    """
    atmo = xr.open_dataset(str(synthetic_atmo_dataset), engine="netcdf4")
    ocean = xr.open_dataset(str(synthetic_ocean_dataset), engine="netcdf4")
    merged = xr.merge([atmo, ocean], compat="override")
    merged.attrs["Conventions"] = "CF-1.8"
    merged.attrs["source"] = "synthetic-merged"

    out = tmp_path / "synthetic_harmonized.nc"
    merged.to_netcdf(str(out), format="NETCDF4")
    return out


# ── Sample asset list ─────────────────────────────────────────────────────────

@pytest.fixture
def sample_asset_list() -> list[AssetLocation]:
    """Return 3 sample AssetLocation objects (2 wind turbines, 1 solar PV)."""
    return [
        AssetLocation(
            asset_id="WTG-TEST-001",
            lon=14.2,
            lat=36.5,
            asset_type="WIND_TURBINE",
            rated_mw=5.0,
        ),
        AssetLocation(
            asset_id="WTG-TEST-002",
            lon=15.0,
            lat=37.0,
            asset_type="WIND_TURBINE",
            rated_mw=5.0,
        ),
        AssetLocation(
            asset_id="SOL-TEST-001",
            lon=14.8,
            lat=36.8,
            asset_type="SOLAR_PV",
            rated_mw=10.0,
        ),
    ]


# ── Sample drift corridor ─────────────────────────────────────────────────────

@pytest.fixture
def sample_drift_corridor() -> DriftCorridorResult:
    """
    Return a DriftCorridorResult with synthetic particle tracks.

    Uses 20 particles, 6 timesteps, fixed seed=42.
    The corridor polygon is a convex hull of the final particle positions.
    """
    rng = np.random.default_rng(42)
    n_particles = 20
    n_steps = 6

    tracks: list[ParticleTrack] = []
    for pid in range(n_particles):
        positions = [
            [14.5 + rng.normal(0.0, 0.05) * step, 36.8 + rng.normal(0.0, 0.03) * step]
            for step in range(1, n_steps + 1)
        ]
        tracks.append(
            ParticleTrack(
                particle_id=pid,
                positions=positions,
                final_position=positions[-1],
            )
        )

    # Build corridor using the real DriftCorridor class
    from src.lagrangian.drift_corridor import DriftCorridor

    corridor = DriftCorridor()
    return corridor.build(
        tracks=tracks,
        forecast_hours=6,
        run_id="test-run-fixture-00000000",
        ingest_run_id="test-ingest-fixture-00000000",
        origin=[14.5, 36.8],
        leeway_pct=2.5,
        seed=42,
        timestep_hours=1.0,
        compute_time_seconds=0.1,
    )
