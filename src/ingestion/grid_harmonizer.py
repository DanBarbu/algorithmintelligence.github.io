"""
Spatio-temporal mesh harmonizer.
Resamples heterogeneous input grids (atmospheric 0.25° and ocean 1/12°)
into a single unified localized spatial mesh via bilinear interpolation.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import structlog
import xarray as xr

from src.core.config import get_settings

logger = structlog.get_logger(__name__)

# Canonical variable names expected in the harmonized output
_ATMO_VARS = ["u10", "v10", "msl"]
_OCEAN_VARS = ["uo", "vo", "zos", "vsdx", "vsdy"]
_ALL_CANONICAL = _ATMO_VARS + _OCEAN_VARS

# Map of (possible_source_names) → canonical_name for atmospheric data
_ATMO_RENAME: dict[str, str] = {
    # CF / ECMWF GRIB2 short names
    "10u": "u10",
    "u10": "u10",
    "u_component_of_wind": "u10",
    "U10M": "u10",
    "10v": "v10",
    "v10": "v10",
    "v_component_of_wind": "v10",
    "V10M": "v10",
    "msl": "msl",
    "mean_sea_level_pressure": "msl",
    "MSL": "msl",
    "prmsl": "msl",
}

# Map of (possible_source_names) → canonical_name for ocean data
_OCEAN_RENAME: dict[str, str] = {
    "uo": "uo",
    "vo": "vo",
    "zos": "zos",
    "vsdx": "vsdx",
    "ugosa": "vsdx",  # some CMEMS products
    "UoWat": "vsdx",
    "vsdy": "vsdy",
    "vgosa": "vsdy",
    "VoWat": "vsdy",
}

# Map of dimension aliases → canonical dimension names
_LAT_ALIASES = {"lat", "latitude", "nav_lat", "y", "rlat"}
_LON_ALIASES = {"lon", "longitude", "nav_lon", "x", "rlon"}


class GridMismatchError(Exception):
    """Raised when required variables are absent from an input dataset."""


class GridHarmonizer:
    """Bilinear-interpolation mesh harmonizer.

    Opens GRIB2 (via cfgrib) and NetCDF files, renames variables to a
    canonical schema, aligns all grids to a uniform 0.25° mesh within
    the requested bounding box, and saves the result as a CF-compliant
    NetCDF4 file.

    Example::

        harmonizer = GridHarmonizer()
        ds = harmonizer.harmonize(
            atmo_path=Path("aifs_20240101_step000.grib2"),
            ocean_path=Path("cmems_20240101.nc"),
            bounding_box=[-10.0, 35.0, 10.0, 50.0],
            output_path=Path("data/output/harmonized.nc"),
        )
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._rng = np.random.default_rng(self._settings.seed)
        self._log = logger.bind(component="GridHarmonizer")
        self._resolution = self._settings.target_grid_resolution_deg

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def harmonize(
        self,
        atmo_path: Path,
        ocean_path: Path,
        bounding_box: list[float],
        output_path: Path,
    ) -> xr.Dataset:
        """Open, rename, interpolate, clip and merge atmospheric + ocean data.

        Args:
            atmo_path:    Path to the atmospheric GRIB2 or NetCDF file.
            ocean_path:   Path to the ocean NetCDF file.
            bounding_box: [lon_min, lat_min, lon_max, lat_max].
            output_path:  Destination path for the merged NetCDF4 output.

        Returns:
            The harmonized :class:`xarray.Dataset`.

        Raises:
            GridMismatchError: If any required canonical variable is missing.
        """
        lon_min, lat_min, lon_max, lat_max = bounding_box
        self._log.info(
            "harmonizer.start",
            atmo=str(atmo_path),
            ocean=str(ocean_path),
            bbox=bounding_box,
        )

        # Build target grid
        target_lat = np.arange(lat_min, lat_max + 1e-9, self._resolution)
        target_lon = np.arange(lon_min, lon_max + 1e-9, self._resolution)

        # Load and normalise sources
        atmo_ds = self._load_atmo(atmo_path)
        ocean_ds = self._load_ocean(ocean_path)

        # Rename to canonical names
        atmo_ds = self._rename_vars(atmo_ds, _ATMO_RENAME, source="atmo")
        ocean_ds = self._rename_vars(ocean_ds, _OCEAN_RENAME, source="ocean")

        # Standardise dimension names
        atmo_ds = self._normalise_dims(atmo_ds)
        ocean_ds = self._normalise_dims(ocean_ds)

        # Clip to bounding box before interpolation (performance)
        atmo_ds = self._clip(atmo_ds, lat_min, lat_max, lon_min, lon_max)
        ocean_ds = self._clip(ocean_ds, lat_min, lat_max, lon_min, lon_max)

        # Check that canonical variables are present
        self._validate_vars(atmo_ds, _ATMO_VARS, source="atmo")
        self._validate_vars(ocean_ds, _OCEAN_VARS, source="ocean")

        # Interpolate to target grid (bilinear)
        self._log.info(
            "harmonizer.interpolate",
            lat_points=len(target_lat),
            lon_points=len(target_lon),
        )
        atmo_interp = atmo_ds[_ATMO_VARS].interp(
            lat=target_lat, lon=target_lon, method="linear"
        )
        ocean_interp = ocean_ds[_OCEAN_VARS].interp(
            lat=target_lat, lon=target_lon, method="linear"
        )

        # Merge into single dataset
        merged = xr.merge([atmo_interp, ocean_interp], compat="override")
        merged.attrs["grid_resolution_deg"] = self._resolution
        merged.attrs["bounding_box"] = str(bounding_box)
        merged.attrs["Conventions"] = "CF-1.8"
        merged.attrs["source_atmo"] = str(atmo_path)
        merged.attrs["source_ocean"] = str(ocean_path)

        # Persist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_netcdf(str(output_path), format="NETCDF4")
        self._log.info("harmonizer.saved", path=str(output_path))

        return merged

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_atmo(self, path: Path) -> xr.Dataset:
        """Load an atmospheric file (GRIB2 or NetCDF) as an xr.Dataset."""
        suffix = path.suffix.lower()
        self._log.debug("harmonizer.load_atmo", path=str(path), suffix=suffix)
        if suffix in {".grib2", ".grib", ".grb2", ".grb"}:
            # cfgrib back-end — may return multiple datasets; merge them
            datasets = xr.open_dataset(
                str(path),
                engine="cfgrib",
                backend_kwargs={"errors": "ignore"},
            )
            return datasets
        # NetCDF (e.g. GraphCast output)
        return xr.open_dataset(str(path))

    def _load_ocean(self, path: Path) -> xr.Dataset:
        """Load an ocean NetCDF file as an xr.Dataset."""
        self._log.debug("harmonizer.load_ocean", path=str(path))
        return xr.open_dataset(str(path))

    @staticmethod
    def _rename_vars(ds: xr.Dataset, rename_map: dict[str, str], source: str) -> xr.Dataset:
        """Rename dataset variables using *rename_map* (only existing vars)."""
        applicable = {k: v for k, v in rename_map.items() if k in ds}
        if applicable:
            ds = ds.rename(applicable)
        logger.debug(
            "harmonizer.rename",
            source=source,
            applied=list(applicable.keys()),
        )
        return ds

    @staticmethod
    def _normalise_dims(ds: xr.Dataset) -> xr.Dataset:
        """Rename latitude/longitude dimension aliases to 'lat'/'lon'."""
        rename: dict[str, str] = {}
        for dim in ds.dims:
            if dim in _LAT_ALIASES:
                rename[dim] = "lat"
            elif dim in _LON_ALIASES:
                rename[dim] = "lon"
        if rename:
            ds = ds.rename(rename)
        return ds

    @staticmethod
    def _clip(
        ds: xr.Dataset,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
    ) -> xr.Dataset:
        """Slice dataset to the given lat/lon extent (inclusive)."""
        if "lat" in ds.dims:
            ds = ds.sel(lat=slice(lat_min, lat_max))
        if "lon" in ds.dims:
            ds = ds.sel(lon=slice(lon_min, lon_max))
        return ds

    @staticmethod
    def _validate_vars(ds: xr.Dataset, required: list[str], source: str) -> None:
        """Assert that all *required* canonical variables exist in *ds*."""
        missing = [v for v in required if v not in ds]
        if missing:
            raise GridMismatchError(
                f"[{source}] Required canonical variables missing from dataset: "
                f"{missing}.  Available: {list(ds.data_vars)}"
            )
