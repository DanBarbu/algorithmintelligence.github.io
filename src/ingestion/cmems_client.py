"""
Copernicus Marine Service (CMEMS) client.
Fetches ocean physics products: surface currents (uo, vo),
sea surface height anomaly (zos), and Stokes drift (vsdx, vsdy).
Product: cmems_mod_glo_phy_anfc_0.083deg_P1D-m (GLORYS12)
In air_gap_mode scans data_input_dir for *.nc files matching "cmems_*".
"""
from __future__ import annotations

import asyncio
import datetime
from pathlib import Path

import structlog

from src.core.config import get_settings

logger = structlog.get_logger(__name__)

# CMEMS GLORYS12 product identifier
_PRODUCT_ID = "cmems_mod_glo_phy_anfc_0.083deg_P1D-m"

# Ocean variables to retrieve
# Stokes drift (vsdx/vsdy) may not be in GLORYS12; we try and fall back
_OCEAN_VARS = ["uo", "vo", "zos"]
_STOKES_VARS = ["vsdx", "vsdy"]
_STOKES_FALLBACK = ["VoWat", "UoWat"]  # alternative names in some products

# Surface depth level
_DEPTH = 0.5  # metres — top layer


class CMEMSClientError(Exception):
    """Raised when the CMEMS client cannot retrieve data."""


class CMEMSClient:
    """Async Copernicus Marine Service client.

    Wraps the ``copernicusmarine.subset()`` call (which is synchronous) in
    an asyncio thread-pool executor.  In air_gap_mode all network I/O is
    bypassed and files are resolved from ``settings.data_input_dir``.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._log = logger.bind(client="CMEMSClient")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch(
        self,
        bounding_box: list[float],
        date: datetime.date | None = None,
    ) -> Path:
        """Download (or locate) a CMEMS ocean NetCDF file.

        Args:
            bounding_box: [lon_min, lat_min, lon_max, lat_max]
            date:         Target analysis date (UTC).  Defaults to today.

        Returns:
            Absolute Path to the NetCDF file on the local filesystem.
        """
        date = date or datetime.date.today()
        self._log.info(
            "cmems.fetch.start",
            air_gap_mode=self._settings.air_gap_mode,
            date=date.isoformat(),
            bounding_box=bounding_box,
        )

        if self._settings.air_gap_mode:
            return self._scan_local("cmems_*.nc")

        return await self._download(bounding_box, date)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_local(self, pattern: str) -> Path:
        """Return the first matching file in data_input_dir."""
        candidates = sorted(self._settings.data_input_dir.glob(pattern))
        if not candidates:
            raise CMEMSClientError(
                f"air_gap_mode=True but no files matching '{pattern}' found in "
                f"{self._settings.data_input_dir}"
            )
        chosen = candidates[0]
        self._log.info("cmems.local_file.found", path=str(chosen))
        return chosen

    async def _download(
        self,
        bounding_box: list[float],
        date: datetime.date,
    ) -> Path:
        """Run copernicusmarine.subset() in a thread and return dest path."""
        output_dir = self._settings.data_input_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"cmems_{date.strftime('%Y%m%d')}.nc"
        dest = output_dir / filename

        if dest.exists():
            self._log.info("cmems.cache_hit", path=str(dest))
            return dest

        lon_min, lat_min, lon_max, lat_max = bounding_box

        # Build variable list — try Stokes drift; handle absence gracefully
        variables = list(_OCEAN_VARS)
        variables.extend(_STOKES_VARS)

        self._log.info(
            "cmems.subset.start",
            product=_PRODUCT_ID,
            variables=variables,
            dest=str(dest),
        )

        try:
            await asyncio.to_thread(
                self._copernicusmarine_subset,
                product_id=_PRODUCT_ID,
                variables=variables,
                lon_min=lon_min,
                lat_min=lat_min,
                lon_max=lon_max,
                lat_max=lat_max,
                depth_min=_DEPTH,
                depth_max=_DEPTH,
                date_start=date,
                date_end=date,
                dest=dest,
            )
        except Exception as exc:  # noqa: BLE001
            # Retry without Stokes drift if unavailable
            self._log.warning(
                "cmems.subset.stokes_fallback",
                error=str(exc),
                fallback_vars=_OCEAN_VARS,
            )
            if dest.exists():
                dest.unlink(missing_ok=True)
            await asyncio.to_thread(
                self._copernicusmarine_subset,
                product_id=_PRODUCT_ID,
                variables=_OCEAN_VARS,
                lon_min=lon_min,
                lat_min=lat_min,
                lon_max=lon_max,
                lat_max=lat_max,
                depth_min=_DEPTH,
                depth_max=_DEPTH,
                date_start=date,
                date_end=date,
                dest=dest,
            )

        self._log.info("cmems.subset.success", path=str(dest))
        return dest

    def _copernicusmarine_subset(
        self,
        *,
        product_id: str,
        variables: list[str],
        lon_min: float,
        lat_min: float,
        lon_max: float,
        lat_max: float,
        depth_min: float,
        depth_max: float,
        date_start: datetime.date,
        date_end: datetime.date,
        dest: Path,
    ) -> None:
        """Synchronous wrapper around copernicusmarine.subset()."""
        import copernicusmarine  # type: ignore[import-untyped]

        copernicusmarine.subset(
            dataset_id=product_id,
            variables=variables,
            minimum_longitude=lon_min,
            maximum_longitude=lon_max,
            minimum_latitude=lat_min,
            maximum_latitude=lat_max,
            minimum_depth=depth_min,
            maximum_depth=depth_max,
            start_datetime=datetime.datetime.combine(
                date_start, datetime.time.min
            ).strftime("%Y-%m-%dT%H:%M:%S"),
            end_datetime=datetime.datetime.combine(
                date_end, datetime.time.max
            ).strftime("%Y-%m-%dT%H:%M:%S"),
            output_filename=dest.name,
            output_directory=str(dest.parent),
            username=self._settings.cmems_username or None,
            password=self._settings.cmems_password or None,
            overwrite=True,
        )
