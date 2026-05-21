"""
METOC-Lagrangian Pipeline Orchestrator.
Runs a complete forecast cycle:
  1. Ingest (AIFS + CMEMS or local files)
  2. Grid harmonization
  3. Lagrangian drift (Monte Carlo)
  4. WESF analysis (ramps + CVI + pricing)
  5. NATO export (METGM + NODEF-1 + APP-6)
  6. Write PipelineRunSummary to data/output/

NFR-2: Full cycle must complete in < 180 seconds.
NFR-3: Fixed seed → deterministic outputs.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import structlog
import xarray as xr

from src.api.schemas import (
    AlertSeverity,
    AlertType,
    App6ExportResult,
    AssetLocation,
    CVIAlert,
    DriftCorridorResult,
    IngestResult,
    MarketID,
    MetgmExportResult,
    Nodef1ExportResult,
    ParticleTrack,
    PipelineRunSummary,
    PriceForecast,
    RampAlertPayload,
)
from src.core.config import get_settings
from src.core.logging_config import configure_logging

logger = structlog.get_logger(__name__)

# ── Synthetic fallback constants ──────────────────────────────────────────────
_SYNTHETIC_GRID_SIZE = 5       # 5×5 lat/lon grid
_SYNTHETIC_TIMESTEPS = 24      # 24 hourly steps
_DEFAULT_BBOX = [10.0, 30.0, 20.0, 40.0]
_DEFAULT_ORIGIN = (14.5, 36.8)


# ── Synthetic dataset builder ─────────────────────────────────────────────────

def _build_synthetic_atmo(
    rng: np.random.Generator,
    lat: np.ndarray,
    lon: np.ndarray,
    times: list[datetime.datetime],
) -> xr.Dataset:
    """Build a minimal synthetic atmospheric xr.Dataset (u10, v10, msl)."""
    nt, ny, nx = len(times), len(lat), len(lon)
    shape = (nt, ny, nx)
    time_vals = np.array([np.datetime64(t.replace(tzinfo=None)) for t in times])
    return xr.Dataset(
        {
            "u10": (["time", "lat", "lon"], rng.normal(5.0, 3.0, shape).astype("float32")),
            "v10": (["time", "lat", "lon"], rng.normal(2.0, 3.0, shape).astype("float32")),
            "msl": (["time", "lat", "lon"], rng.normal(101325.0, 500.0, shape).astype("float32")),
        },
        coords={"time": time_vals, "lat": lat, "lon": lon},
        attrs={"Conventions": "CF-1.8", "source": "synthetic"},
    )


def _build_synthetic_ocean(
    rng: np.random.Generator,
    lat: np.ndarray,
    lon: np.ndarray,
    times: list[datetime.datetime],
) -> xr.Dataset:
    """Build a minimal synthetic ocean xr.Dataset (uo, vo, zos, vsdx, vsdy)."""
    nt, ny, nx = len(times), len(lat), len(lon)
    shape = (nt, ny, nx)
    time_vals = np.array([np.datetime64(t.replace(tzinfo=None)) for t in times])
    return xr.Dataset(
        {
            "uo":   (["time", "lat", "lon"], rng.normal(0.1, 0.05, shape).astype("float32")),
            "vo":   (["time", "lat", "lon"], rng.normal(0.05, 0.05, shape).astype("float32")),
            "zos":  (["time", "lat", "lon"], rng.normal(0.0, 0.02, shape).astype("float32")),
            "vsdx": (["time", "lat", "lon"], rng.normal(0.02, 0.01, shape).astype("float32")),
            "vsdy": (["time", "lat", "lon"], rng.normal(0.01, 0.01, shape).astype("float32")),
        },
        coords={"time": time_vals, "lat": lat, "lon": lon},
        attrs={"Conventions": "CF-1.8", "source": "synthetic"},
    )


def _build_merged_synthetic(
    rng: np.random.Generator,
    lat: np.ndarray,
    lon: np.ndarray,
    times: list[datetime.datetime],
) -> xr.Dataset:
    """Build a single merged synthetic dataset with all canonical variables."""
    atmo = _build_synthetic_atmo(rng, lat, lon, times)
    ocean = _build_synthetic_ocean(rng, lat, lon, times)
    merged = xr.merge([atmo, ocean], compat="override")
    merged.attrs["grid_resolution_deg"] = float(lon[1] - lon[0]) if len(lon) > 1 else 0.25
    merged.attrs["source"] = "synthetic"
    merged.attrs["Conventions"] = "CF-1.8"
    return merged


def _extract_scalar_forcing(ds: xr.Dataset) -> dict[str, float]:
    """Extract scalar (spatiotemporal mean) forcing values from a dataset."""
    def _mean(var: str) -> float:
        if var in ds:
            return float(ds[var].values.mean())
        return 0.0

    return {
        "u_current": _mean("uo"),
        "v_current": _mean("vo"),
        "u_wind":    _mean("u10"),
        "v_wind":    _mean("v10"),
        "u_geo":     _mean("vsdx"),
        "v_geo":     _mean("vsdy"),
    }


def _default_assets() -> list[AssetLocation]:
    """Return a minimal default set of test assets."""
    return [
        AssetLocation(asset_id="WTG-001", lon=14.2, lat=36.5, asset_type="WIND_TURBINE", rated_mw=5.0),
        AssetLocation(asset_id="WTG-002", lon=15.0, lat=37.0, asset_type="WIND_TURBINE", rated_mw=5.0),
        AssetLocation(asset_id="INV-001", lon=14.8, lat=36.8, asset_type="INVERTER", rated_mw=10.0),
    ]


def _synthetic_price_forecast(run_id: str, seed: int) -> PriceForecast:
    """Generate a synthetic 24-h price forecast for testing."""
    rng = np.random.default_rng(seed)
    now = datetime.datetime.now(tz=datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
    intervals = [now + datetime.timedelta(hours=i) for i in range(24)]
    prices = rng.normal(50.0, 15.0, 24).tolist()
    neg_flags = [p < 0 for p in prices]
    return PriceForecast(
        run_id=run_id,
        market=MarketID.EPEX_DE,
        forecast_generated_at=now,
        forecast_intervals=intervals,
        forecast_prices_eur_mwh=prices,
        negative_pricing_flags=neg_flags,
        model_mae=4.5,
        model_name="N-BEATS-synthetic",
    )


# ── Main pipeline function ────────────────────────────────────────────────────

async def run_pipeline(
    origin: tuple[float, float],
    bounding_box: list[float],
    leeway_pct: float = 2.5,
    seed: int = 42,
    assets: list[AssetLocation] | None = None,
) -> PipelineRunSummary:
    """
    Run the complete METOC-Lagrangian forecast pipeline.

    Parameters
    ----------
    origin:
        (lon, lat) of the object's last known GPS fix.
    bounding_box:
        [lon_min, lat_min, lon_max, lat_max] defining the area of interest.
    leeway_pct:
        Wind leeway percentage (1.0–5.0 %).
    seed:
        RNG seed — guarantees deterministic outputs (NFR-3).
    assets:
        Renewable energy assets to monitor.  Defaults to three synthetic assets.

    Returns
    -------
    PipelineRunSummary
        Top-level result written to data/output/{run_id}_summary.json.
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    run_id = str(uuid.uuid4())
    started_at = datetime.datetime.now(tz=datetime.timezone.utc)
    t_start = time.perf_counter()

    log = logger.bind(run_id=run_id, seed=seed)
    log.info("pipeline.start", origin=origin, bbox=bounding_box, leeway_pct=leeway_pct)

    # Resolved state defaults
    ingest_result: IngestResult | None = None
    drift_result: DriftCorridorResult | None = None
    ramp_alerts: list[RampAlertPayload] = []
    cvi_alerts: list[CVIAlert] = []
    price_forecast: PriceForecast | None = None
    metgm_export: MetgmExportResult | None = None
    nodef1_export: Nodef1ExportResult | None = None
    app6_export: App6ExportResult | None = None
    error_message: str | None = None

    if assets is None:
        assets = _default_assets()

    rng = np.random.default_rng(seed)

    # Build grid coordinates from bounding box
    lon_min, lat_min, lon_max, lat_max = bounding_box
    res = settings.target_grid_resolution_deg
    lat_arr = np.arange(lat_min, lat_max + 1e-9, res)
    lon_arr = np.arange(lon_min, lon_max + 1e-9, res)
    now_utc = datetime.datetime.now(tz=datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
    times = [now_utc + datetime.timedelta(hours=i) for i in range(_SYNTHETIC_TIMESTEPS)]

    try:
        # ── Step 1: Ingestion ─────────────────────────────────────────────────
        log.info("pipeline.step", step=1, name="ingestion")
        dataset_path: str | None = None
        source_files: list[str] = []

        if settings.air_gap_mode:
            # Scan local data/input/ for NetCDF files
            input_files = sorted(settings.data_input_dir.glob("*.nc"))
            if input_files:
                dataset_path = str(input_files[0])
                source_files = [str(p) for p in input_files]
                log.info("pipeline.air_gap_ingest", n_files=len(input_files))
            else:
                log.info("pipeline.air_gap_no_files", msg="will use synthetic data")
        else:
            # Try live ingestion clients with graceful fallback
            try:
                from src.ingestion.aifs_client import AIFSClient  # type: ignore[import]
                from src.ingestion.cmems_client import CMEMSClient  # type: ignore[import]
                log.debug("pipeline.live_clients_found")
            except ImportError as exc:
                log.warning("pipeline.live_clients_missing", error=str(exc))

        # ── Step 2: Grid harmonization ────────────────────────────────────────
        log.info("pipeline.step", step=2, name="grid_harmonization")
        merged_ds: xr.Dataset | None = None

        if dataset_path and Path(dataset_path).exists():
            try:
                from src.ingestion.grid_harmonizer import GridHarmonizer
                harmonizer = GridHarmonizer()
                # Attempt harmonization only if both atmo+ocean paths exist
                # (dataset_path may already be merged — load directly)
                merged_ds = xr.open_dataset(dataset_path, engine="netcdf4")
                log.info("pipeline.harmonized_loaded", path=dataset_path)
            except Exception as exc:
                log.warning("pipeline.harmonize_failed", error=str(exc), fallback="synthetic")
                merged_ds = None

        if merged_ds is None:
            # Generate synthetic merged dataset for testability
            merged_ds = _build_merged_synthetic(rng, lat_arr, lon_arr, times)
            # Save it so downstream steps (MetgmCompiler) can read it by path
            settings.data_output_dir.mkdir(parents=True, exist_ok=True)
            synthetic_path = settings.data_output_dir / f"{run_id}_harmonized.nc"
            merged_ds.to_netcdf(str(synthetic_path), format="NETCDF4")
            dataset_path = str(synthetic_path)
            log.info("pipeline.synthetic_dataset_saved", path=dataset_path)

        ingest_result = IngestResult(
            run_id=run_id,
            timestamp=now_utc,
            bounding_box=bounding_box,
            atmospheric_vars=["u10", "v10", "msl"],
            ocean_vars=["uo", "vo", "zos", "vsdx", "vsdy"],
            dataset_path=dataset_path or "",
            air_gap_mode=settings.air_gap_mode,
            source_files=source_files,
            grid_resolution_deg=res,
        )
        log.info("pipeline.ingest_done", dataset_path=dataset_path)

        # ── Step 3: Lagrangian drift (Monte Carlo) ────────────────────────────
        log.info("pipeline.step", step=3, name="monte_carlo_drift")
        mc_start = time.perf_counter()

        from src.lagrangian.monte_carlo import MonteCarloEnsemble

        forcing = _extract_scalar_forcing(merged_ds)
        mc = MonteCarloEnsemble(
            n_particles=settings.monte_carlo_particles,
            seed=seed,
        )
        tracks = mc.run(
            origin_lon=origin[0],
            origin_lat=origin[1],
            u_current=forcing["u_current"],
            v_current=forcing["v_current"],
            u_wind=forcing["u_wind"],
            v_wind=forcing["v_wind"],
            u_geo=forcing["u_geo"],
            v_geo=forcing["v_geo"],
            leeway_pct=leeway_pct,
            dt_hours=1.0,
            n_steps=settings.forecast_hours,
        )
        mc_elapsed = time.perf_counter() - mc_start
        log.info("pipeline.monte_carlo_done", n_particles=len(tracks), elapsed_s=round(mc_elapsed, 2))

        # ── Step 4: Build drift corridor ──────────────────────────────────────
        log.info("pipeline.step", step=4, name="drift_corridor")
        from src.lagrangian.drift_corridor import DriftCorridor

        corridor = DriftCorridor()
        drift_result = corridor.build(
            tracks=tracks,
            forecast_hours=settings.forecast_hours,
            run_id=run_id,
            ingest_run_id=run_id,
            origin=list(origin),
            leeway_pct=leeway_pct,
            seed=seed,
            timestep_hours=1.0,
            compute_time_seconds=mc_elapsed,
        )
        log.info(
            "pipeline.corridor_done",
            area_km2=round(drift_result.corridor_area_km2, 2),
            centroid=drift_result.centroid,
        )

        # ── Step 5a: Ramp forecasting ─────────────────────────────────────────
        log.info("pipeline.step", step=5, name="ramp_forecasting")
        from src.wesf.ramp_forecaster import RampForecaster

        u10_data = merged_ds["u10"].values if "u10" in merged_ds else np.zeros((1, len(lat_arr), len(lon_arr)))
        v10_data = merged_ds["v10"].values if "v10" in merged_ds else np.zeros((1, len(lat_arr), len(lon_arr)))
        # Synthetic cloud fraction (oktas) — not in canonical dataset; generate it
        cloud_frac = rng.uniform(0.0, 8.0, u10_data.shape).astype("float32")

        # Ensure 3-D shape
        if u10_data.ndim == 2:
            u10_data = u10_data[np.newaxis]
            v10_data = v10_data[np.newaxis]
            cloud_frac = cloud_frac[np.newaxis]

        # Slice to available time steps
        n_t = min(u10_data.shape[0], len(times))
        ramp_forecaster = RampForecaster(
            assets=assets,
            run_id=run_id,
            ingest_run_id=run_id,
        )
        ramp_alerts = ramp_forecaster.forecast(
            u10=u10_data[:n_t],
            v10=v10_data[:n_t],
            cloud_fraction=cloud_frac[:n_t],
            lat=lat_arr,
            lon=lon_arr,
            timestamps=times[:n_t],
        )
        log.info("pipeline.ramp_done", n_alerts=len(ramp_alerts))

        # ── Step 5b: CVI scoring ──────────────────────────────────────────────
        log.info("pipeline.step", step=5, name="cvi_scoring")
        from src.wesf.cvi_engine import CVIEngine

        cvi_engine = CVIEngine(run_id=run_id, ingest_run_id=run_id)
        wind_speeds = [float(np.sqrt(forcing["u_wind"] ** 2 + forcing["v_wind"] ** 2))] * len(assets)
        anomaly_scores = [min(10.0, ws / 3.0) for ws in wind_speeds]
        cvi_alerts = cvi_engine.batch_score(
            assets=assets,
            weather_wind_ms_list=wind_speeds,
            weather_anomaly_scores=anomaly_scores,
            grid_stress_mw_list=[50.0] * len(assets),
            monitoring_quality_list=[0.8] * len(assets),
            event_time=now_utc,
        )
        log.info("pipeline.cvi_done", n_alerts=len(cvi_alerts))

        # ── Step 5c: Price forecast ───────────────────────────────────────────
        price_forecast = _synthetic_price_forecast(run_id, seed)
        log.info("pipeline.price_forecast_done", market=price_forecast.market.value)

        # ── Step 6a: METGM export ─────────────────────────────────────────────
        log.info("pipeline.step", step=6, name="metgm_export")
        from src.nato.metgm_compiler import MetgmCompiler

        metgm_compiler = MetgmCompiler(output_dir=settings.data_output_dir)
        metgm_export = metgm_compiler.compile(dataset_path=dataset_path or "", run_id=run_id)
        log.info("pipeline.metgm_done", schema_valid=metgm_export.schema_valid)

        # ── Step 6b: NODEF-1 export ───────────────────────────────────────────
        log.info("pipeline.step", step=6, name="nodef1_export")
        from src.nato.nodef1_exporter import Nodef1Exporter

        nodef1_exporter = Nodef1Exporter()
        nodef1_export = nodef1_exporter.export(
            dataset_path=dataset_path or "",
            run_id=run_id,
            output_dir=settings.data_output_dir,
        )
        log.info("pipeline.nodef1_done", record_count=nodef1_export.record_count)

        # ── Step 6c: APP-6 export ─────────────────────────────────────────────
        log.info("pipeline.step", step=6, name="app6_export")
        from src.nato.app6_symbology import App6Symbology

        app6_exporter = App6Symbology()
        app6_export = app6_exporter.export(
            drift=drift_result,
            ramp_alerts=ramp_alerts,
            cvi_alerts=cvi_alerts,
            run_id=run_id,
            output_dir=settings.data_output_dir,
        )
        log.info("pipeline.app6_done", feature_count=app6_export.feature_count)

        success = True

    except Exception as exc:
        log.exception("pipeline.error", error=str(exc))
        error_message = f"{type(exc).__name__}: {exc}"
        success = False

    # ── Step 7: Write PipelineRunSummary ──────────────────────────────────────
    completed_at = datetime.datetime.now(tz=datetime.timezone.utc)
    duration_seconds = time.perf_counter() - t_start

    summary = PipelineRunSummary(
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=round(duration_seconds, 3),
        success=success,
        error_message=error_message,
        ingest=ingest_result,
        drift=drift_result,
        ramp_alerts=ramp_alerts,
        cvi_alerts=cvi_alerts,
        price_forecast=price_forecast,
        metgm_export=metgm_export,
        nodef1_export=nodef1_export,
        app6_export=app6_export,
    )

    # Write summary JSON
    settings.data_output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = settings.data_output_dir / f"{run_id}_summary.json"
    summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

    log.info(
        "pipeline.complete",
        duration_s=round(duration_seconds, 2),
        success=success,
        nfr2_ok=summary.under_three_minutes,
        summary_path=str(summary_path),
    )
    return summary


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main() -> None:
    """CLI entrypoint for the METOC-Lagrangian pipeline."""
    parser = argparse.ArgumentParser(
        prog="metoc-pipeline",
        description="METOC-Lagrangian Pipeline Orchestrator",
    )
    parser.add_argument(
        "--origin",
        default="14.5,36.8",
        help='Origin point as "lon,lat" (e.g. "14.5,36.8")',
    )
    parser.add_argument(
        "--leeway",
        type=float,
        default=2.5,
        help="Wind leeway percentage (1.0–5.0)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Monte Carlo RNG seed",
    )
    parser.add_argument(
        "--bbox",
        default="10.0,30.0,20.0,40.0",
        help='Bounding box as "lon_min,lat_min,lon_max,lat_max"',
    )
    args = parser.parse_args()

    # Parse origin
    try:
        lon_s, lat_s = args.origin.split(",")
        origin = (float(lon_s.strip()), float(lat_s.strip()))
    except ValueError as exc:
        parser.error(f"Invalid --origin format: {exc}")

    # Parse bbox
    try:
        bbox_parts = [float(x.strip()) for x in args.bbox.split(",")]
        if len(bbox_parts) != 4:
            raise ValueError("Expected 4 values")
        bounding_box = bbox_parts
    except ValueError as exc:
        parser.error(f"Invalid --bbox format: {exc}")

    summary = asyncio.run(
        run_pipeline(
            origin=origin,
            bounding_box=bounding_box,
            leeway_pct=args.leeway,
            seed=args.seed,
        )
    )
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
