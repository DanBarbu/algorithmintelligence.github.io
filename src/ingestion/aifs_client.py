"""
ECMWF AIFS (AI Forecasting System) Open Data client.
Downloads GRIB2 files for u10, v10, msl from the ECMWF open data portal.
Falls back to local staging folder when air_gap_mode=True.
"""
from __future__ import annotations

import asyncio
import datetime
from pathlib import Path

import structlog

from src.core.config import get_settings

logger = structlog.get_logger(__name__)

# Variables to fetch: 10m U-wind, 10m V-wind, mean sea level pressure
_AIFS_PARAMS = ["10u", "10v", "msl"]

# Retry configuration
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds


class AIFSClientError(Exception):
    """Raised when the AIFS client cannot retrieve data."""


class AIFSClient:
    """Async ECMWF AIFS open-data client.

    In normal mode downloads GRIB2 files using `ecmwf-opendata`.
    In air_gap_mode scans ``settings.data_input_dir`` for files
    matching ``aifs_*.grib2`` instead of making any network calls.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._log = logger.bind(client="AIFSClient")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch(
        self,
        bounding_box: list[float],
        date: datetime.date | None = None,
        step_hours: int = 0,
    ) -> Path:
        """Download (or locate) an AIFS GRIB2 file.

        Args:
            bounding_box: [lon_min, lat_min, lon_max, lat_max]
            date:         Forecast base date (UTC).  Defaults to today.
            step_hours:   Forecast step in hours (default 0 = analysis).

        Returns:
            Absolute Path to the GRIB2 file on the local filesystem.
        """
        date = date or datetime.date.today()
        self._log.info(
            "aifs.fetch.start",
            air_gap_mode=self._settings.air_gap_mode,
            date=date.isoformat(),
            step_hours=step_hours,
            bounding_box=bounding_box,
        )

        if self._settings.air_gap_mode:
            return self._scan_local("aifs_*.grib2")

        return await self._download(bounding_box, date, step_hours)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_local(self, pattern: str) -> Path:
        """Return the first matching file in data_input_dir."""
        candidates = sorted(self._settings.data_input_dir.glob(pattern))
        if not candidates:
            raise AIFSClientError(
                f"air_gap_mode=True but no files matching '{pattern}' found in "
                f"{self._settings.data_input_dir}"
            )
        chosen = candidates[0]
        self._log.info("aifs.local_file.found", path=str(chosen))
        return chosen

    async def _download(
        self,
        bounding_box: list[float],
        date: datetime.date,
        step_hours: int,
    ) -> Path:
        """Perform the actual download with retry / exponential back-off."""
        output_dir = self._settings.data_input_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        lon_min, lat_min, lon_max, lat_max = bounding_box
        filename = (
            f"aifs_{date.strftime('%Y%m%d')}_step{step_hours:03d}.grib2"
        )
        dest = output_dir / filename

        if dest.exists():
            self._log.info("aifs.cache_hit", path=str(dest))
            return dest

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                self._log.info(
                    "aifs.download.attempt",
                    attempt=attempt,
                    dest=str(dest),
                )
                await asyncio.to_thread(
                    self._ecmwf_download,
                    date=date,
                    step_hours=step_hours,
                    dest=dest,
                    area=[lat_max, lon_min, lat_min, lon_max],  # N/W/S/E
                )
                self._log.info("aifs.download.success", path=str(dest))
                return dest
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                wait = _BACKOFF_BASE**attempt
                self._log.warning(
                    "aifs.download.retry",
                    attempt=attempt,
                    wait_seconds=wait,
                    error=str(exc),
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(wait)

        raise AIFSClientError(
            f"AIFS download failed after {_MAX_RETRIES} attempts"
        ) from last_exc

    @staticmethod
    def _ecmwf_download(
        date: datetime.date,
        step_hours: int,
        dest: Path,
        area: list[float],
    ) -> None:
        """Synchronous ECMWF open-data download (runs in a thread pool)."""
        from ecmwf.opendata import Client  # type: ignore[import-untyped]

        client = Client(source="ecmwf")
        client.retrieve(
            date=date.strftime("%Y%m%d"),
            time=0,
            step=step_hours,
            stream="oper",
            type="fc",
            param=_AIFS_PARAMS,
            target=str(dest),
        )
