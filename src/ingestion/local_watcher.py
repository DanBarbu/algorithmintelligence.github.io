"""
Air-gap local filesystem watcher.
Monitors data/input/ for staged NetCDF or GRIB2 files dropped by operators.
Emits IngestResult events via an asyncio.Queue.
Used when AIR_GAP_MODE=true — no outbound network access.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from watchfiles import awatch, Change  # type: ignore[import-untyped]  # noqa: F401

from src.core.config import get_settings

logger = structlog.get_logger(__name__)

# File extensions that trigger ingestion
_WATCHED_SUFFIXES = {".nc", ".grib2"}


class LocalWatcher:
    """Async filesystem watcher for air-gap operation.

    Monitors ``settings.data_input_dir`` using ``watchfiles.awatch()`` and
    emits :class:`pathlib.Path` objects onto *queue* whenever a new NetCDF
    or GRIB2 file appears.  Only readable, non-empty files are emitted.

    Usage::

        watcher = LocalWatcher()
        queue: asyncio.Queue[Path] = asyncio.Queue()
        await watcher.watch(queue)   # runs until cancelled
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._log = logger.bind(component="LocalWatcher")
        self._watch_dir: Path = self._settings.data_input_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def watch(self, queue: asyncio.Queue) -> None:  # type: ignore[type-arg]
        """Watch the input directory and push valid paths onto *queue*.

        This coroutine runs indefinitely until cancelled.  Cancellation
        (``asyncio.CancelledError``) propagates cleanly.

        Args:
            queue: An ``asyncio.Queue[Path]`` that receives discovered file
                   paths as they appear in the watched directory.
        """
        self._watch_dir.mkdir(parents=True, exist_ok=True)
        self._log.info(
            "local_watcher.start",
            watch_dir=str(self._watch_dir),
            suffixes=list(_WATCHED_SUFFIXES),
        )

        # Emit any files that were already present before we started watching
        await self._scan_existing(queue)

        async for changes in awatch(str(self._watch_dir)):
            for change_type, path_str in changes:
                if change_type not in (Change.added, Change.modified):
                    continue
                path = Path(path_str)
                if path.suffix.lower() not in _WATCHED_SUFFIXES:
                    self._log.debug(
                        "local_watcher.skip_non_data",
                        path=str(path),
                        suffix=path.suffix,
                    )
                    continue
                if not self._is_readable(path):
                    self._log.warning(
                        "local_watcher.skip_unreadable",
                        path=str(path),
                    )
                    continue
                self._log.info(
                    "local_watcher.file_detected",
                    path=str(path),
                    change=str(change_type),
                )
                await queue.put(path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _scan_existing(self, queue: asyncio.Queue) -> None:  # type: ignore[type-arg]
        """Emit files that already exist in the watched directory."""
        for suffix in _WATCHED_SUFFIXES:
            for path in sorted(self._watch_dir.glob(f"*{suffix}")):
                if self._is_readable(path):
                    self._log.info(
                        "local_watcher.existing_file",
                        path=str(path),
                    )
                    await queue.put(path)

    @staticmethod
    def _is_readable(path: Path) -> bool:
        """Return True if *path* exists, is a file, is non-empty and readable."""
        try:
            return path.is_file() and path.stat().st_size > 0 and path.open("rb").read(1) is not None
        except OSError:
            return False
