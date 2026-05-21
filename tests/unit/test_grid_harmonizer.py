"""
Unit tests for GridHarmonizer.
Uses synthetic xarray Datasets (no real data files needed).
Target coverage: ≥ 90% of grid_harmonizer.py
"""
from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from src.ingestion.grid_harmonizer import GridHarmonizer, GridMismatchError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_atmo_ds(
    lat: np.ndarray,
    lon: np.ndarray,
    include_u10: bool = True,
) -> xr.Dataset:
    """Build a synthetic atmospheric dataset on a regular lat/lon grid."""
    rng = np.random.default_rng(0)
    shape = (len(lat), len(lon))
    data_vars: dict[str, xr.Variable] = {}
    if include_u10:
        data_vars["u10"] = xr.Variable(
            ("lat", "lon"), rng.standard_normal(shape).astype("float32")
        )
    data_vars["v10"] = xr.Variable(
        ("lat", "lon"), rng.standard_normal(shape).astype("float32")
    )
    data_vars["msl"] = xr.Variable(
        ("lat", "lon"),
        (101_325.0 + rng.standard_normal(shape) * 100.0).astype("float32"),
    )
    return xr.Dataset(data_vars, coords={"lat": lat, "lon": lon})


def _make_ocean_ds(lat: np.ndarray, lon: np.ndarray) -> xr.Dataset:
    """Build a synthetic ocean dataset on a fine (1/12°) lat/lon grid."""
    rng = np.random.default_rng(1)
    shape = (len(lat), len(lon))
    return xr.Dataset(
        {
            "uo": xr.Variable(("lat", "lon"), rng.standard_normal(shape).astype("float32")),
            "vo": xr.Variable(("lat", "lon"), rng.standard_normal(shape).astype("float32")),
            "zos": xr.Variable(("lat", "lon"), rng.standard_normal(shape).astype("float32")),
            "vsdx": xr.Variable(("lat", "lon"), rng.standard_normal(shape).astype("float32")),
            "vsdy": xr.Variable(("lat", "lon"), rng.standard_normal(shape).astype("float32")),
        },
        coords={"lat": lat, "lon": lon},
    )


@pytest.fixture()
def bbox() -> list[float]:
    return [-5.0, 40.0, 5.0, 50.0]


@pytest.fixture()
def atmo_lat(bbox) -> np.ndarray:
    # 0.25° atmospheric grid
    return np.arange(bbox[1], bbox[3] + 0.01, 0.25)


@pytest.fixture()
def atmo_lon(bbox) -> np.ndarray:
    return np.arange(bbox[0], bbox[2] + 0.01, 0.25)


@pytest.fixture()
def ocean_lat(bbox) -> np.ndarray:
    # 1/12° ocean grid
    step = round(1 / 12, 6)
    return np.arange(bbox[1], bbox[3] + 0.001, step)


@pytest.fixture()
def ocean_lon(bbox) -> np.ndarray:
    step = round(1 / 12, 6)
    return np.arange(bbox[0], bbox[2] + 0.001, step)


@pytest.fixture()
def atmo_nc(tmp_path, atmo_lat, atmo_lon) -> object:
    """Persist synthetic atmospheric data to a NetCDF file."""
    ds = _make_atmo_ds(atmo_lat, atmo_lon)
    p = tmp_path / "atmo.nc"
    ds.to_netcdf(str(p))
    return p


@pytest.fixture()
def ocean_nc(tmp_path, ocean_lat, ocean_lon) -> object:
    """Persist synthetic ocean data to a NetCDF file."""
    ds = _make_ocean_ds(ocean_lat, ocean_lon)
    p = tmp_path / "ocean.nc"
    ds.to_netcdf(str(p))
    return p


@pytest.fixture()
def harmonizer() -> GridHarmonizer:
    return GridHarmonizer()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHarmonizeReturnsExpectedVariables:
    """The merged dataset must contain all 7 canonical variables."""

    def test_harmonize_returns_expected_variables(
        self, harmonizer, atmo_nc, ocean_nc, bbox, tmp_path
    ):
        out = tmp_path / "harmonized.nc"
        ds = harmonizer.harmonize(
            atmo_path=atmo_nc,
            ocean_path=ocean_nc,
            bounding_box=bbox,
            output_path=out,
        )
        canonical = ["u10", "v10", "msl", "uo", "vo", "zos", "vsdx", "vsdy"]
        for var in canonical:
            assert var in ds, f"Missing canonical variable '{var}' in output dataset"

    def test_output_file_is_created(
        self, harmonizer, atmo_nc, ocean_nc, bbox, tmp_path
    ):
        out = tmp_path / "harmonized.nc"
        harmonizer.harmonize(
            atmo_path=atmo_nc,
            ocean_path=ocean_nc,
            bounding_box=bbox,
            output_path=out,
        )
        assert out.exists(), "Output NetCDF file was not written"
        assert out.stat().st_size > 0, "Output NetCDF file is empty"

    def test_output_is_readable_netcdf(
        self, harmonizer, atmo_nc, ocean_nc, bbox, tmp_path
    ):
        out = tmp_path / "harmonized.nc"
        harmonizer.harmonize(
            atmo_path=atmo_nc,
            ocean_path=ocean_nc,
            bounding_box=bbox,
            output_path=out,
        )
        reloaded = xr.open_dataset(str(out))
        assert "u10" in reloaded.data_vars


class TestHarmonizeRaisesOnMissingVariable:
    """GridMismatchError should be raised when a required variable is absent."""

    def test_harmonize_raises_on_missing_u10(
        self, harmonizer, atmo_lat, atmo_lon, ocean_nc, bbox, tmp_path
    ):
        # Build atmo dataset WITHOUT u10
        ds = _make_atmo_ds(atmo_lat, atmo_lon, include_u10=False)
        bad_atmo = tmp_path / "atmo_no_u10.nc"
        ds.to_netcdf(str(bad_atmo))

        out = tmp_path / "harmonized.nc"
        with pytest.raises(GridMismatchError, match="u10"):
            harmonizer.harmonize(
                atmo_path=bad_atmo,
                ocean_path=ocean_nc,
                bounding_box=bbox,
                output_path=out,
            )

    def test_harmonize_raises_on_missing_ocean_var(
        self, harmonizer, atmo_nc, ocean_lat, ocean_lon, bbox, tmp_path
    ):
        # Build ocean dataset WITHOUT vsdy
        rng = np.random.default_rng(2)
        shape = (len(ocean_lat), len(ocean_lon))
        ds = xr.Dataset(
            {
                "uo": xr.Variable(("lat", "lon"), rng.standard_normal(shape)),
                "vo": xr.Variable(("lat", "lon"), rng.standard_normal(shape)),
                "zos": xr.Variable(("lat", "lon"), rng.standard_normal(shape)),
                "vsdx": xr.Variable(("lat", "lon"), rng.standard_normal(shape)),
                # vsdy intentionally omitted
            },
            coords={"lat": ocean_lat, "lon": ocean_lon},
        )
        bad_ocean = tmp_path / "ocean_no_vsdy.nc"
        ds.to_netcdf(str(bad_ocean))

        out = tmp_path / "harmonized.nc"
        with pytest.raises(GridMismatchError, match="vsdy"):
            harmonizer.harmonize(
                atmo_path=atmo_nc,
                ocean_path=bad_ocean,
                bounding_box=bbox,
                output_path=out,
            )


class TestOutputResolution:
    """The output grid spacing must equal settings.target_grid_resolution_deg (0.25°)."""

    def test_output_resolution_matches_target(
        self, harmonizer, atmo_nc, ocean_nc, bbox, tmp_path
    ):
        out = tmp_path / "harmonized.nc"
        ds = harmonizer.harmonize(
            atmo_path=atmo_nc,
            ocean_path=ocean_nc,
            bounding_box=bbox,
            output_path=out,
        )
        lats = ds.coords["lat"].values
        lons = ds.coords["lon"].values

        assert len(lats) >= 2, "Output must have at least two latitude points"
        assert len(lons) >= 2, "Output must have at least two longitude points"

        lat_spacing = np.diff(lats)
        lon_spacing = np.diff(lons)

        np.testing.assert_allclose(lat_spacing, 0.25, atol=1e-6,
                                   err_msg="Latitude spacing is not 0.25°")
        np.testing.assert_allclose(lon_spacing, 0.25, atol=1e-6,
                                   err_msg="Longitude spacing is not 0.25°")

    def test_grid_resolution_attr_is_set(
        self, harmonizer, atmo_nc, ocean_nc, bbox, tmp_path
    ):
        out = tmp_path / "harmonized.nc"
        ds = harmonizer.harmonize(
            atmo_path=atmo_nc,
            ocean_path=ocean_nc,
            bounding_box=bbox,
            output_path=out,
        )
        assert ds.attrs.get("grid_resolution_deg") == 0.25


class TestBoundingBoxClipping:
    """Output data extent must not exceed the bounding_box argument."""

    def test_bounding_box_clips_data(
        self, harmonizer, atmo_nc, ocean_nc, bbox, tmp_path
    ):
        lon_min, lat_min, lon_max, lat_max = bbox
        out = tmp_path / "harmonized.nc"
        ds = harmonizer.harmonize(
            atmo_path=atmo_nc,
            ocean_path=ocean_nc,
            bounding_box=bbox,
            output_path=out,
        )
        lats = ds.coords["lat"].values
        lons = ds.coords["lon"].values

        assert float(lats.min()) >= lat_min - 1e-6, (
            f"Min latitude {lats.min():.4f} is below bbox min {lat_min}"
        )
        assert float(lats.max()) <= lat_max + 1e-6, (
            f"Max latitude {lats.max():.4f} exceeds bbox max {lat_max}"
        )
        assert float(lons.min()) >= lon_min - 1e-6, (
            f"Min longitude {lons.min():.4f} is below bbox min {lon_min}"
        )
        assert float(lons.max()) <= lon_max + 1e-6, (
            f"Max longitude {lons.max():.4f} exceeds bbox max {lon_max}"
        )

    def test_narrow_bbox_produces_fewer_points(
        self, harmonizer, atmo_lat, atmo_lon, ocean_lat, ocean_lon, tmp_path
    ):
        """A narrower bounding box should produce fewer grid points."""
        # Wide bbox
        wide_bbox = [-5.0, 40.0, 5.0, 50.0]
        # Narrow bbox
        narrow_bbox = [-2.0, 43.0, 2.0, 47.0]

        # Save same dataset for both
        atmo_ds = _make_atmo_ds(atmo_lat, atmo_lon)
        ocean_ds = _make_ocean_ds(ocean_lat, ocean_lon)
        atmo_p = tmp_path / "atmo.nc"
        ocean_p = tmp_path / "ocean.nc"
        atmo_ds.to_netcdf(str(atmo_p))
        ocean_ds.to_netcdf(str(ocean_p))

        wide_ds = harmonizer.harmonize(
            atmo_path=atmo_p,
            ocean_path=ocean_p,
            bounding_box=wide_bbox,
            output_path=tmp_path / "wide.nc",
        )
        narrow_ds = harmonizer.harmonize(
            atmo_path=atmo_p,
            ocean_path=ocean_p,
            bounding_box=narrow_bbox,
            output_path=tmp_path / "narrow.nc",
        )
        assert wide_ds.dims["lat"] > narrow_ds.dims["lat"]
        assert wide_ds.dims["lon"] > narrow_ds.dims["lon"]


class TestVariableRenaming:
    """Variables with non-canonical names should be renamed correctly."""

    def test_rename_aliases_to_canonical(
        self, harmonizer, ocean_nc, bbox, tmp_path
    ):
        """Atmospheric dataset using ECMWF alias names should be normalised."""
        atmo_lat = np.arange(bbox[1], bbox[3] + 0.01, 0.25)
        atmo_lon = np.arange(bbox[0], bbox[2] + 0.01, 0.25)
        rng = np.random.default_rng(3)
        shape = (len(atmo_lat), len(atmo_lon))
        # Use aliases: "10u", "10v", "mean_sea_level_pressure"
        ds = xr.Dataset(
            {
                "10u": xr.Variable(("lat", "lon"), rng.standard_normal(shape)),
                "10v": xr.Variable(("lat", "lon"), rng.standard_normal(shape)),
                "mean_sea_level_pressure": xr.Variable(
                    ("lat", "lon"), rng.standard_normal(shape)
                ),
            },
            coords={"lat": atmo_lat, "lon": atmo_lon},
        )
        alias_atmo = tmp_path / "atmo_alias.nc"
        ds.to_netcdf(str(alias_atmo))

        out = tmp_path / "harmonized_alias.nc"
        result = harmonizer.harmonize(
            atmo_path=alias_atmo,
            ocean_path=ocean_nc,
            bounding_box=bbox,
            output_path=out,
        )
        assert "u10" in result.data_vars
        assert "v10" in result.data_vars
        assert "msl" in result.data_vars
