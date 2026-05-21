"""
Shared Pydantic data contracts for inter-agent data exchange.

OWNERSHIP: Agent Epsilon (MLOps) exclusively maintains this file.
All other agents IMPORT from here — never redefine these models.

Design principles:
  - All geographic coordinates are [longitude, latitude] (GeoJSON convention).
  - All timestamps are UTC ISO-8601 strings.
  - GeoJSON geometries follow RFC 7946.
"""
from __future__ import annotations

import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Enumerations ─────────────────────────────────────────────────────────────

class AlertSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(StrEnum):
    TURBINE_CUTOUT = "TURBINE_CUTOUT"
    SOLAR_DROP = "SOLAR_DROP"
    NEGATIVE_PRICE = "NEGATIVE_PRICE"
    CVI_THRESHOLD = "CVI_THRESHOLD"


class MarketID(StrEnum):
    EPEX_DE = "EPEX_DE"
    EPEX_FR = "EPEX_FR"
    EPEX_GB = "EPEX_GB"
    NORD_POOL = "NORD_POOL"


# ── Sprint 1-2: Ingestion Contract ───────────────────────────────────────────

class IngestResult(BaseModel):
    """
    Produced by: Agent Alpha (ingestion module).
    Consumed by: Agent Beta (lagrangian), Agent Gamma (wesf).
    """

    run_id: str = Field(..., description="Unique run identifier (UUID4 string).")
    timestamp: datetime.datetime = Field(..., description="Ingestion completion timestamp (UTC).")
    bounding_box: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[lon_min, lat_min, lon_max, lat_max] in decimal degrees.",
    )
    atmospheric_vars: list[str] = Field(
        ...,
        description="Variable names present in dataset (e.g. ['u10', 'v10', 'msl']).",
    )
    ocean_vars: list[str] = Field(
        ...,
        description="Ocean variable names (e.g. ['uo', 'vo', 'zos', 'vsdx', 'vsdy']).",
    )
    dataset_path: str = Field(
        ...,
        description="Absolute path to the harmonised NetCDF4 file on the local filesystem.",
    )
    air_gap_mode: bool = Field(default=False)
    source_files: list[str] = Field(
        default_factory=list,
        description="Paths of the raw input files (GRIB2 / NetCDF) used.",
    )
    grid_resolution_deg: float = Field(
        default=0.25,
        description="Spatial resolution of the harmonised mesh (degrees).",
    )

    @field_validator("bounding_box")
    @classmethod
    def validate_bbox(cls, v: list[float]) -> list[float]:
        lon_min, lat_min, lon_max, lat_max = v
        if not (-180 <= lon_min < lon_max <= 180):
            raise ValueError("Longitudes must satisfy -180 ≤ lon_min < lon_max ≤ 180")
        if not (-90 <= lat_min < lat_max <= 90):
            raise ValueError("Latitudes must satisfy -90 ≤ lat_min < lat_max ≤ 90")
        return v


# ── Sprint 3: Lagrangian Drift Contract ──────────────────────────────────────

class ParticleTrack(BaseModel):
    """Single particle trajectory: list of [lon, lat] pairs over time."""

    particle_id: int
    positions: list[list[float]] = Field(
        ...,
        description="Ordered list of [lon, lat] positions (one per timestep).",
    )
    final_position: list[float] = Field(..., min_length=2, max_length=2)


class DriftCorridorResult(BaseModel):
    """
    Produced by: Agent Beta (lagrangian module).
    Consumed by: Agent Delta (nato), Agent Eta (api/visualization).
    """

    run_id: str
    ingest_run_id: str = Field(..., description="run_id of the IngestResult that forced this run.")
    origin: list[float] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="[lon, lat] of the object's last known GPS fix.",
    )
    leeway_pct: float = Field(..., ge=1.0, le=5.0)
    seed: int = Field(..., description="RNG seed used — enables exact reproduction.")
    n_particles: int = Field(..., ge=10)
    timestep_hours: float = Field(default=1.0)
    forecast_hours: int = Field(default=24, ge=1)

    particle_tracks: list[ParticleTrack] = Field(
        ...,
        description="One track per simulated particle.",
    )
    corridor_geojson: dict[str, Any] = Field(
        ...,
        description="Convex hull corridor as GeoJSON Polygon (RFC 7946).",
    )
    corridor_area_km2: float = Field(
        ...,
        ge=0.0,
        description="Area of the drift corridor polygon in km².",
    )
    centroid: list[float] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="[lon, lat] centroid of the final particle cloud.",
    )
    compute_time_seconds: float = Field(..., ge=0.0)


# ── Sprint 4: WESF Contracts ─────────────────────────────────────────────────

class AssetLocation(BaseModel):
    asset_id: str
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    asset_type: str = Field(default="WIND_TURBINE", description="WIND_TURBINE | SOLAR_PV | INVERTER")
    rated_mw: float | None = None


class RampAlertPayload(BaseModel):
    """
    Produced by: Agent Gamma (ramp_forecaster).
    Consumed by: Agent Delta (nato SIEM), Agent Eta (dashboard).
    """

    run_id: str
    ingest_run_id: str
    alert_type: AlertType
    asset: AssetLocation
    severity: AlertSeverity
    trigger_value: float = Field(
        ...,
        description="The physical value that crossed the threshold (m/s, oktas, etc.).",
    )
    threshold_value: float
    unit: str = Field(..., description="Physical unit of trigger_value (e.g. 'm/s', 'oktas').")
    time_window_start: datetime.datetime
    time_window_end: datetime.datetime
    estimated_mw_loss: float | None = Field(
        None,
        description="Estimated generation loss in MW.",
    )
    siem_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Pre-formatted SIEM payload for ingestion by security operations centre.",
    )

    @model_validator(mode="after")
    def validate_time_window(self) -> RampAlertPayload:
        if self.time_window_end <= self.time_window_start:
            raise ValueError("time_window_end must be after time_window_start")
        return self


class CVIAlert(BaseModel):
    """
    Produced by: Agent Gamma (cvi_engine).
    Consumed by: Agent Delta (nato SIEM), Agent Eta (dashboard).
    """

    run_id: str
    ingest_run_id: str
    asset: AssetLocation
    cvi_score: float = Field(..., ge=0.0, le=100.0, description="Cyber Vulnerability Index (0–100).")
    severity: AlertSeverity
    weather_severity_score: float = Field(..., ge=0.0, le=10.0)
    contributing_factors: list[str] = Field(
        default_factory=list,
        description="Human-readable list of factors that elevated the CVI.",
    )
    attack_surface_window_start: datetime.datetime
    attack_surface_window_end: datetime.datetime
    recommended_action: str
    siem_json: dict[str, Any] = Field(default_factory=dict)


class PriceForecast(BaseModel):
    """
    Produced by: Agent Gamma (price_model).
    Consumed by: Agent Eta (dashboard, VPP scheduling).
    """

    run_id: str
    market: MarketID
    forecast_generated_at: datetime.datetime
    forecast_intervals: list[datetime.datetime] = Field(
        ...,
        description="UTC timestamps for each forecast interval (hourly).",
    )
    forecast_prices_eur_mwh: list[float] = Field(
        ...,
        description="Forecast spot price for each interval (€/MWh).",
    )
    negative_pricing_flags: list[bool] = Field(
        ...,
        description="True where price is predicted to be negative.",
    )
    model_mae: float | None = Field(None, description="Model MAE on validation set (€/MWh).")
    model_name: str = Field(default="N-BEATS")

    @model_validator(mode="after")
    def validate_length_consistency(self) -> PriceForecast:
        n = len(self.forecast_intervals)
        if len(self.forecast_prices_eur_mwh) != n:
            raise ValueError("forecast_prices_eur_mwh length must match forecast_intervals")
        if len(self.negative_pricing_flags) != n:
            raise ValueError("negative_pricing_flags length must match forecast_intervals")
        return self


# ── Sprint 5: NATO Contracts ─────────────────────────────────────────────────

class MetgmExportResult(BaseModel):
    """
    Produced by: Agent Delta (metgm_compiler).
    Consumed by: Agent Eta (API download endpoint).
    """

    run_id: str
    xml_path: str = Field(..., description="Path to the STANAG 6015 METGM XML file.")
    binary_path: str = Field(..., description="Path to the STANAG 6015 METGM binary file.")
    parameter_count: int = Field(..., ge=1)
    grid_points: int
    time_steps: int
    schema_valid: bool = Field(..., description="True if XML validated against METGM XSD.")


class Nodef1ExportResult(BaseModel):
    """
    Produced by: Agent Delta (nodef1_exporter).
    Consumed by: Agent Eta (API download endpoint).
    """

    run_id: str
    binary_path: str = Field(..., description="Path to the STANAG 1317 NODEF-1 binary file.")
    record_count: int = Field(..., ge=1)
    checksum_sha256: str


class App6Feature(BaseModel):
    """Single APP-6 / MIL-STD-2525 symbology feature."""

    sidc: str = Field(
        ...,
        min_length=15,
        max_length=20,
        description="Symbol Identification Code (SIDC) per APP-6D.",
    )
    name: str
    geojson_geometry: dict[str, Any]
    properties: dict[str, Any] = Field(default_factory=dict)


class App6ExportResult(BaseModel):
    """
    Produced by: Agent Delta (app6_symbology).
    Consumed by: GeoServer / Leaflet.js client.
    """

    run_id: str
    geojson_path: str
    feature_count: int
    features: list[App6Feature]


# ── Sprint 6: Pipeline Summary ───────────────────────────────────────────────

class PipelineRunSummary(BaseModel):
    """
    Produced by: Agent Epsilon (core/pipeline.py).
    Top-level result returned by the REST API and written to data/output/.
    """

    run_id: str
    started_at: datetime.datetime
    completed_at: datetime.datetime
    duration_seconds: float
    success: bool
    error_message: str | None = None

    ingest: IngestResult | None = None
    drift: DriftCorridorResult | None = None
    ramp_alerts: list[RampAlertPayload] = Field(default_factory=list)
    cvi_alerts: list[CVIAlert] = Field(default_factory=list)
    price_forecast: PriceForecast | None = None
    metgm_export: MetgmExportResult | None = None
    nodef1_export: Nodef1ExportResult | None = None
    app6_export: App6ExportResult | None = None

    @property
    def under_three_minutes(self) -> bool:
        """NFR-2: Full pipeline must complete in under 180 seconds."""
        return self.duration_seconds < 180.0
