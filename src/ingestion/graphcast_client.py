"""
Google GraphCast / GenCast NetCDF client.
Fetches from the WeatherBench2 public GCS bucket (no auth required).
In air_gap_mode scans data_input_dir for *.nc files matching "graphcast_*".
"""
from __future__ import annotations

import asyncio
import datetime
from pathlib import Path

import httpx
import structlog

from src.core.config import get_settings

logger = structlog.get_logger(__name__)

# WeatherBench2 public GCS base URL (HTTP, no auth)
_GCS_BASE = "https://storage.googleapis.com"
_BUCKET = "weatherbench2"

# Variables expected in the WeatherBench2 GraphCast archive
_GC_VARIABLES = [
    "u_component_of_wind",
    "v_component_of_wind",
    "mean_sea_level_pressure",
]

# Retry configuration
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds
_CHUNK_SIZE = 1 << 20  # 1 MiB


class GraphCastClientError(Exception):
    """Raised when the GraphCast client cannot retrieve data."""


class GraphCastClient:
    """Async Google GraphCast / GenCast NetCDF client.

    Downloads NetCDF files from the WeatherBench2 public GCS bucket.
    In air_gap_mode the network is bypassed entirely and files are
    resolved from ``settings.data_input_dir``.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._log = logger.bind(client="GraphCastClient")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch(
        self,
        bounding_box: list[float],
        date: datetime.date | None = None,
        step_hours: int = 0,
    ) -> Path:
        """Download (or locate) a GraphCast NetCDF file.

        Args:
            bounding_box: [lon_min, lat_min, lon_max, lat_max]
            date:         Forecast base date (UTC).  Defaults to today.
            step_hours:   Forecast step in hours.

        Returns:
            Absolute Path to the NetCDF file on the local filesystem.
        """
        date = date or datetime.date.today()
        self._log.info(
            "graphcast.fetch.start",
            air_gap_mode=self._settings.air_gap_mode,
            date=date.isoformat(),
            step_hours=step_hours,
            bounding_box=bounding_box,
        )

        if self._settings.air_gap_mode:
            return self._scan_local("graphcast_*.nc")

        return await self._download(bounding_box, date, step_hours)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_local(self, pattern: str) -> Path:
        """Return the first matching file in data_input_dir."""
        candidates = sorted(self._settings.data_input_dir.glob(pattern))
        if not candidates:
            raise GraphCastClientError(
                f"air_gap_mode=True but no files matching '{pattern}' found in "
                f"{self._settings.data_input_dir}"
            )
        chosen = candidates[0]
        self._log.info("graphcast.local_file.found", path=str(chosen))
        return chosen

    async def _download(
        self,
        bounding_box: list[float],
        date: datetime.date,
        step_hours: int,
    ) -> Path:
        """Stream the NetCDF from GCS with retry / exponential back-off."""
        output_dir = self._settings.data_input_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = (
            f"graphcast_{date.strftime('%Y%m%d')}_step{step_hours:03d}.nc"
        )
        dest = output_dir / filename

        if dest.exists():
            self._log.info("graphcast.cache_hit", path=str(dest))
            return dest

        # Construct GCS object path.  WeatherBench2 uses a date-based layout.
        year = date.strftime("%Y")
        obj_path = (
            f"datasets/graphcast/{year}/"
            f"{date.strftime('%Y%m%d')}_step{step_hours:03d}.nc"
        )
        url = f"{_GCS_BASE}/{_BUCKET}/{obj_path}"

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                self._log.info(
                    "graphcast.download.attempt",
                    attempt=attempt,
                    url=url,
                    dest=str(dest),
                )
                await self._stream_to_file(url, dest)
                self._log.info("graphcast.download.success", path=str(dest))
                return dest
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                wait = _BACKOFF_BASE**attempt
                self._log.warning(
                    "graphcast.download.retry",
                    attempt=attempt,
                    wait_seconds=wait,
                    error=str(exc),
                )
                if dest.exists():
                    dest.unlink(missing_ok=True)
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(wait)

        raise GraphCastClientError(
            f"GraphCast download failed after {_MAX_RETRIES} attempts: {url}"
        ) from last_exc

    async def _stream_to_file(self, url: str, dest: Path) -> None:
        """Stream HTTP response content to *dest* using httpx."""
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with dest.open("wb") as fh:
                    async for chunk in response.aiter_bytes(_CHUNK_SIZE):
                        fh.write(chunk)
