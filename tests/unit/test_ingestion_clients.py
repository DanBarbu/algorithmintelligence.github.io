"""
Unit tests for AIFS, GraphCast, and CMEMS clients.
All network calls are mocked — no internet access required in CI.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.aifs_client import AIFSClient, AIFSClientError
from src.ingestion.cmems_client import CMEMSClient, CMEMSClientError
from src.ingestion.graphcast_client import GraphCastClient, GraphCastClientError
from src.ingestion.local_watcher import LocalWatcher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_dummy_file(path: Path, content: bytes = b"\x00" * 64) -> Path:
    """Write a dummy non-empty file and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# AIFS Client Tests
# ---------------------------------------------------------------------------

class TestAIFSClient:
    """Tests for AIFSClient with all I/O mocked."""

    def test_aifs_air_gap_mode_finds_local_file(self, tmp_path):
        """Client returns the first aifs_*.grib2 file in data_input_dir."""
        # Arrange: create a dummy GRIB2 file
        dummy = _write_dummy_file(tmp_path / "aifs_20240101_step000.grib2")

        # Patch settings to point at tmp_path with air_gap_mode=True
        mock_settings = MagicMock()
        mock_settings.air_gap_mode = True
        mock_settings.data_input_dir = tmp_path

        with patch("src.ingestion.aifs_client.get_settings", return_value=mock_settings):
            client = AIFSClient()
            result = asyncio.get_event_loop().run_until_complete(
                client.fetch(bounding_box=[-10.0, 35.0, 10.0, 50.0])
            )

        assert result == dummy

    def test_aifs_air_gap_mode_no_file_raises(self, tmp_path):
        """Client raises AIFSClientError when no local GRIB2 file is found."""
        mock_settings = MagicMock()
        mock_settings.air_gap_mode = True
        mock_settings.data_input_dir = tmp_path  # empty directory

        with patch("src.ingestion.aifs_client.get_settings", return_value=mock_settings):
            client = AIFSClient()
            with pytest.raises(AIFSClientError, match="aifs_\\*.grib2"):
                asyncio.get_event_loop().run_until_complete(
                    client.fetch(bounding_box=[-10.0, 35.0, 10.0, 50.0])
                )

    def test_aifs_air_gap_picks_first_alphabetically(self, tmp_path):
        """When multiple files match, the first alphabetically is returned."""
        _write_dummy_file(tmp_path / "aifs_20240102_step000.grib2")
        first = _write_dummy_file(tmp_path / "aifs_20240101_step000.grib2")

        mock_settings = MagicMock()
        mock_settings.air_gap_mode = True
        mock_settings.data_input_dir = tmp_path

        with patch("src.ingestion.aifs_client.get_settings", return_value=mock_settings):
            client = AIFSClient()
            result = asyncio.get_event_loop().run_until_complete(
                client.fetch(bounding_box=[-10.0, 35.0, 10.0, 50.0])
            )

        assert result == first

    @pytest.mark.asyncio
    async def test_aifs_live_mode_calls_ecmwf(self, tmp_path):
        """In live mode, _ecmwf_download should be called once."""
        mock_settings = MagicMock()
        mock_settings.air_gap_mode = False
        mock_settings.data_input_dir = tmp_path

        with patch("src.ingestion.aifs_client.get_settings", return_value=mock_settings):
            client = AIFSClient()
            with patch.object(
                client,
                "_ecmwf_download",
                side_effect=lambda **kw: kw["dest"].write_bytes(b"\x00" * 32),
            ) as mock_dl:
                result = await client.fetch(bounding_box=[-10.0, 35.0, 10.0, 50.0])

        assert mock_dl.call_count == 1
        assert result.exists()

    @pytest.mark.asyncio
    async def test_aifs_live_mode_uses_cache(self, tmp_path):
        """When the destination file already exists it is returned immediately."""
        import datetime

        date = datetime.date(2024, 1, 1)
        cached = _write_dummy_file(tmp_path / "aifs_20240101_step000.grib2")

        mock_settings = MagicMock()
        mock_settings.air_gap_mode = False
        mock_settings.data_input_dir = tmp_path

        with patch("src.ingestion.aifs_client.get_settings", return_value=mock_settings):
            client = AIFSClient()
            with patch.object(client, "_ecmwf_download") as mock_dl:
                result = await client.fetch(
                    bounding_box=[-10.0, 35.0, 10.0, 50.0],
                    date=date,
                )

        mock_dl.assert_not_called()
        assert result == cached


# ---------------------------------------------------------------------------
# CMEMS Client Tests
# ---------------------------------------------------------------------------

class TestCMEMSClient:
    """Tests for CMEMSClient with all I/O mocked."""

    def test_cmems_air_gap_mode_finds_local_file(self, tmp_path):
        """Client returns the first cmems_*.nc file in data_input_dir."""
        dummy = _write_dummy_file(tmp_path / "cmems_20240101.nc")

        mock_settings = MagicMock()
        mock_settings.air_gap_mode = True
        mock_settings.data_input_dir = tmp_path

        with patch("src.ingestion.cmems_client.get_settings", return_value=mock_settings):
            client = CMEMSClient()
            result = asyncio.get_event_loop().run_until_complete(
                client.fetch(bounding_box=[-10.0, 35.0, 10.0, 50.0])
            )

        assert result == dummy

    def test_cmems_air_gap_mode_no_file_raises(self, tmp_path):
        """Client raises CMEMSClientError when no local NC file is found."""
        mock_settings = MagicMock()
        mock_settings.air_gap_mode = True
        mock_settings.data_input_dir = tmp_path

        with patch("src.ingestion.cmems_client.get_settings", return_value=mock_settings):
            client = CMEMSClient()
            with pytest.raises(CMEMSClientError, match="cmems_\\*.nc"):
                asyncio.get_event_loop().run_until_complete(
                    client.fetch(bounding_box=[-10.0, 35.0, 10.0, 50.0])
                )

    @pytest.mark.asyncio
    async def test_cmems_live_mode_calls_subset(self, tmp_path):
        """In live mode, copernicusmarine.subset is invoked."""
        mock_settings = MagicMock()
        mock_settings.air_gap_mode = False
        mock_settings.data_input_dir = tmp_path
        mock_settings.cmems_username = "user"
        mock_settings.cmems_password = "pass"

        with patch("src.ingestion.cmems_client.get_settings", return_value=mock_settings):
            client = CMEMSClient()
            with patch.object(
                client,
                "_copernicusmarine_subset",
                side_effect=lambda **kw: kw["dest"].write_bytes(b"\x00" * 32),
            ) as mock_sub:
                result = await client.fetch(bounding_box=[-10.0, 35.0, 10.0, 50.0])

        # Either the primary or fallback call should have been made
        assert mock_sub.call_count >= 1
        assert result.exists()

    @pytest.mark.asyncio
    async def test_cmems_live_mode_falls_back_without_stokes(self, tmp_path):
        """Stokes-drift failure is swallowed and subset retried without them."""
        import datetime

        mock_settings = MagicMock()
        mock_settings.air_gap_mode = False
        mock_settings.data_input_dir = tmp_path
        mock_settings.cmems_username = ""
        mock_settings.cmems_password = ""

        call_count = 0

        def fake_subset(**kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("vsdx not available")
            # Second call succeeds
            kw["dest"].write_bytes(b"\x00" * 32)

        with patch("src.ingestion.cmems_client.get_settings", return_value=mock_settings):
            client = CMEMSClient()
            with patch.object(client, "_copernicusmarine_subset", side_effect=fake_subset):
                result = await client.fetch(
                    bounding_box=[-10.0, 35.0, 10.0, 50.0],
                    date=datetime.date(2024, 1, 1),
                )

        assert call_count == 2
        assert result.exists()


# ---------------------------------------------------------------------------
# GraphCast Client Tests
# ---------------------------------------------------------------------------

class TestGraphCastClient:
    """Tests for GraphCastClient with all I/O mocked."""

    def test_graphcast_air_gap_mode_finds_local_file(self, tmp_path):
        """Client returns the first graphcast_*.nc file in data_input_dir."""
        dummy = _write_dummy_file(tmp_path / "graphcast_20240101_step000.nc")

        mock_settings = MagicMock()
        mock_settings.air_gap_mode = True
        mock_settings.data_input_dir = tmp_path

        with patch("src.ingestion.graphcast_client.get_settings", return_value=mock_settings):
            client = GraphCastClient()
            result = asyncio.get_event_loop().run_until_complete(
                client.fetch(bounding_box=[-10.0, 35.0, 10.0, 50.0])
            )

        assert result == dummy

    def test_graphcast_air_gap_mode_no_file_raises(self, tmp_path):
        """Client raises GraphCastClientError when no local NC file is found."""
        mock_settings = MagicMock()
        mock_settings.air_gap_mode = True
        mock_settings.data_input_dir = tmp_path

        with patch("src.ingestion.graphcast_client.get_settings", return_value=mock_settings):
            client = GraphCastClient()
            with pytest.raises(GraphCastClientError, match="graphcast_\\*.nc"):
                asyncio.get_event_loop().run_until_complete(
                    client.fetch(bounding_box=[-10.0, 35.0, 10.0, 50.0])
                )

    @pytest.mark.asyncio
    async def test_graphcast_live_mode_streams_from_gcs(self, tmp_path):
        """In live mode, httpx is used to stream from GCS."""
        mock_settings = MagicMock()
        mock_settings.air_gap_mode = False
        mock_settings.data_input_dir = tmp_path

        with patch("src.ingestion.graphcast_client.get_settings", return_value=mock_settings):
            client = GraphCastClient()
            with patch.object(
                client,
                "_stream_to_file",
                new_callable=AsyncMock,
                side_effect=lambda url, dest: dest.write_bytes(b"\x00" * 32),
            ) as mock_stream:
                result = await client.fetch(bounding_box=[-10.0, 35.0, 10.0, 50.0])

        mock_stream.assert_called_once()
        assert result.exists()

    @pytest.mark.asyncio
    async def test_graphcast_live_mode_uses_cache(self, tmp_path):
        """When destination file already exists, stream is not called."""
        import datetime

        date = datetime.date(2024, 1, 1)
        cached = _write_dummy_file(tmp_path / "graphcast_20240101_step000.nc")

        mock_settings = MagicMock()
        mock_settings.air_gap_mode = False
        mock_settings.data_input_dir = tmp_path

        with patch("src.ingestion.graphcast_client.get_settings", return_value=mock_settings):
            client = GraphCastClient()
            with patch.object(
                client, "_stream_to_file", new_callable=AsyncMock
            ) as mock_stream:
                result = await client.fetch(
                    bounding_box=[-10.0, 35.0, 10.0, 50.0],
                    date=date,
                )

        mock_stream.assert_not_called()
        assert result == cached


# ---------------------------------------------------------------------------
# LocalWatcher Tests
# ---------------------------------------------------------------------------

class TestLocalWatcher:
    """Tests for LocalWatcher with watchfiles mocked."""

    @pytest.mark.asyncio
    async def test_local_watcher_emits_on_new_file(self, tmp_path):
        """Watcher emits a Path when watchfiles reports a new .nc file."""
        new_file = tmp_path / "cmems_20240101.nc"
        _write_dummy_file(new_file)

        mock_settings = MagicMock()
        mock_settings.data_input_dir = tmp_path

        # Simulate watchfiles yielding one set of changes then stopping
        from watchfiles import Change

        async def _fake_awatch(*args, **kwargs):
            yield {(Change.added, str(new_file))}
            # After one iteration, do not yield again → watcher should exit
            # We raise CancelledError to simulate graceful shutdown
            raise asyncio.CancelledError

        with patch("src.ingestion.local_watcher.get_settings", return_value=mock_settings):
            with patch("src.ingestion.local_watcher.awatch", side_effect=_fake_awatch):
                watcher = LocalWatcher()
                queue: asyncio.Queue[Path] = asyncio.Queue()

                # The watcher will raise CancelledError after one batch
                with pytest.raises(asyncio.CancelledError):
                    await watcher.watch(queue)

        # The file emitted via existing-scan or via change should be in queue
        items = []
        while not queue.empty():
            items.append(queue.get_nowait())

        assert any(p == new_file for p in items), (
            f"Expected {new_file} in queue, got {items}"
        )

    @pytest.mark.asyncio
    async def test_local_watcher_ignores_non_data_files(self, tmp_path):
        """Watcher must not emit .txt or other non-data-format files."""
        txt_file = tmp_path / "readme.txt"
        _write_dummy_file(txt_file)

        mock_settings = MagicMock()
        mock_settings.data_input_dir = tmp_path

        from watchfiles import Change

        async def _fake_awatch(*args, **kwargs):
            yield {(Change.added, str(txt_file))}
            raise asyncio.CancelledError

        with patch("src.ingestion.local_watcher.get_settings", return_value=mock_settings):
            with patch("src.ingestion.local_watcher.awatch", side_effect=_fake_awatch):
                watcher = LocalWatcher()
                queue: asyncio.Queue[Path] = asyncio.Queue()
                with pytest.raises(asyncio.CancelledError):
                    await watcher.watch(queue)

        # txt file should not appear (it may have been scanned out by existing-scan,
        # but it has .txt suffix so is excluded)
        items = []
        while not queue.empty():
            items.append(queue.get_nowait())
        assert txt_file not in items

    @pytest.mark.asyncio
    async def test_local_watcher_emits_existing_files_on_startup(self, tmp_path):
        """Files already present in the directory are emitted before watching."""
        existing = _write_dummy_file(tmp_path / "aifs_20240101_step000.grib2")

        mock_settings = MagicMock()
        mock_settings.data_input_dir = tmp_path

        async def _fake_awatch(*args, **kwargs):
            # Raise immediately — no new change events
            raise asyncio.CancelledError
            yield  # make it a generator

        with patch("src.ingestion.local_watcher.get_settings", return_value=mock_settings):
            with patch("src.ingestion.local_watcher.awatch", side_effect=_fake_awatch):
                watcher = LocalWatcher()
                queue: asyncio.Queue[Path] = asyncio.Queue()
                with pytest.raises(asyncio.CancelledError):
                    await watcher.watch(queue)

        items = []
        while not queue.empty():
            items.append(queue.get_nowait())
        assert existing in items

    @pytest.mark.asyncio
    async def test_local_watcher_skips_unreadable_file(self, tmp_path):
        """Zero-byte files must not be emitted."""
        empty_file = tmp_path / "empty.nc"
        empty_file.touch()  # 0 bytes

        mock_settings = MagicMock()
        mock_settings.data_input_dir = tmp_path

        from watchfiles import Change

        async def _fake_awatch(*args, **kwargs):
            yield {(Change.added, str(empty_file))}
            raise asyncio.CancelledError

        with patch("src.ingestion.local_watcher.get_settings", return_value=mock_settings):
            with patch("src.ingestion.local_watcher.awatch", side_effect=_fake_awatch):
                watcher = LocalWatcher()
                queue: asyncio.Queue[Path] = asyncio.Queue()
                with pytest.raises(asyncio.CancelledError):
                    await watcher.watch(queue)

        items = []
        while not queue.empty():
            items.append(queue.get_nowait())
        assert empty_file not in items


# ---------------------------------------------------------------------------
# Integration-level: IngestResult schema compatibility
# ---------------------------------------------------------------------------

class TestIngestResultSchemaCompat:
    """Verify that our outputs conform to the IngestResult contract."""

    def test_ingest_result_can_be_constructed(self, tmp_path):
        """Smoke-test: IngestResult can be built with values from ingestion."""
        import datetime
        import uuid

        from src.api.schemas import IngestResult

        ir = IngestResult(
            run_id=str(uuid.uuid4()),
            timestamp=datetime.datetime.now(tz=datetime.UTC),
            bounding_box=[-10.0, 35.0, 10.0, 50.0],
            atmospheric_vars=["u10", "v10", "msl"],
            ocean_vars=["uo", "vo", "zos", "vsdx", "vsdy"],
            dataset_path=str(tmp_path / "harmonized.nc"),
            air_gap_mode=True,
            source_files=[
                str(tmp_path / "aifs_20240101.grib2"),
                str(tmp_path / "cmems_20240101.nc"),
            ],
            grid_resolution_deg=0.25,
        )
        assert ir.air_gap_mode is True
        assert len(ir.atmospheric_vars) == 3
        assert len(ir.ocean_vars) == 5
        assert ir.grid_resolution_deg == 0.25
