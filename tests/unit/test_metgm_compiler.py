"""
Unit tests for STANAG 6015 METGM Compiler.

Tests compile XML and binary outputs from a synthetic 2×2 grid,
3-timestep NetCDF dataset covering all six METGM parameter groups.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest
import xarray as xr
from lxml import etree

from src.nato.metgm_compiler import MetgmCompiler


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def synthetic_dataset(tmp_path: Path) -> str:
    """
    Create a minimal synthetic xr.Dataset and save as NetCDF.

    Grid: 2×2 (lat×lon), 3 timesteps.
    Variables: u10, v10, msl, uo, vo, zos — all required METGM parameters.
    """
    lats = [51.0, 51.25]
    lons = [2.0, 2.25]
    times = np.array(
        ["2024-06-01T00:00:00", "2024-06-01T01:00:00", "2024-06-01T02:00:00"],
        dtype="datetime64[ns]",
    )

    shape = (3, 2, 2)  # (time, lat, lon)
    rng = np.random.default_rng(42)

    ds = xr.Dataset(
        {
            "u10": (["time", "lat", "lon"], rng.uniform(-10, 10, shape).astype(np.float32)),
            "v10": (["time", "lat", "lon"], rng.uniform(-10, 10, shape).astype(np.float32)),
            "msl": (["time", "lat", "lon"], rng.uniform(99_000, 103_000, shape).astype(np.float32)),
            "uo":  (["time", "lat", "lon"], rng.uniform(-1, 1, shape).astype(np.float32)),
            "vo":  (["time", "lat", "lon"], rng.uniform(-1, 1, shape).astype(np.float32)),
            "zos": (["time", "lat", "lon"], rng.uniform(-0.5, 0.5, shape).astype(np.float32)),
        },
        coords={
            "lat": lats,
            "lon": lons,
            "time": times,
        },
    )

    nc_path = tmp_path / "synthetic.nc"
    ds.to_netcdf(nc_path)
    return str(nc_path)


@pytest.fixture()
def compiler(tmp_path: Path) -> MetgmCompiler:
    """Return a MetgmCompiler writing to tmp_path."""
    return MetgmCompiler(output_dir=tmp_path / "metgm_out")


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestMetgmCompilerOutputFiles:
    """Verify that compile() produces the expected output files."""

    def test_compile_produces_xml_and_binary(
        self,
        compiler: MetgmCompiler,
        synthetic_dataset: str,
        tmp_path: Path,
    ) -> None:
        """Both the .metgm.xml and .metgm.bin files must exist after compile()."""
        result = compiler.compile(synthetic_dataset, run_id="run-001")
        assert Path(result.xml_path).exists(), "XML output file not found"
        assert Path(result.binary_path).exists(), "Binary output file not found"

    def test_xml_has_required_elements(
        self,
        compiler: MetgmCompiler,
        synthetic_dataset: str,
    ) -> None:
        """The XML document must have a METGM root with ParameterGroup children."""
        result = compiler.compile(synthetic_dataset, run_id="run-002")
        tree = etree.parse(result.xml_path)
        root = tree.getroot()

        assert root.tag == "METGM", f"Expected root tag 'METGM', got '{root.tag}'"
        param_groups = root.findall("ParameterGroup")
        assert len(param_groups) > 0, "Expected at least one ParameterGroup element"

        for pg in param_groups:
            assert pg.find("GridDescriptor") is not None, "Missing GridDescriptor"
            assert pg.find("TimeSteps") is not None, "Missing TimeSteps"
            assert pg.find("DataChecksum") is not None, "Missing DataChecksum"

    def test_xml_validation_passes(
        self,
        compiler: MetgmCompiler,
        synthetic_dataset: str,
    ) -> None:
        """MetgmExportResult.schema_valid must be True for a valid dataset."""
        result = compiler.compile(synthetic_dataset, run_id="run-003")
        assert result.schema_valid is True, (
            "XML XSD validation failed — schema_valid should be True"
        )


class TestMetgmBinaryFormat:
    """Verify the binary output format and structure."""

    def test_binary_header_magic_parseable(
        self,
        compiler: MetgmCompiler,
        synthetic_dataset: str,
    ) -> None:
        """
        The first binary record header must be parseable and contain
        a valid p_id (one of the known STANAG 6015 parameter IDs).
        """
        result = compiler.compile(synthetic_dataset, run_id="run-004")
        raw = Path(result.binary_path).read_bytes()

        # Parse first parameter group header: struct.pack(">HHHHHf", ...)
        header_fmt = ">HHHHHf"
        header_size = struct.calcsize(header_fmt)
        assert len(raw) >= header_size, "Binary file shorter than one header"

        p_id, nt, nlat, nlon, nd, fill_val = struct.unpack_from(header_fmt, raw, 0)
        valid_p_ids = {1, 2, 3, 10, 11, 20}
        assert p_id in valid_p_ids, (
            f"First p_id {p_id} not in expected STANAG 6015 IDs {valid_p_ids}"
        )

    def test_parameter_count_matches_variables(
        self,
        compiler: MetgmCompiler,
        synthetic_dataset: str,
    ) -> None:
        """
        Dataset has 6 variables (u10, v10, msl, uo, vo, zos) →
        parameter_count must equal 6.
        """
        result = compiler.compile(synthetic_dataset, run_id="run-005")
        assert result.parameter_count == 6, (
            f"Expected parameter_count=6, got {result.parameter_count}"
        )


class TestMetgmExportResultFields:
    """Verify MetgmExportResult field values."""

    def test_result_grid_points_correct(
        self,
        compiler: MetgmCompiler,
        synthetic_dataset: str,
    ) -> None:
        """2×2 grid → grid_points must equal 4."""
        result = compiler.compile(synthetic_dataset, run_id="run-006")
        assert result.grid_points == 4, (
            f"Expected grid_points=4 for 2×2 grid, got {result.grid_points}"
        )

    def test_result_time_steps_correct(
        self,
        compiler: MetgmCompiler,
        synthetic_dataset: str,
    ) -> None:
        """Dataset has 3 timesteps → time_steps must equal 3."""
        result = compiler.compile(synthetic_dataset, run_id="run-007")
        assert result.time_steps == 3, (
            f"Expected time_steps=3, got {result.time_steps}"
        )

    def test_result_run_id_preserved(
        self,
        compiler: MetgmCompiler,
        synthetic_dataset: str,
    ) -> None:
        """run_id in result must match the one supplied to compile()."""
        result = compiler.compile(synthetic_dataset, run_id="sentinel-run-id")
        assert result.run_id == "sentinel-run-id"

    def test_xml_embeds_run_id(
        self,
        compiler: MetgmCompiler,
        synthetic_dataset: str,
    ) -> None:
        """The METGM root element must carry the run_id attribute."""
        result = compiler.compile(synthetic_dataset, run_id="embed-test")
        tree = etree.parse(result.xml_path)
        root = tree.getroot()
        assert root.get("run_id") == "embed-test"


class TestMetgmValidateXml:
    """Unit-test the validate_xml helper independently."""

    def test_validate_xml_returns_true_for_valid_file(
        self,
        compiler: MetgmCompiler,
        synthetic_dataset: str,
    ) -> None:
        """validate_xml() must return True for a freshly compiled file."""
        result = compiler.compile(synthetic_dataset, run_id="val-001")
        assert compiler.validate_xml(result.xml_path) is True

    def test_validate_xml_returns_false_for_corrupt_xml(
        self,
        compiler: MetgmCompiler,
        tmp_path: Path,
    ) -> None:
        """validate_xml() must return False for a syntactically broken file."""
        bad_xml = tmp_path / "bad.metgm.xml"
        bad_xml.write_bytes(b"<NOT_VALID_XML")
        assert compiler.validate_xml(str(bad_xml)) is False

    def test_validate_xml_returns_false_for_missing_file(
        self,
        compiler: MetgmCompiler,
        tmp_path: Path,
    ) -> None:
        """validate_xml() must return False when the file does not exist."""
        missing = tmp_path / "ghost.metgm.xml"
        assert compiler.validate_xml(str(missing)) is False
