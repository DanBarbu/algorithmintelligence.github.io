"""
Drift corridor polygon computation.
Takes the final particle cloud (all positions at each timestep)
and computes the convex hull enclosing all particles at T+24h.
Outputs a GeoJSON Polygon (RFC 7946).
"""
from __future__ import annotations

import uuid
from typing import Any

import numpy as np
import structlog
from shapely.geometry import MultiPoint, mapping

from src.api.schemas import DriftCorridorResult, ParticleTrack
from src.core.config import get_settings

logger = structlog.get_logger(__name__)


class DriftCorridor:
    """
    Build a convex-hull drift corridor from a Monte Carlo particle ensemble.

    The corridor encloses *all* final positions of the particle tracks
    (positions at the last timestep of each track) and is returned as a
    GeoJSON Polygon together with derived metrics (area, centroid).

    Example
    -------
    >>> corridor = DriftCorridor()
    >>> result = corridor.build(tracks, forecast_hours=24)
    """

    def build(
        self,
        tracks: list[ParticleTrack],
        forecast_hours: int = 24,
        run_id: str | None = None,
        ingest_run_id: str = "",
        origin: list[float] | None = None,
        leeway_pct: float = 2.5,
        seed: int = 42,
        timestep_hours: float = 1.0,
        compute_time_seconds: float = 0.0,
    ) -> DriftCorridorResult:
        """
        Compute the convex hull drift corridor from particle tracks.

        Parameters
        ----------
        tracks:
            Ensemble of particle trajectories produced by
            :class:`~src.lagrangian.monte_carlo.MonteCarloEnsemble`.
        forecast_hours:
            Length of the forecast window (hours).  Stored as metadata.
        run_id:
            UUID for this run.  Auto-generated if not supplied.
        ingest_run_id:
            run_id of the upstream IngestResult.
        origin:
            [lon, lat] of the object's last known GPS fix.
        leeway_pct:
            Wind leeway percentage used for this run.
        seed:
            RNG seed used for this run.
        timestep_hours:
            Timestep duration (hours).
        compute_time_seconds:
            Wall-clock time taken by the upstream Monte Carlo run.

        Returns
        -------
        DriftCorridorResult
        """
        settings = get_settings()
        if run_id is None:
            run_id = str(uuid.uuid4())

        if not tracks:
            raise ValueError("tracks list is empty — cannot build corridor")

        # ── Extract final positions ───────────────────────────────────────────
        final_positions: list[list[float]] = [t.final_position for t in tracks]
        lons = np.array([p[0] for p in final_positions])
        lats = np.array([p[1] for p in final_positions])

        # ── Convex hull via Shapely ───────────────────────────────────────────
        cloud = MultiPoint(list(zip(lons, lats)))
        hull = cloud.convex_hull          # Point, LineString, or Polygon

        geojson: dict[str, Any] = dict(mapping(hull))

        # Ensure the GeoJSON is always a Polygon (handle degenerate cases)
        if hull.geom_type == "Point":
            # Single point or coincident points — create a tiny circle proxy
            # expressed as a polygon by buffering 0.001° (~100 m)
            geojson = dict(mapping(hull.buffer(0.001)))
            hull = hull.buffer(0.001)
        elif hull.geom_type == "LineString":
            # Co-linear points — buffer to a thin corridor
            hull = hull.buffer(0.001)
            geojson = dict(mapping(hull))

        # ── Area in km² ──────────────────────────────────────────────────────
        centroid_lon = float(hull.centroid.x)
        centroid_lat = float(hull.centroid.y)

        area_km2 = self._area_km2(hull, centroid_lon, centroid_lat)

        logger.info(
            "DriftCorridor built",
            n_tracks=len(tracks),
            hull_type=hull.geom_type,
            area_km2=area_km2,
            centroid=[centroid_lon, centroid_lat],
        )

        return DriftCorridorResult(
            run_id=run_id,
            ingest_run_id=ingest_run_id,
            origin=origin if origin is not None else [float(lons.mean()), float(lats.mean())],
            leeway_pct=leeway_pct,
            seed=seed,
            n_particles=len(tracks),
            timestep_hours=timestep_hours,
            forecast_hours=forecast_hours,
            particle_tracks=tracks,
            corridor_geojson=geojson,
            corridor_area_km2=area_km2,
            centroid=[centroid_lon, centroid_lat],
            compute_time_seconds=compute_time_seconds,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _area_km2(hull, centroid_lon: float, centroid_lat: float) -> float:
        """
        Project the hull to a local azimuthal-equidistant CRS centred on the
        centroid and return its area in km².
        """
        try:
            from pyproj import CRS, Transformer
            from shapely.ops import transform as shp_transform

            # WGS84 geographic → local azimuthal equidistant (metres)
            wgs84 = CRS("EPSG:4326")
            aeqd_crs = CRS.from_proj4(
                f"+proj=aeqd +lat_0={centroid_lat} +lon_0={centroid_lon} "
                f"+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
            )
            transformer = Transformer.from_crs(wgs84, aeqd_crs, always_xy=True)
            projected = shp_transform(transformer.transform, hull)
            area_m2 = projected.area
            return max(area_m2 / 1e6, 0.0)  # m² → km²
        except Exception as exc:
            logger.warning("area_km2 projection failed, using degree approximation", error=str(exc))
            # Rough fallback: degrees² × (111.32 km/deg)²
            area_deg2 = hull.area
            return abs(area_deg2) * (111.32 ** 2)


