"""
APP-6D / MIL-STD-2525D Symbology Exporter.
Converts drift corridor polygons, asset locations, and alert markers
into a GeoJSON FeatureCollection annotated with SIDC codes.

SIDC structure (APP-6D, 20 characters):
  Characters 1-2:  Version (10 = APP-6D)
  Character  3:    Standard identity (P=Pending, U=Unknown, F=Friend, N=Neutral, H=Hostile, S=Suspect)
  Characters 4-6:  Symbol Set (01=Air, 10=Ground, 30=Land Unit, 40=Sea Surface)
  Character  7:    Status (0=Present, 1=Anticipated)
  Characters 8-10: HQ/TF/Dummy (000=none)
  Characters 11-20: Function ID (10 chars, padded with hyphens)
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import structlog

from src.api.schemas import (
    App6ExportResult,
    App6Feature,
    AssetLocation,
    CVIAlert,
    DriftCorridorResult,
    RampAlertPayload,
)
from src.core.config import get_settings

logger = structlog.get_logger(__name__)

# APP-6D SIDCs used in this platform
_SIDC_DRIFT_CORRIDOR = "10013500001101000000"   # Sea Surface - Environmental (drift zone)
_SIDC_WIND_TURBINE   = "10062500001101000000"   # Infrastructure - Wind Turbine
_SIDC_SOLAR_PV       = "10062500001201000000"   # Infrastructure - Solar PV
_SIDC_INVERTER       = "10062500001301000000"   # Infrastructure - Inverter
_SIDC_RAMP_ALERT     = "10033500001101000000"   # Control Measure - Weather Alert
_SIDC_CVI_ALERT      = "10033500002101000000"   # Control Measure - Cyber Threat

_ASSET_TYPE_SIDC: dict[str, str] = {
    "WIND_TURBINE": _SIDC_WIND_TURBINE,
    "SOLAR_PV": _SIDC_SOLAR_PV,
    "INVERTER": _SIDC_INVERTER,
}


def _asset_point_geometry(asset: AssetLocation) -> dict[str, Any]:
    return {"type": "Point", "coordinates": [asset.lon, asset.lat]}


class App6Symbology:
    """
    APP-6D / MIL-STD-2525D GeoJSON symbology exporter.

    Converts all pipeline artifacts (drift corridor, assets, alerts)
    into a single GeoJSON FeatureCollection with SIDC-annotated features.

    Parameters
    ----------
    output_dir:
        Directory to write the .app6.geojson file.
    standard_identity:
        APP-6D standard identity character ('F'=Friend, 'H'=Hostile, etc.).
    """

    def __init__(
        self,
        output_dir: Path,
        standard_identity: str = "F",
    ) -> None:
        self._settings = get_settings()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.standard_identity = standard_identity.upper()[0]

        logger.info(
            "App6Symbology initialised",
            output_dir=str(self.output_dir),
            standard_identity=self.standard_identity,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def export(
        self,
        drift: DriftCorridorResult,
        assets: list[AssetLocation],
        ramp_alerts: list[RampAlertPayload],
        cvi_alerts: list[CVIAlert],
        run_id: str | None = None,
    ) -> App6ExportResult:
        """
        Build a GeoJSON FeatureCollection and write it to disk.

        Parameters
        ----------
        drift:
            Drift corridor result; the corridor polygon is exported as-is.
        assets:
            Asset locations (one point feature per asset).
        ramp_alerts:
            Ramp alert payloads (one point feature per alert, co-located with asset).
        cvi_alerts:
            CVI alert payloads (one point feature per alert).
        run_id:
            Identifier for this export run.  Auto-generated if None.

        Returns
        -------
        App6ExportResult
        """
        run_id = run_id or str(uuid.uuid4())
        log = logger.bind(run_id=run_id)
        log.info("App6Symbology.export started")

        features: list[App6Feature] = []

        # ── Drift corridor polygon ────────────────────────────────────────────
        drift_feature = App6Feature(
            sidc=self._apply_identity(_SIDC_DRIFT_CORRIDOR),
            name=f"Drift Corridor {run_id[:8]}",
            geojson_geometry=drift.corridor_geojson,
            properties={
                "run_id": drift.run_id,
                "area_km2": drift.corridor_area_km2,
                "n_particles": drift.n_particles,
                "leeway_pct": drift.leeway_pct,
                "forecast_hours": drift.forecast_hours,
                "centroid_lon": drift.centroid[0],
                "centroid_lat": drift.centroid[1],
                "feature_type": "drift_corridor",
            },
        )
        features.append(drift_feature)
        log.debug("Drift corridor feature added")

        # ── Asset point features ──────────────────────────────────────────────
        for asset in assets:
            sidc = self._apply_identity(
                _ASSET_TYPE_SIDC.get(asset.asset_type, _SIDC_INVERTER)
            )
            asset_feature = App6Feature(
                sidc=sidc,
                name=f"{asset.asset_type} {asset.asset_id}",
                geojson_geometry=_asset_point_geometry(asset),
                properties={
                    "asset_id": asset.asset_id,
                    "asset_type": asset.asset_type,
                    "rated_mw": asset.rated_mw,
                    "feature_type": "asset",
                },
            )
            features.append(asset_feature)

        log.debug("Asset features added", count=len(assets))

        # ── Ramp alert markers ────────────────────────────────────────────────
        for alert in ramp_alerts:
            alert_feature = App6Feature(
                sidc=self._apply_identity(_SIDC_RAMP_ALERT),
                name=f"{alert.alert_type.value} @ {alert.asset.asset_id}",
                geojson_geometry=_asset_point_geometry(alert.asset),
                properties={
                    "run_id": alert.run_id,
                    "alert_type": alert.alert_type.value,
                    "severity": alert.severity.value,
                    "trigger_value": alert.trigger_value,
                    "unit": alert.unit,
                    "asset_id": alert.asset.asset_id,
                    "feature_type": "ramp_alert",
                },
            )
            features.append(alert_feature)

        log.debug("Ramp alert features added", count=len(ramp_alerts))

        # ── CVI alert markers ─────────────────────────────────────────────────
        for cvi in cvi_alerts:
            cvi_feature = App6Feature(
                sidc=self._apply_identity(_SIDC_CVI_ALERT),
                name=f"CVI {cvi.cvi_score:.1f} @ {cvi.asset.asset_id}",
                geojson_geometry=_asset_point_geometry(cvi.asset),
                properties={
                    "run_id": cvi.run_id,
                    "cvi_score": cvi.cvi_score,
                    "severity": cvi.severity.value,
                    "asset_id": cvi.asset.asset_id,
                    "recommended_action": cvi.recommended_action,
                    "feature_type": "cvi_alert",
                },
            )
            features.append(cvi_feature)

        log.debug("CVI alert features added", count=len(cvi_alerts))

        # ── Build GeoJSON FeatureCollection ───────────────────────────────────
        feature_collection: dict[str, Any] = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": f.geojson_geometry,
                    "properties": {
                        "sidc": f.sidc,
                        "name": f.name,
                        **f.properties,
                    },
                }
                for f in features
            ],
            "metadata": {
                "run_id": run_id,
                "standard": "APP-6D",
                "standard_identity": self.standard_identity,
                "feature_count": len(features),
            },
        }

        geojson_path = self.output_dir / f"{run_id}.app6.geojson"
        geojson_path.write_text(
            json.dumps(feature_collection, indent=2), encoding="utf-8"
        )

        result = App6ExportResult(
            run_id=run_id,
            geojson_path=str(geojson_path),
            feature_count=len(features),
            features=features,
        )

        log.info(
            "App6Symbology.export finished",
            geojson_path=str(geojson_path),
            feature_count=len(features),
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _apply_identity(self, sidc: str) -> str:
        """
        Substitute the standard identity character (position index 2, 0-based)
        of a SIDC code with ``self.standard_identity``.
        """
        if len(sidc) < 3:
            return sidc
        return sidc[:2] + self.standard_identity + sidc[3:]
