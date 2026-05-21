"""
APP-6D / MIL-STD-2525D Tactical Symbology Builder.
Generates GeoJSON FeatureCollections with Symbol Identification Codes (SIDCs)
for display in NATO-compatible tactical mapping systems and GeoServer WMS layers.

Key SIDCs used:
  Drift corridor (hostile track area):   SFGP-ACAI-------  (area of interest)
  Drift origin (last known position):    SFSP---------H---  (sub-surface track)
  Wind cut-out zone (hazard area):       SFGP-ACMH-------  (hazard area)
  CVI CRITICAL asset (cyber threat):     SFGP-ACMC-------  (CBRN hazard)
  Price spike marker:                    SFGP-ACMF-------  (infrastructure)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from src.api.schemas import (
    AlertSeverity,
    AlertType,
    App6ExportResult,
    App6Feature,
    CVIAlert,
    DriftCorridorResult,
    RampAlertPayload,
)
from src.core.config import get_settings

logger = structlog.get_logger(__name__)

# APP-6D Symbol Identification Codes
_SIDC_DRIFT_CORRIDOR = "SFGP-ACAI-------"   # neutral, area of interest
_SIDC_DRIFT_ORIGIN   = "SFSP---------H---"  # last known position (sub-surface)
_SIDC_HAZARD_AREA    = "SFGP-ACMH-------"   # hazard area (turbine cut-out)
_SIDC_INFRA_MARKER   = "SFGP-ACMF-------"   # infrastructure (solar drop)
_SIDC_CBRN_HAZARD    = "SFGP-ACMC-------"   # CBRN hazard (critical CVI)

# Mapping alert_type → SIDC
_RAMP_SIDC: dict[AlertType, str] = {
    AlertType.TURBINE_CUTOUT: _SIDC_HAZARD_AREA,
    AlertType.SOLAR_DROP:     _SIDC_INFRA_MARKER,
    AlertType.NEGATIVE_PRICE: _SIDC_INFRA_MARKER,
    AlertType.CVI_THRESHOLD:  _SIDC_CBRN_HAZARD,
}

# Mapping severity → SIDC for CVI alerts
_CVI_SIDC: dict[AlertSeverity, str] = {
    AlertSeverity.CRITICAL: _SIDC_CBRN_HAZARD,
    AlertSeverity.HIGH:     _SIDC_HAZARD_AREA,
    AlertSeverity.MEDIUM:   _SIDC_INFRA_MARKER,
    AlertSeverity.LOW:      _SIDC_INFRA_MARKER,
}


def _make_feature(
    sidc: str,
    name: str,
    geometry: dict[str, Any],
    **extra_props: Any,
) -> App6Feature:
    """
    Construct an App6Feature with the standard GeoJSON feature template.

    Parameters
    ----------
    sidc:
        APP-6D Symbol Identification Code.
    name:
        Human-readable feature name.
    geometry:
        RFC 7946 GeoJSON geometry dict.
    **extra_props:
        Additional key-value pairs merged into the feature properties dict.

    Returns
    -------
    App6Feature
    """
    props: dict[str, Any] = {"sidc": sidc, "name": name, **extra_props}
    return App6Feature(
        sidc=sidc,
        name=name,
        geojson_geometry=geometry,
        properties=props,
    )


class App6Symbology:
    """
    APP-6D / MIL-STD-2525D tactical symbology builder.

    Converts internal pipeline results (drift corridors, WESF alerts, CVI
    alerts) into GeoJSON FeatureCollections annotated with NATO-standard
    Symbol Identification Codes for rendering in tactical mapping systems
    and GeoServer WMS layers.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        logger.info("App6Symbology initialised")

    # ── Feature builders ──────────────────────────────────────────────────────

    def build_drift_corridor(self, drift_result: DriftCorridorResult) -> App6Feature:
        """
        Build a Polygon App6Feature representing the drift corridor.

        Uses the corridor_geojson from the DriftCorridorResult directly as
        the GeoJSON geometry.  The SIDC "SFGP-ACAI-------" marks this as a
        neutral area of interest in NATO tactical displays.

        Parameters
        ----------
        drift_result:
            Completed drift corridor simulation result.

        Returns
        -------
        App6Feature with Polygon geometry and drift metrics in properties.
        """
        geometry = drift_result.corridor_geojson
        return _make_feature(
            sidc=_SIDC_DRIFT_CORRIDOR,
            name=f"Drift Corridor [{drift_result.run_id[:8]}]",
            geometry=geometry,
            run_id=drift_result.run_id,
            leeway_pct=drift_result.leeway_pct,
            corridor_area_km2=drift_result.corridor_area_km2,
            n_particles=drift_result.n_particles,
        )

    def build_drift_origin(self, drift_result: DriftCorridorResult) -> App6Feature:
        """
        Build a Point App6Feature at the drift simulation origin.

        The SIDC "SFSP---------H---" marks this as a last-known-position
        sub-surface track marker (applied to surface object last-known GPS fix).

        Parameters
        ----------
        drift_result:
            Completed drift corridor simulation result.

        Returns
        -------
        App6Feature with Point geometry at drift origin.
        """
        lon, lat = drift_result.origin
        geometry: dict[str, Any] = {
            "type": "Point",
            "coordinates": [lon, lat],
        }
        return _make_feature(
            sidc=_SIDC_DRIFT_ORIGIN,
            name=f"Drift Origin [{drift_result.run_id[:8]}]",
            geometry=geometry,
            run_id=drift_result.run_id,
            origin_lon=lon,
            origin_lat=lat,
        )

    def build_ramp_alert_zone(self, alert: RampAlertPayload) -> App6Feature:
        """
        Build a Point (with radius property) App6Feature for a WESF ramp alert.

        Alert type → SIDC mapping:
          TURBINE_CUTOUT → "SFGP-ACMH-------" (hazard area)
          SOLAR_DROP     → "SFGP-ACMF-------" (infrastructure)

        Parameters
        ----------
        alert:
            WESF ramp alert payload from the ramp_forecaster.

        Returns
        -------
        App6Feature with Point geometry centred on the asset location.
        """
        sidc = _RAMP_SIDC.get(alert.alert_type, _SIDC_HAZARD_AREA)
        geometry: dict[str, Any] = {
            "type": "Point",
            "coordinates": [alert.asset.lon, alert.asset.lat],
        }
        return _make_feature(
            sidc=sidc,
            name=f"Ramp Alert [{alert.alert_type.value}] {alert.asset.asset_id}",
            geometry=geometry,
            run_id=alert.run_id,
            alert_type=alert.alert_type.value,
            severity=alert.severity.value,
            trigger_value=alert.trigger_value,
            threshold_value=alert.threshold_value,
            unit=alert.unit,
            asset_id=alert.asset.asset_id,
            estimated_mw_loss=alert.estimated_mw_loss,
            # Circle-convention radius in metres (1 km default marker radius)
            radius_m=1000.0,
        )

    def build_cvi_alert(self, alert: CVIAlert) -> App6Feature:
        """
        Build a Point App6Feature for a Cyber Vulnerability Index alert.

        Severity → SIDC mapping:
          CRITICAL → "SFGP-ACMC-------" (CBRN hazard)
          HIGH     → "SFGP-ACMH-------" (hazard area)

        Parameters
        ----------
        alert:
            CVI alert payload from the cvi_engine.

        Returns
        -------
        App6Feature with Point geometry at the asset location.
        """
        sidc = _CVI_SIDC.get(alert.severity, _SIDC_HAZARD_AREA)
        geometry: dict[str, Any] = {
            "type": "Point",
            "coordinates": [alert.asset.lon, alert.asset.lat],
        }
        return _make_feature(
            sidc=sidc,
            name=f"CVI Alert [{alert.severity.value}] {alert.asset.asset_id}",
            geometry=geometry,
            run_id=alert.run_id,
            severity=alert.severity.value,
            cvi_score=alert.cvi_score,
            weather_severity_score=alert.weather_severity_score,
            asset_id=alert.asset.asset_id,
            contributing_factors=alert.contributing_factors,
            recommended_action=alert.recommended_action,
        )

    # ── Export ────────────────────────────────────────────────────────────────

    def export(
        self,
        drift: DriftCorridorResult | None,
        ramp_alerts: list[RampAlertPayload],
        cvi_alerts: list[CVIAlert],
        run_id: str,
        output_dir: Path,
    ) -> App6ExportResult:
        """
        Assemble all symbology features into a GeoJSON FeatureCollection and
        write it to disk.

        Parameters
        ----------
        drift:
            Drift corridor result; if None, drift features are omitted.
        ramp_alerts:
            List of WESF ramp alert payloads.
        cvi_alerts:
            List of CVI alert payloads.
        run_id:
            Pipeline run identifier used to name the output file and embedded
            in feature properties.
        output_dir:
            Directory to write the GeoJSON file.  Created if absent.

        Returns
        -------
        App6ExportResult with path, feature count, and feature list.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        log = logger.bind(run_id=run_id)
        log.info("App6Symbology.export started")

        features: list[App6Feature] = []

        # Drift features
        if drift is not None:
            features.append(self.build_drift_corridor(drift))
            features.append(self.build_drift_origin(drift))

        # Ramp alert features
        for alert in ramp_alerts:
            features.append(self.build_ramp_alert_zone(alert))

        # CVI alert features
        for cvi in cvi_alerts:
            features.append(self.build_cvi_alert(cvi))

        # Assemble GeoJSON FeatureCollection
        feature_collection: dict[str, Any] = {
            "type": "FeatureCollection",
            "properties": {
                "run_id": run_id,
                "feature_count": len(features),
            },
            "features": [
                {
                    "type": "Feature",
                    "geometry": f.geojson_geometry,
                    "properties": f.properties,
                }
                for f in features
            ],
        }

        out_path = output_dir / f"{run_id}.app6.geojson"
        out_path.write_text(
            json.dumps(feature_collection, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        result = App6ExportResult(
            run_id=run_id,
            geojson_path=str(out_path),
            feature_count=len(features),
            features=features,
        )

        log.info(
            "App6Symbology.export finished",
            feature_count=len(features),
            path=str(out_path),
        )
        return result
