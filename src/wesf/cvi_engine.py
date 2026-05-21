"""
Cyber Vulnerability Index (CVI) Engine.
Scores inverter and grid-edge asset cyber risk on a 0–100 scale.

The CVI framework is grounded in operational reality:
adversaries exploit extreme weather anomalies because:
  1. Grid stress is maximum (operators focused on physical threat)
  2. Monitoring visibility is degraded (sensor noise, communication loss)
  3. Remote access for firmware updates is legitimately elevated
  4. Ride-through threshold modifications go undetected under noise

CVI = w1*Weather + w2*Exposure + w3*Stress + w4*Visibility
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from src.api.schemas import (
    AlertSeverity,
    AssetLocation,
    CVIAlert,
)
from src.core.config import get_settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# CVI weights (must sum to 1.0)
# ---------------------------------------------------------------------------
_W_WEATHER: float = 0.35
_W_EXPOSURE: float = 0.25
_W_STRESS: float = 0.25
_W_VISIBILITY: float = 0.15

# Stress normalisation denominator (MW) — full-scale grid deviation
_STRESS_FULL_SCALE_MW: float = 500.0

# Attack-surface window duration for HIGH / CRITICAL events
_ATTACK_WINDOW_HOURS: int = 4

# Asset types treated as highest exposure
_HIGH_EXPOSURE_TYPES: frozenset[str] = frozenset({"INVERTER"})


class CVIEngine:
    """
    Cyber Vulnerability Index scoring engine.

    Scores are deterministic given the same inputs and settings.
    No stochastic elements; safe for parallel or batch use.

    Parameters
    ----------
    run_id : str | None
        Identifier for this engine run; auto-generated if omitted.
    ingest_run_id : str | None
        Upstream ingest run identifier.
    """

    def __init__(
        self,
        *,
        run_id: str | None = None,
        ingest_run_id: str | None = None,
    ) -> None:
        self.settings = get_settings()
        self.run_id: str = run_id or str(uuid.uuid4())
        self.ingest_run_id: str = ingest_run_id or str(uuid.uuid4())

        logger.info(
            "CVIEngine initialised",
            run_id=self.run_id,
            cvi_alert_threshold=self.settings.cvi_alert_threshold,
        )

    # ------------------------------------------------------------------
    # Public API — single asset
    # ------------------------------------------------------------------

    def score(
        self,
        asset: AssetLocation,
        weather_wind_ms: float,
        weather_anomaly_score: float,
        grid_stress_mw: float,
        monitoring_quality: float,
        *,
        event_time: datetime | None = None,
    ) -> CVIAlert:
        """
        Compute the Cyber Vulnerability Index for a single asset.

        Parameters
        ----------
        asset : AssetLocation
        weather_wind_ms : float
            Current wind speed at asset location [m/s].
        weather_anomaly_score : float
            Normalised weather anomaly severity, 0 (normal) – 10 (extreme).
        grid_stress_mw : float
            Absolute grid load deviation from baseline [MW].  Clamped to ≥ 0.
        monitoring_quality : float
            Current monitoring fidelity, 0.0 (blind) – 1.0 (full visibility).
        event_time : datetime | None
            Reference time for the attack-surface window; defaults to UTC now.

        Returns
        -------
        CVIAlert
        """
        # ── Input sanitisation ───────────────────────────────────────────────
        weather_anomaly_score = float(max(0.0, min(10.0, weather_anomaly_score)))
        grid_stress_mw = float(max(0.0, grid_stress_mw))
        monitoring_quality = float(max(0.0, min(1.0, monitoring_quality)))
        weather_wind_ms = float(max(0.0, weather_wind_ms))

        # ── Sub-score computation ────────────────────────────────────────────
        weather_score = 100.0 * (weather_anomaly_score / 10.0)
        exposure_score = 100.0 if asset.asset_type in _HIGH_EXPOSURE_TYPES else 70.0
        stress_score = min(100.0, (grid_stress_mw / _STRESS_FULL_SCALE_MW) * 100.0)
        visibility_score = 100.0 * (1.0 - monitoring_quality)

        # ── Weighted CVI ─────────────────────────────────────────────────────
        cvi = (
            _W_WEATHER * weather_score
            + _W_EXPOSURE * exposure_score
            + _W_STRESS * stress_score
            + _W_VISIBILITY * visibility_score
        )
        cvi = float(max(0.0, min(100.0, cvi)))

        # ── Severity mapping ─────────────────────────────────────────────────
        severity = self._cvi_severity(cvi)

        # ── Contributing factors ─────────────────────────────────────────────
        factors = self._build_contributing_factors(
            weather_score=weather_score,
            weather_anomaly_score=weather_anomaly_score,
            weather_wind_ms=weather_wind_ms,
            exposure_score=exposure_score,
            asset=asset,
            stress_score=stress_score,
            grid_stress_mw=grid_stress_mw,
            visibility_score=visibility_score,
            monitoring_quality=monitoring_quality,
        )

        # ── Attack-surface window ────────────────────────────────────────────
        now = event_time or datetime.now(tz=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        window_start = now
        window_end = now + timedelta(hours=_ATTACK_WINDOW_HOURS)

        # ── Recommended action ───────────────────────────────────────────────
        recommended_action = self._recommended_action(severity, asset)

        # ── SIEM JSON ────────────────────────────────────────────────────────
        siem_json: dict[str, Any] = {
            "event_type": "CVI_ALERT",
            "severity": severity.value,
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type,
            "cvi_score": round(cvi, 2),
            "weather_anomaly_score": weather_anomaly_score,
            "weather_wind_ms": weather_wind_ms,
            "grid_stress_mw": grid_stress_mw,
            "monitoring_quality": monitoring_quality,
            "sub_scores": {
                "weather": round(weather_score, 2),
                "exposure": round(exposure_score, 2),
                "stress": round(stress_score, 2),
                "visibility": round(visibility_score, 2),
            },
            "attack_surface_window_start": window_start.isoformat(),
            "attack_surface_window_end": window_end.isoformat(),
            "recommended_action": recommended_action,
            "contributing_factors": factors,
            "run_id": self.run_id,
            "ingest_run_id": self.ingest_run_id,
            "source": "METOC_WESF_CVI",
        }

        alert = CVIAlert(
            run_id=self.run_id,
            ingest_run_id=self.ingest_run_id,
            asset=asset,
            cvi_score=cvi,
            severity=severity,
            weather_severity_score=weather_anomaly_score,
            contributing_factors=factors,
            attack_surface_window_start=window_start,
            attack_surface_window_end=window_end,
            recommended_action=recommended_action,
            siem_json=siem_json,
        )

        logger.info(
            "CVI scored",
            asset_id=asset.asset_id,
            cvi_score=round(cvi, 2),
            severity=severity.value,
            run_id=self.run_id,
        )
        return alert

    # ------------------------------------------------------------------
    # Public API — batch
    # ------------------------------------------------------------------

    def batch_score(
        self,
        assets: list[AssetLocation],
        weather_wind_ms_list: list[float],
        weather_anomaly_scores: list[float],
        grid_stress_mw_list: list[float],
        monitoring_quality_list: list[float],
        *,
        event_time: datetime | None = None,
    ) -> list[CVIAlert]:
        """
        Score a list of assets in sequence.

        All list arguments must have the same length as ``assets``.

        Parameters
        ----------
        assets : list[AssetLocation]
        weather_wind_ms_list : list[float]
        weather_anomaly_scores : list[float]
        grid_stress_mw_list : list[float]
        monitoring_quality_list : list[float]
        event_time : datetime | None

        Returns
        -------
        list[CVIAlert]
        """
        n = len(assets)
        if not (
            len(weather_wind_ms_list) == n
            and len(weather_anomaly_scores) == n
            and len(grid_stress_mw_list) == n
            and len(monitoring_quality_list) == n
        ):
            raise ValueError(
                "All input lists must have the same length as `assets`."
            )

        results: list[CVIAlert] = []
        for i, asset in enumerate(assets):
            alert = self.score(
                asset=asset,
                weather_wind_ms=weather_wind_ms_list[i],
                weather_anomaly_score=weather_anomaly_scores[i],
                grid_stress_mw=grid_stress_mw_list[i],
                monitoring_quality=monitoring_quality_list[i],
                event_time=event_time,
            )
            results.append(alert)

        logger.info(
            "CVI batch scored",
            n_assets=n,
            n_critical=sum(1 for a in results if a.severity == AlertSeverity.CRITICAL),
            run_id=self.run_id,
        )
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cvi_severity(cvi: float) -> AlertSeverity:
        """Map CVI score to alert severity."""
        if cvi > 75.0:
            return AlertSeverity.CRITICAL
        if cvi > 55.0:
            return AlertSeverity.HIGH
        if cvi >= 35.0:
            return AlertSeverity.MEDIUM
        return AlertSeverity.LOW

    @staticmethod
    def _build_contributing_factors(
        *,
        weather_score: float,
        weather_anomaly_score: float,
        weather_wind_ms: float,
        exposure_score: float,
        asset: AssetLocation,
        stress_score: float,
        grid_stress_mw: float,
        visibility_score: float,
        monitoring_quality: float,
    ) -> list[str]:
        """Build human-readable list of the top CVI drivers (in score order)."""
        factors: list[tuple[float, str]] = []

        # Weather
        weighted_weather = _W_WEATHER * weather_score
        if weather_anomaly_score >= 8.0:
            factors.append((weighted_weather, f"Extreme weather event (anomaly score {weather_anomaly_score:.1f}/10, wind {weather_wind_ms:.1f} m/s)"))
        elif weather_anomaly_score >= 5.0:
            factors.append((weighted_weather, f"Elevated weather anomaly (score {weather_anomaly_score:.1f}/10, wind {weather_wind_ms:.1f} m/s)"))
        elif weather_anomaly_score > 0.0:
            factors.append((weighted_weather, f"Moderate weather variation (score {weather_anomaly_score:.1f}/10)"))

        # Exposure
        weighted_exposure = _W_EXPOSURE * exposure_score
        if asset.asset_type in _HIGH_EXPOSURE_TYPES:
            factors.append((weighted_exposure, f"High-exposure asset type: {asset.asset_type} (firmware attack surface)"))
        else:
            factors.append((weighted_exposure, f"Standard-exposure asset type: {asset.asset_type}"))

        # Grid stress
        weighted_stress = _W_STRESS * stress_score
        if stress_score >= 80.0:
            factors.append((weighted_stress, f"Full grid stress ({grid_stress_mw:.0f} MW deviation)"))
        elif stress_score >= 50.0:
            factors.append((weighted_stress, f"Elevated grid stress ({grid_stress_mw:.0f} MW deviation)"))
        elif stress_score > 0.0:
            factors.append((weighted_stress, f"Moderate grid stress ({grid_stress_mw:.0f} MW deviation)"))

        # Monitoring quality
        weighted_vis = _W_VISIBILITY * visibility_score
        if monitoring_quality <= 0.1:
            factors.append((weighted_vis, "Severely degraded monitoring (near-blind)"))
        elif monitoring_quality <= 0.4:
            factors.append((weighted_vis, f"Reduced monitoring visibility ({monitoring_quality * 100:.0f}% fidelity)"))
        elif monitoring_quality <= 0.7:
            factors.append((weighted_vis, f"Partial monitoring coverage ({monitoring_quality * 100:.0f}% fidelity)"))

        # Sort by weighted contribution descending, return descriptions only
        factors.sort(key=lambda x: x[0], reverse=True)
        return [desc for _, desc in factors]

    @staticmethod
    def _recommended_action(severity: AlertSeverity, asset: AssetLocation) -> str:
        """Generate a recommended security action based on severity and asset type."""
        if severity == AlertSeverity.CRITICAL:
            if asset.asset_type in _HIGH_EXPOSURE_TYPES:
                return "Isolate inverter from remote firmware update channel immediately; initiate OT incident response"
            return "Activate OT security incident response; restrict all remote maintenance access"
        if severity == AlertSeverity.HIGH:
            if asset.asset_type in _HIGH_EXPOSURE_TYPES:
                return "Isolate inverter from remote firmware update channel; increase monitoring cadence"
            return "Increase monitoring cadence; review remote-access logs; restrict non-essential VPN sessions"
        if severity == AlertSeverity.MEDIUM:
            return "Heighten monitoring of asset telemetry; flag for manual review within 2 hours"
        return "Continue normal monitoring; no immediate action required"
