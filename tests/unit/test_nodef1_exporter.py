"""
Unit tests for STANAG 1317 NODEF-1 Binary Exporter.

Tests export/parse round-trips on a synthetic 2×2 grid NetCDF dataset
containing all five recognised ocean variables (uo, vo, zos, vsdx, vsdy).
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.nato.nodef1_exporter import Nodef1Exporter


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def synthetic_dataset(tmp_path: Path) -> str:
    """
    Create a minimal synthetic xr.Dataset with all NODEF-1 ocean variables.

    Grid: 2×2 (lat×lon), 3 timesteps.
    Variables: uo, vo, zos, vsdx, vsdy.
    """
    lats = [51.0, 51.25]
    lons = [2.0, 2.25]
    times = np.array(
        ["2024-06-01T00:00:00", "2024-06-01T01:00:00", "2024-06-01T02:00:00"],
        dtype="datetime64[ns]",
    )

    shape = (3, 2, 2)
    rng = np.random.default_rng(7)

    ds = xr.Dataset(
        {
            "uo":   (["time", "lat", "lon"], rng.uniform(-1.0, 1.0, shape).astype(np.float32)),
            "vo":   (["time", "lat", "lon"], rng.uniform(-1.0, 1.0, shape).astype(np.float32)),
            "zos":  (["time", "lat", "lon"], rng.uniform(-0.5, 0.5, shape).astype(np.float32)),
            "vsdx": (["time", "lat", "lon"], rng.uniform(-0.2, 0.2, shape).astype(np.float32)),
            "vsdy": (["time", "lat", "lon"], rng.uniform(-0.2, 0.2, shape).astype(np.float32)),
            # Extra atmospheric vars that should be ignored
            "u10":  (["time", "lat", "lon"], rng.uniform(-10, 10, shape).astype(np.float32)),
        },
        coords={
            "lat": lats,
            "lon": lons,
            "time": times,
        },
    )

    nc_path = tmp_path / "ocean_synthetic.nc"
    ds.to_netcdf(nc_path)
    return str(nc_path)


@pytest.fixture()
def exporter() -> Nodef1Exporter:
    """Return a default Nodef1Exporter instance."""
    return Nodef1Exporter()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestNodef1ExportOutputFile:
    """Verify that export() produces the expected binary output file."""

    def test_export_produces_binary_file(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """The .nodef1.bin file must exist and be non-empty after export."""
        result = exporter.export(synthetic_dataset, run_id="nd-001", output_dir=tmp_path)
        out_path = Path(result.binary_path)
        assert out_path.exists(), ".nodef1.bin output file not found"
        assert out_path.stat().st_size > 0, ".nodef1.bin output file is empty"

    def test_magic_bytes_present(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """The first 4 bytes of the file must equal b'NODF' (0x4E4F4446)."""
        result = exporter.export(synthetic_dataset, run_id="nd-002", output_dir=tmp_path)
        raw = Path(result.binary_path).read_bytes()
        assert raw[:4] == b"NODF", (
            f"Expected magic b'NODF', got {raw[:4]!r}"
        )

    def test_checksum_sha256_in_result(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """checksum_sha256 must be a 64-character lowercase hex string."""
        result = exporter.export(synthetic_dataset, run_id="nd-003", output_dir=tmp_path)
        sha = result.checksum_sha256
        assert isinstance(sha, str), "checksum_sha256 is not a string"
        assert len(sha) == 64, f"Expected 64-char SHA-256 hex, got length {len(sha)}"
        assert all(c in "0123456789abcdef" for c in sha), (
            "checksum_sha256 contains non-hex characters"
        )

    def test_record_count_matches_variables(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """
        Dataset has 5 recognised ocean vars (uo, vo, zos, vsdx, vsdy) →
        record_count must equal 5.  The u10 variable must be ignored.
        """
        result = exporter.export(synthetic_dataset, run_id="nd-004", output_dir=tmp_path)
        assert result.record_count == 5, (
            f"Expected record_count=5 for 5 ocean variables, got {result.record_count}"
        )


class TestNodef1RoundTrip:
    """Verify parse() correctly reconstructs records written by export()."""

    def test_round_trip_data_integrity(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """
        float32 values survive export → parse with tolerance ≤ 1e-5.

        This verifies that the struct.pack / struct.unpack cycle (via the data
        block) is lossless within float32 precision.
        """
        import xarray as xr

        result = exporter.export(synthetic_dataset, run_id="rt-001", output_dir=tmp_path)
        parsed = exporter.parse(result.binary_path)

        assert len(parsed) == 5, f"Expected 5 parsed records, got {len(parsed)}"

        # Reload original dataset to compare first time slice
        ds_orig = xr.open_dataset(synthetic_dataset)
        var_names = ["uo", "vo", "zos", "vsdx", "vsdy"]

        for i, (var_name, rec) in enumerate(zip(var_names, parsed)):
            orig_slice = ds_orig[var_name].isel(time=0).values.astype(np.float32)
            # Replace NaN with 0.0 to match exporter behaviour
            orig_slice = np.where(np.isfinite(orig_slice), orig_slice, 0.0)

            np.testing.assert_allclose(
                rec["data"].flatten(),
                orig_slice.flatten(),
                atol=1e-5,
                err_msg=f"Round-trip data mismatch for variable {var_name} (record {i})",
            )

        ds_orig.close()

    def test_parse_returns_correct_record_count(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """parse() must return exactly one dict per exported record."""
        result = exporter.export(synthetic_dataset, run_id="rt-002", output_dir=tmp_path)
        parsed = exporter.parse(result.binary_path)
        assert len(parsed) == result.record_count

    def test_parse_magic_matches_class_constant(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """Every parsed record must report magic == Nodef1Exporter.MAGIC."""
        result = exporter.export(synthetic_dataset, run_id="rt-003", output_dir=tmp_path)
        parsed = exporter.parse(result.binary_path)
        for i, rec in enumerate(parsed):
            assert rec["magic"] == Nodef1Exporter.MAGIC, (
                f"Record {i}: magic {rec['magic']!r} != expected {Nodef1Exporter.MAGIC!r}"
            )

    def test_parse_crc32_ok(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """All parsed records must have crc32_ok == True."""
        result = exporter.export(synthetic_dataset, run_id="rt-004", output_dir=tmp_path)
        parsed = exporter.parse(result.binary_path)
        for i, rec in enumerate(parsed):
            assert rec["crc32_ok"] is True, f"CRC-32 mismatch in record {i}"


class TestNodef1BinaryLayout:
    """Verify raw binary layout compliance with the NODEF-1 spec."""

    def test_first_record_version_field(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """The version field (bytes 4-6) must equal 0x0001."""
        result = exporter.export(synthetic_dataset, run_id="lay-001", output_dir=tmp_path)
        raw = Path(result.binary_path).read_bytes()
        (version,) = struct.unpack_from(">H", raw, 4)
        assert version == 0x0001, f"Expected version 0x0001, got 0x{version:04X}"

    def test_record_type_is_valid(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """The first record's record_type must be one of the defined type codes."""
        valid_types = {0x0010, 0x0020, 0x0030}
        result = exporter.export(synthetic_dataset, run_id="lay-002", output_dir=tmp_path)
        raw = Path(result.binary_path).read_bytes()
        (record_type,) = struct.unpack_from(">H", raw, 6)
        assert record_type in valid_types, (
            f"Unexpected record_type 0x{record_type:04X}; expected one of "
            f"{[hex(t) for t in valid_types]}"
        )

    def test_grid_dimensions_encoded_correctly(
        self,
        exporter: Nodef1Exporter,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """nlat and nlon in the binary header must match the 2×2 synthetic grid."""
        result = exporter.export(synthetic_dataset, run_id="lay-003", output_dir=tmp_path)
        parsed = exporter.parse(result.binary_path)
        for rec in parsed:
            assert rec["nlat"] == 2, f"Expected nlat=2, got {rec['nlat']}"
            assert rec["nlon"] == 2, f"Expected nlon=2, got {rec['nlon']}"
