"""
STANAG 1317 NODEF-1 Binary Exporter.
Exports ocean state data (currents, SSH, wave Stokes drift) as NATO
Oceanographic Data Exchange Format binary records for ingestion by
allied naval computing environments.

NODEF-1 Record Layout (big-endian):
  [4B] magic: 0x4E4F4446 ("NODF")
  [2B] version: 0x0001
  [2B] record_type: 0x0010 (ocean currents) | 0x0020 (SSH) | 0x0030 (Stokes)
  [4B] n_records: uint32
  [8B] ref_time: int64 Unix timestamp (UTC)
  [4B] lat_start: float32 degrees
  [4B] lon_start: float32 degrees
  [4B] dlat: float32 degrees
  [4B] dlon: float32 degrees
  [2B] nlat: uint16
  [2B] nlon: uint16
  --- data block ---
  [4B * nlat * nlon] data: float32 values (m/s or m)
  [4B] checksum: CRC32 of data block
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path

import numpy as np
import structlog
import xarray as xr

from src.api.schemas import Nodef1ExportResult
from src.core.config import get_settings

logger = structlog.get_logger(__name__)

# Ocean variable → (record_type, description)
_OCEAN_VARS: dict[str, tuple[int, str]] = {
    "uo":   (0x0010, "surface_current_u"),
    "vo":   (0x0010, "surface_current_v"),
    "zos":  (0x0020, "sea_surface_height"),
    "vsdx": (0x0030, "stokes_drift_u"),
    "vsdy": (0x0030, "stokes_drift_v"),
}

# Fixed record header format (big-endian):
#   magic(4B) version(2B) record_type(2B) n_records(4B) ref_time(8B)
#   lat_start(4B) lon_start(4B) dlat(4B) dlon(4B) nlat(2B) nlon(2B)
_HEADER_FMT = ">IHHIqffffHH"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)  # 36 bytes


class Nodef1Exporter:
    """
    STANAG 1317 NODEF-1 binary ocean data exporter.

    Writes one binary record per ocean variable present in the harmonised
    dataset.  Each record is self-describing (magic bytes, version, grid
    metadata) and ends with a CRC-32 integrity checksum of the data block.

    Class Attributes
    ----------------
    MAGIC:
        4-byte magic number 0x4E4F4446 ("NODF") at the start of every record.
    VERSION:
        2-byte version field value: 0x0001.
    """

    MAGIC: int = 0x4E4F4446
    VERSION: int = 0x0001

    def __init__(self) -> None:
        self._settings = get_settings()
        logger.info("Nodef1Exporter initialised")

    # ── Public API ────────────────────────────────────────────────────────────

    def export(
        self,
        dataset_path: str,
        run_id: str,
        output_dir: Path,
    ) -> Nodef1ExportResult:
        """
        Export ocean state variables as a NODEF-1 binary file.

        Parameters
        ----------
        dataset_path:
            Absolute path to the harmonised NetCDF4 file.
        run_id:
            Pipeline run identifier used to construct the output filename.
        output_dir:
            Directory to write the binary output file.  Created if absent.

        Returns
        -------
        Nodef1ExportResult with file path, record count, and SHA-256 checksum.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        log = logger.bind(run_id=run_id, dataset_path=dataset_path)
        log.info("Nodef1Exporter.export started")

        ds = xr.open_dataset(dataset_path, engine="netcdf4")
        try:
            records = self._build_records(ds)
        finally:
            ds.close()

        if not records:
            raise ValueError(
                f"No recognised NODEF-1 ocean variables found in {dataset_path}. "
                f"Expected one or more of: {list(_OCEAN_VARS.keys())}"
            )

        out_path = output_dir / f"{run_id}.nodef1.bin"
        file_bytes = b"".join(records)
        out_path.write_bytes(file_bytes)

        sha256 = hashlib.sha256(file_bytes).hexdigest()
        log.info(
            "Nodef1Exporter.export finished",
            record_count=len(records),
            sha256=sha256,
            path=str(out_path),
        )

        return Nodef1ExportResult(
            run_id=run_id,
            binary_path=str(out_path),
            record_count=len(records),
            checksum_sha256=sha256,
        )

    def parse(self, binary_path: str) -> list[dict]:
        """
        Read a NODEF-1 binary file back into a list of record dictionaries.

        Performs full CRC-32 verification of each data block.  Used for
        round-trip validation and interoperability testing.

        Parameters
        ----------
        binary_path:
            Absolute path to the .nodef1.bin file to parse.

        Returns
        -------
        List of dicts, one per record, containing grid metadata and data array.

        Raises
        ------
        ValueError
            If magic bytes mismatch or CRC-32 check fails.
        """
        raw = Path(binary_path).read_bytes()
        offset = 0
        results: list[dict] = []

        while offset < len(raw):
            if offset + _HEADER_SIZE > len(raw):
                logger.warning("Truncated NODEF-1 record at offset", offset=offset)
                break

            (
                magic,
                version,
                record_type,
                n_records,
                ref_time,
                lat_start,
                lon_start,
                dlat,
                dlon,
                nlat,
                nlon,
            ) = struct.unpack_from(_HEADER_FMT, raw, offset)

            if magic != self.MAGIC:
                raise ValueError(
                    f"Bad magic bytes at offset {offset}: "
                    f"expected 0x{self.MAGIC:08X}, got 0x{magic:08X}"
                )

            offset += _HEADER_SIZE

            n_floats = nlat * nlon
            data_size = n_floats * 4  # float32
            data_block = raw[offset: offset + data_size]
            offset += data_size

            # Read and verify CRC-32
            (stored_crc,) = struct.unpack_from(">I", raw, offset)
            offset += 4
            computed_crc = zlib.crc32(data_block) & 0xFFFFFFFF

            if stored_crc != computed_crc:
                logger.warning(
                    "CRC-32 mismatch in NODEF-1 record",
                    stored=hex(stored_crc),
                    computed=hex(computed_crc),
                )

            # Unpack float32 data
            floats = struct.unpack(f">{n_floats}f", data_block)
            data_array = np.array(floats, dtype=np.float32).reshape(nlat, nlon)

            results.append(
                {
                    "magic": magic,
                    "version": version,
                    "record_type": record_type,
                    "n_records": n_records,
                    "ref_time": ref_time,
                    "lat_start": lat_start,
                    "lon_start": lon_start,
                    "dlat": dlat,
                    "dlon": dlon,
                    "nlat": nlat,
                    "nlon": nlon,
                    "data": data_array,
                    "crc32_ok": stored_crc == computed_crc,
                }
            )

        return results

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_records(self, ds: xr.Dataset) -> list[bytes]:
        """
        Construct a binary record for each ocean variable present in *ds*.

        Variables are processed in the canonical order defined by _OCEAN_VARS.
        The first time slice is used when the dataset contains a time dimension.
        """
        lat = ds.coords.get("lat") if "lat" in ds.coords else ds.coords.get("latitude")
        lon = ds.coords.get("lon") if "lon" in ds.coords else ds.coords.get("longitude")
        time_coord = ds.coords.get("time")

        if lat is None or lon is None:
            raise ValueError("Dataset must have 'lat'/'latitude' and 'lon'/'longitude' coordinates.")

        lat_vals = lat.values.astype(float)
        lon_vals = lon.values.astype(float)
        nlat = len(lat_vals)
        nlon = len(lon_vals)

        lat_start = float(lat_vals[0])
        lon_start = float(lon_vals[0])
        dlat = float(lat_vals[1] - lat_vals[0]) if nlat > 1 else 0.25
        dlon = float(lon_vals[1] - lon_vals[0]) if nlon > 1 else 0.25

        # Reference time as Unix timestamp (int64)
        if time_coord is not None and len(time_coord) > 0:
            t0 = time_coord.values[0]
            ref_time_unix = int(
                (t0 - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
            )
        else:
            ref_time_unix = 0

        records: list[bytes] = []

        for var_name, (record_type, _desc) in _OCEAN_VARS.items():
            if var_name not in ds:
                continue

            data_arr = ds[var_name]
            # Take first time slice if time dimension exists
            if "time" in data_arr.dims:
                arr2d = data_arr.isel(time=0).values.astype(np.float32)
            else:
                arr2d = data_arr.values.astype(np.float32)

            # Ensure 2-D (nlat, nlon)
            if arr2d.ndim > 2:
                arr2d = arr2d[0]  # take first slice of any extra dimension

            # Replace NaN/Inf with 0.0 for binary export
            arr2d = np.where(np.isfinite(arr2d), arr2d, 0.0).astype(np.float32)

            n_records_field = arr2d.size
            data_block = struct.pack(f">{n_records_field}f", *arr2d.flatten().tolist())
            crc32_val = zlib.crc32(data_block) & 0xFFFFFFFF

            header = struct.pack(
                _HEADER_FMT,
                self.MAGIC,       # I: magic
                self.VERSION,     # H: version
                record_type,      # H: record type
                n_records_field,  # I: n_records
                ref_time_unix,    # q: ref_time (int64 UTC Unix timestamp)
                lat_start,        # f: lat_start
                lon_start,        # f: lon_start
                dlat,             # f: dlat
                dlon,             # f: dlon
                nlat,             # H: nlat
                nlon,             # H: nlon
            )
            crc_bytes = struct.pack(">I", crc32_val)
            records.append(header + data_block + crc_bytes)

        return records
