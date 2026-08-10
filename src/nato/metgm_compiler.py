"""
STANAG 6015 (AMETOCP-4) METGM Compiler.
Serialises internal xarray Datasets into NATO Gridded Meteorological Messages
in both XML (human-readable) and binary (compact, allied system-compatible) formats.

METGM Structure:
  - File Header: version, classification, originator, ref time
  - Parameter Groups (one per variable):
    - Parameter Header: p_id (param ID), tz (time zones), np (n_points), nd (n_depths), nt (n_times)
    - Grid Descriptor: lat_start, lon_start, dlat, dlon, nlat, nlon
    - Data Block: float32 values in row-major order (lat-major, lon-minor)

STANAG 6015 Parameter IDs used:
  p_id=1: u-wind (m/s)
  p_id=2: v-wind (m/s)
  p_id=3: sea-level pressure (Pa)
  p_id=10: surface current u (m/s)
  p_id=11: surface current v (m/s)
  p_id=20: sea surface height (m)
"""
from __future__ import annotations

import hashlib
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import structlog
import xarray as xr
from lxml import etree

from src.api.schemas import MetgmExportResult
from src.core.config import get_settings

logger = structlog.get_logger(__name__)

# Mapping from variable name → (p_id, human name, unit)
_PARAM_MAP: dict[str, tuple[int, str, str]] = {
    "u10": (1, "u_wind", "m/s"),
    "v10": (2, "v_wind", "m/s"),
    "msl": (3, "sea_level_pressure", "Pa"),
    "uo":  (10, "surface_current_u", "m/s"),
    "vo":  (11, "surface_current_v", "m/s"),
    "zos": (20, "sea_surface_height", "m"),
}

# Minimal inline XSD for structural validation of METGM XML documents
_METGM_XSD = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="METGM">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="ParameterGroup" minOccurs="1" maxOccurs="unbounded">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="GridDescriptor">
                <xs:complexType>
                  <xs:attribute name="lat_start" type="xs:decimal" use="required"/>
                  <xs:attribute name="lon_start" type="xs:decimal" use="required"/>
                  <xs:attribute name="dlat"      type="xs:decimal" use="required"/>
                  <xs:attribute name="dlon"      type="xs:decimal" use="required"/>
                  <xs:attribute name="nlat"      type="xs:integer" use="required"/>
                  <xs:attribute name="nlon"      type="xs:integer" use="required"/>
                </xs:complexType>
              </xs:element>
              <xs:element name="TimeSteps">
                <xs:complexType>
                  <xs:attribute name="count"          type="xs:integer" use="required"/>
                  <xs:attribute name="interval_hours" type="xs:decimal" use="required"/>
                </xs:complexType>
              </xs:element>
              <xs:element name="DataChecksum">
                <xs:complexType>
                  <xs:attribute name="sha256" type="xs:string" use="required"/>
                </xs:complexType>
              </xs:element>
            </xs:sequence>
            <xs:attribute name="p_id" type="xs:integer" use="required"/>
            <xs:attribute name="name" type="xs:string"  use="required"/>
            <xs:attribute name="unit" type="xs:string"  use="required"/>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
      <xs:attribute name="version"        type="xs:string" use="required"/>
      <xs:attribute name="classification" type="xs:string" use="required"/>
      <xs:attribute name="run_id"         type="xs:string" use="required"/>
      <xs:attribute name="ref_time"       type="xs:string" use="required"/>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""


class MetgmCompiler:
    """
    STANAG 6015 / AMETOCP-4 Gridded Meteorological Message compiler.

    Produces both an XML (human-readable) and a flat binary representation
    of all recognised METGM parameter groups found in the input NetCDF dataset.

    Parameters
    ----------
    output_dir:
        Directory to write output files.  Created if it does not exist.
    classification:
        NATO document classification string embedded in the file header.
    """

    METGM_VERSION = "4.0"
    FILL_VALUE: float = -9999.0

    def __init__(
        self,
        output_dir: Path,
        classification: str = "UNCLASSIFIED",
    ) -> None:
        self._settings = get_settings()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.classification = classification

        # Parse XSD once and reuse
        self._xsd_schema: etree.XMLSchema = etree.XMLSchema(etree.fromstring(_METGM_XSD))

        logger.info(
            "MetgmCompiler initialised",
            output_dir=str(self.output_dir),
            classification=classification,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def compile(self, dataset_path: str, run_id: str) -> MetgmExportResult:
        """
        Compile METGM XML and binary outputs from a harmonised NetCDF dataset.

        Parameters
        ----------
        dataset_path:
            Absolute path to the harmonised NetCDF4 file.
        run_id:
            Pipeline run identifier embedded in output filenames and XML header.

        Returns
        -------
        MetgmExportResult with paths, counts, and validation status.
        """
        log = logger.bind(run_id=run_id, dataset_path=dataset_path)
        log.info("MetgmCompiler.compile started")

        ds = xr.open_dataset(dataset_path, engine="netcdf4")
        try:
            params = self._extract_parameters(ds)
            if not params:
                raise ValueError(
                    f"No recognised METGM variables found in {dataset_path}. "
                    f"Expected one or more of: {list(_PARAM_MAP.keys())}"
                )

            ref_time = self._extract_ref_time(ds)
            xml_path = self.output_dir / f"{run_id}.metgm.xml"
            bin_path = self.output_dir / f"{run_id}.metgm.bin"

            # --- XML ---
            xml_doc = self._build_xml(params, run_id, ref_time)
            xml_bytes = etree.tostring(xml_doc, pretty_print=True, xml_declaration=True, encoding="UTF-8")
            xml_path.write_bytes(xml_bytes)
            log.debug("METGM XML written", path=str(xml_path), size_bytes=len(xml_bytes))

            # Validate against inline XSD
            schema_valid = self.validate_xml(str(xml_path))

            # --- Binary ---
            self._write_binary(params, bin_path)
            log.debug("METGM binary written", path=str(bin_path))

            # Grid size from first parameter
            first = params[0]
            grid_points = int(first["nlat"]) * int(first["nlon"])
            time_steps = int(first["nt"])

            result = MetgmExportResult(
                run_id=run_id,
                xml_path=str(xml_path),
                binary_path=str(bin_path),
                parameter_count=len(params),
                grid_points=grid_points,
                time_steps=time_steps,
                schema_valid=schema_valid,
            )
            log.info(
                "MetgmCompiler.compile finished",
                parameter_count=len(params),
                schema_valid=schema_valid,
            )
            return result
        finally:
            ds.close()

    def validate_xml(self, xml_path: str) -> bool:
        """
        Validate a METGM XML file against the inline XSD schema.

        Parameters
        ----------
        xml_path:
            Absolute path to the XML file to validate.

        Returns
        -------
        True if validation passes, False otherwise.
        """
        try:
            doc = etree.parse(xml_path)
            valid = self._xsd_schema.validate(doc)
            if not valid:
                errors = self._xsd_schema.error_log
                logger.warning("METGM XML XSD validation failed", errors=str(errors))
            return valid
        except (etree.XMLSyntaxError, OSError) as exc:
            logger.error("METGM XML parse/validation error", exc=str(exc))
            return False

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_parameters(self, ds: xr.Dataset) -> list[dict[str, Any]]:
        """
        Build a list of parameter descriptors from the dataset variables.

        Each descriptor contains the raw numpy data plus grid metadata needed
        to produce both XML and binary representations.
        """
        params: list[dict[str, Any]] = []

        lat = ds.coords.get("lat") if "lat" in ds.coords else ds.coords.get("latitude")
        lon = ds.coords.get("lon") if "lon" in ds.coords else ds.coords.get("longitude")

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


        for var_name, (p_id, param_name, unit) in _PARAM_MAP.items():
            if var_name not in ds:
                continue

            data_arr = ds[var_name]
            # Ensure we have a 3-D array (time, lat, lon); squeeze out extra dims
            if "time" in data_arr.dims:
                data = data_arr.values.astype(np.float32)
                if data.ndim == 2:
                    data = data[np.newaxis, :, :]
            else:
                data = data_arr.values.astype(np.float32)
                if data.ndim == 2:
                    data = data[np.newaxis, :, :]

            # Replace NaN with fill value
            data = np.where(np.isfinite(data), data, self.FILL_VALUE).astype(np.float32)

            # SHA-256 checksum of data block bytes
            data_bytes = data.astype(">f4").tobytes()
            sha256 = hashlib.sha256(data_bytes).hexdigest()

            params.append(
                {
                    "p_id": p_id,
                    "name": param_name,
                    "unit": unit,
                    "data": data,
                    "nlat": nlat,
                    "nlon": nlon,
                    "nt": data.shape[0],
                    "nd": 1,
                    "lat_start": lat_start,
                    "lon_start": lon_start,
                    "dlat": round(dlat, 6),
                    "dlon": round(dlon, 6),
                    "sha256": sha256,
                }
            )

        return params

    def _extract_ref_time(self, ds: xr.Dataset) -> str:
        """Return ISO-8601 reference time from dataset time coordinate, or now."""
        time_coord = ds.coords.get("time")
        if time_coord is not None and len(time_coord) > 0:
            t0 = time_coord.values[0]
            # Convert numpy datetime64 → Python datetime
            ts = (t0 - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
            dt = datetime.fromtimestamp(float(ts), tz=UTC)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _build_xml(
        self,
        params: list[dict[str, Any]],
        run_id: str,
        ref_time: str,
    ) -> etree._Element:
        """Construct an lxml element tree for the METGM document."""
        root = etree.Element(
            "METGM",
            attrib={
                "version": self.METGM_VERSION,
                "classification": self.classification,
                "run_id": run_id,
                "ref_time": ref_time,
            },
        )

        for p in params:
            pg = etree.SubElement(
                root,
                "ParameterGroup",
                attrib={
                    "p_id": str(p["p_id"]),
                    "name": p["name"],
                    "unit": p["unit"],
                },
            )
            etree.SubElement(
                pg,
                "GridDescriptor",
                attrib={
                    "lat_start": str(p["lat_start"]),
                    "lon_start": str(p["lon_start"]),
                    "dlat": str(p["dlat"]),
                    "dlon": str(p["dlon"]),
                    "nlat": str(p["nlat"]),
                    "nlon": str(p["nlon"]),
                },
            )
            etree.SubElement(
                pg,
                "TimeSteps",
                attrib={
                    "count": str(p["nt"]),
                    "interval_hours": "1",
                },
            )
            etree.SubElement(
                pg,
                "DataChecksum",
                attrib={"sha256": p["sha256"]},
            )

        return root

    def _write_binary(self, params: list[dict[str, Any]], bin_path: Path) -> None:
        """
        Write the METGM binary file.

        Layout per parameter group:
          Header: struct.pack(">HHHHHf", p_id, nt, nlat, nlon, nd, fill_value)
          Data  : struct.pack(f">{n_values}f", *data.flat)
        """
        chunks: list[bytes] = []
        for p in params:
            data: np.ndarray = p["data"]
            n_values = data.size
            header = struct.pack(
                ">HHHHHf",
                p["p_id"],   # H: parameter ID
                p["nt"],     # H: number of time steps
                p["nlat"],   # H: number of latitude points
                p["nlon"],   # H: number of longitude points
                p["nd"],     # H: number of depth levels
                self.FILL_VALUE,  # f: fill value
            )
            flat = data.flatten().astype(np.float32).tolist()
            data_block = struct.pack(f">{n_values}f", *flat)
            chunks.append(header + data_block)

        bin_path.write_bytes(b"".join(chunks))
