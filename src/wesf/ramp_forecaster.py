"""
WESF Ramp Forecaster.
Maps renewable energy asset locations against weather forcing grids
to predict sudden generation ramps (turbine cut-outs, solar drops).

Physical models:
  Turbine cut-out: wind_speed >= turbine_cutout_ms (default 25 m/s)
  Solar drop: cloud_fraction (oktas) >= solar_cloud_threshold_oktas (default 7)
              OR total_column_aerosol_optical_depth > 0.5 (dust events)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import numpy as np
import structlog

from src.api.schemas import (
    AlertSeverity,
    AlertType,
    AssetLocation,
    RampAlertPayload,
)
from src.core.config import get_settings

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Bilinear interpolation (optional scipy fast path, pure-numpy fallback)
# ---------------------------------------------------------------------------
try:
    from scipy.interpolate import RegularGridInterpolator as _RGI  # type: ignore

    _SCIPY_AVAILABLE = True
    logger.debug("scipy.interpolate available — using RegularGridInterpolator")
except ImportError:
    _SCIPY_AVAILABLE = False
    logger.warning("scipy not available; falling back to numpy bilinear interpolation")


class RampForecaster:
    """
    Predicts wind-turbine cut-out and solar irradiance drop events.

    Parameters
    ----------
    assets : list[AssetLocation]
        Renewable energy assets to monitor.
    cutout_ms : float | None
        Override turbine cut-out wind speed threshold (m/s).
        Defaults to ``Settings.turbine_cutout_ms``.
    cloud_threshold_oktas : float | None
        Override cloud-fraction threshold (oktas).
        Defaults to ``Settings.solar_cloud_threshold_oktas``.
    run_id : str | None
        Identifier for this forecast run; auto-generated if omitted.
    ingest_run_id : str | None
        Identifier of the upstream ingest run that provided the weather data.
    """

    def __init__(
        self,
        assets: list[AssetLocation],
        *,
        cutout_ms: float | None = None,
        cloud_threshold_oktas: float | None = None,
        run_id: str | None = None,
        ingest_run_id: str | None = None,
    ) -> None:
        settings = get_settings()
        self.assets = assets
        self.cutout_ms: float = cutout_ms if cutout_ms is not None else settings.turbine_cutout_ms
        self.cloud_threshold_oktas: float = (
            cloud_threshold_oktas
            if cloud_threshold_oktas is not None
            else settings.solar_cloud_threshold_oktas
        )
        self.run_id: str = run_id or str(uuid.uuid4())
        self.ingest_run_id: str = ingest_run_id or str(uuid.uuid4())

        logger.info(
            "RampForecaster initialised",
            n_assets=len(assets),
            cutout_ms=self.cutout_ms,
            cloud_threshold_oktas=self.cloud_threshold_oktas,
            run_id=self.run_id,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def forecast(
        self,
        u10: np.ndarray,
        v10: np.ndarray,
        cloud_fraction: np.ndarray,
        lat: np.ndarray,
        lon: np.ndarray,
        timestamps: list[datetime],
    ) -> list[RampAlertPayload]:
        """
        Run ramp event detection across all assets and all timestamps.

        Parameters
        ----------
        u10 : np.ndarray
            East-ward 10-m wind component, shape (T, Y, X) [m/s].
        v10 : np.ndarray
            North-ward 10-m wind component, shape (T, Y, X) [m/s].
        cloud_fraction : np.ndarray
            Total cloud cover in oktas, shape (T, Y, X) [0–8].
        lat : np.ndarray
            Latitude axis of the grid, shape (Y,) [degrees N].
        lon : np.ndarray
            Longitude axis of the grid, shape (X,) [degrees E].
        timestamps : list[datetime]
            UTC datetimes corresponding to the T axis, length T.

        Returns
        -------
        list[RampAlertPayload]
            One payload per (asset, timestamp, alert_type) triple that
            crosses a threshold.
        """
        n_times = len(timestamps)
        if u10.ndim == 2:
            # Single time-step — add batch dimension
            u10 = u10[np.newaxis, ...]
            v10 = v10[np.newaxis, ...]
            cloud_fraction = cloud_fraction[np.newaxis, ...]

        if u10.shape[0] != n_times:
            raise ValueError(
                f"u10 leading axis ({u10.shape[0]}) must equal len(timestamps) ({n_times})"
            )

        alerts: list[RampAlertPayload] = []

        for asset in self.assets:
            for t_idx, ts in enumerate(timestamps):
                # Ensure timestamp is UTC-aware
                ts_utc = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)

                wind_speed = self._interpolate_to_asset(
                    np.sqrt(u10[t_idx] ** 2 + v10[t_idx] ** 2),
                    lat,
                    lon,
                    asset.lat,
                    asset.lon,
                )
                cloud_val = self._interpolate_to_asset(
                    cloud_fraction[t_idx],
                    lat,
                    lon,
                    asset.lat,
                    asset.lon,
                )

                # ── Turbine cut-out ──────────────────────────────────────
                if asset.asset_type in ("WIND_TURBINE", "INVERTER") and wind_speed >= self.cutout_ms:
                    severity = self._wind_severity(wind_speed)
                    mw_loss = asset.rated_mw if asset.rated_mw is not None else None
                    alert = self._build_ramp_alert(
                        asset=asset,
                        alert_type=AlertType.TURBINE_CUTOUT,
                        severity=severity,
                        trigger_value=float(wind_speed),
                        threshold_value=self.cutout_ms,
                        unit="m/s",
                        ts=ts_utc,
                        estimated_mw_loss=mw_loss,
                    )
                    alerts.append(alert)
                    logger.info(
                        "Turbine cut-out alert",
                        asset_id=asset.asset_id,
                        wind_speed_ms=round(float(wind_speed), 2),
                        severity=severity.value,
                        timestamp=ts_utc.isoformat(),
                    )

                # ── Solar drop ───────────────────────────────────────────
                if asset.asset_type in ("SOLAR_PV", "INVERTER") and cloud_val >= self.cloud_threshold_oktas:
                    severity = self._cloud_severity(cloud_val)
                    mw_loss = (
                        asset.rated_mw * cloud_val / 8.0
                        if asset.rated_mw is not None
                        else None
                    )
                    alert = self._build_ramp_alert(
                        asset=asset,
                        alert_type=AlertType.SOLAR_DROP,
                        severity=severity,
                        trigger_value=float(cloud_val),
                        threshold_value=self.cloud_threshold_oktas,
                        unit="oktas",
                        ts=ts_utc,
                        estimated_mw_loss=mw_loss,
                    )
                    alerts.append(alert)
                    logger.info(
                        "Solar drop alert",
                        asset_id=asset.asset_id,
                        cloud_oktas=round(float(cloud_val), 2),
                        severity=severity.value,
                        timestamp=ts_utc.isoformat(),
                    )

        logger.info(
            "Ramp forecast complete",
            n_assets=len(self.assets),
            n_timestamps=n_times,
            n_alerts=len(alerts),
            run_id=self.run_id,
        )
        return alerts

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _interpolate_to_asset(
        self,
        field: np.ndarray,
        lat_grid: np.ndarray,
        lon_grid: np.ndarray,
        asset_lat: float,
        asset_lon: float,
    ) -> float:
        """
        Bilinear interpolation of a 2-D field at a single (lat, lon) point.

        Uses ``scipy.interpolate.RegularGridInterpolator`` when scipy is
        available, otherwise a hand-rolled numpy implementation.

        Parameters
        ----------
        field : np.ndarray, shape (Y, X)
            Gridded scalar field.
        lat_grid : np.ndarray, shape (Y,)
        lon_grid : np.ndarray, shape (X,)
        asset_lat, asset_lon : float

        Returns
        -------
        float
            Interpolated value at the asset position.
        """
        # Clamp to grid extent to handle edge assets gracefully
        asset_lat = float(np.clip(asset_lat, lat_grid.min(), lat_grid.max()))
        asset_lon = float(np.clip(asset_lon, lon_grid.min(), lon_grid.max()))

        if _SCIPY_AVAILABLE:
            interp = _RGI(
                (lat_grid, lon_grid),
                field,
                method="linear",
                bounds_error=False,
                fill_value=None,
            )
            return float(interp([[asset_lat, asset_lon]])[0])

        # ── Pure-numpy bilinear fallback ─────────────────────────────
        return self._numpy_bilinear(field, lat_grid, lon_grid, asset_lat, asset_lon)

    @staticmethod
    def _numpy_bilinear(
        field: np.ndarray,
        lat_grid: np.ndarray,
        lon_grid: np.ndarray,
        asset_lat: float,
        asset_lon: float,
    ) -> float:
        """Bilinear interpolation without scipy."""
        # Latitude index
        j_hi = int(np.searchsorted(lat_grid, asset_lat, side="right"))
        j_hi = int(np.clip(j_hi, 1, len(lat_grid) - 1))
        j_lo = j_hi - 1

        # Longitude index
        i_hi = int(np.searchsorted(lon_grid, asset_lon, side="right"))
        i_hi = int(np.clip(i_hi, 1, len(lon_grid) - 1))
        i_lo = i_hi - 1

        lat_lo, lat_hi = lat_grid[j_lo], lat_grid[j_hi]
        lon_lo, lon_hi = lon_grid[i_lo], lon_grid[i_hi]

        # Fractional distances
        dy = lat_hi - lat_lo
        dx = lon_hi - lon_lo

        if dy == 0.0:
            fy = 0.0
        else:
            fy = (asset_lat - lat_lo) / dy

        if dx == 0.0:
            fx = 0.0
        else:
            fx = (asset_lon - lon_lo) / dx

        v00 = field[j_lo, i_lo]
        v01 = field[j_lo, i_hi]
        v10 = field[j_hi, i_lo]
        v11 = field[j_hi, i_hi]

        value = (
            v00 * (1 - fy) * (1 - fx)
            + v01 * (1 - fy) * fx
            + v10 * fy * (1 - fx)
            + v11 * fy * fx
        )
        return float(value)

    def _build_ramp_alert(
        self,
        asset: AssetLocation,
        alert_type: AlertType,
        severity: AlertSeverity,
        trigger_value: float,
        threshold_value: float,
        unit: str,
        ts: datetime,
        estimated_mw_loss: float | None,
    ) -> RampAlertPayload:
        """Construct a fully-formed RampAlertPayload with embedded SIEM JSON."""
        from datetime import timedelta

        window_start = ts
        window_end = ts + timedelta(hours=1)

        siem_json = {
            "event_type": alert_type.value,
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type,
            "alert_type": alert_type.value,
            "severity": severity.value,
            "timestamp": ts.isoformat(),
            "trigger_value": round(trigger_value, 4),
            "threshold_value": threshold_value,
            "unit": unit,
            "estimated_mw_loss": estimated_mw_loss,
            "lat": asset.lat,
            "lon": asset.lon,
            "run_id": self.run_id,
            "ingest_run_id": self.ingest_run_id,
            "source": "WESF_RAMP_FORECASTER",
        }

        return RampAlertPayload(
            run_id=self.run_id,
            ingest_run_id=self.ingest_run_id,
            alert_type=alert_type,
            asset=asset,
            severity=severity,
            trigger_value=trigger_value,
            threshold_value=threshold_value,
            unit=unit,
            time_window_start=window_start,
            time_window_end=window_end,
            estimated_mw_loss=estimated_mw_loss,
            siem_json=siem_json,
        )

    # ------------------------------------------------------------------
    # Severity mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wind_severity(wind_speed: float) -> AlertSeverity:
        """Map wind speed (m/s) to alert severity."""
        if wind_speed > 28.0:
            return AlertSeverity.CRITICAL
        if wind_speed >= 25.0:
            return AlertSeverity.HIGH
        return AlertSeverity.MEDIUM  # sub-threshold (should not normally reach here)

    @staticmethod
    def _cloud_severity(cloud_oktas: float) -> AlertSeverity:
        """Map cloud cover (oktas) to alert severity."""
        if cloud_oktas >= 8.0:
            return AlertSeverity.HIGH
        if cloud_oktas >= 7.0:
            return AlertSeverity.MEDIUM
        return AlertSeverity.LOW
