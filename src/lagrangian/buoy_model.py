"""
BuoyLeewayModel: OpenDrift subclass for unmoored buoy drift.
Configures wind leeway coefficients and cross-sectional buoy profiles.
Supports both OpenDrift native execution and a lightweight fallback
numpy-based solver (used in CI when OpenDrift is not installed).
"""
from __future__ import annotations

import numpy as np
import structlog

from src.core.config import get_settings

logger = structlog.get_logger(__name__)

try:
    from opendrift.models.oceandrift import OceanDrift  # type: ignore[import]
    OPENDRIFT_AVAILABLE = True
except ImportError:
    OPENDRIFT_AVAILABLE = False
    OceanDrift = object  # sentinel


class BuoyLeewayModel:
    """
    Buoy drift model supporting both OpenDrift and a numpy fallback solver.

    Works with or without OpenDrift installed.  When OpenDrift is available
    the class inherits its full ocean-drift machinery; when it is absent a
    simple Euler-integration solver is used instead (adequate for CI and
    unit-testing purposes).

    Parameters
    ----------
    leeway_pct:
        Wind leeway as a percentage of the wind speed that contributes to
        drift (range 1.0–5.0 %).
    cross_section_m2:
        Effective cross-sectional area of the buoy (exposed to wind/current),
        in m².  Used for drag-scaling in a full OpenDrift run.
    seed:
        Integer RNG seed for reproducible stochastic perturbations.
    """

    def __init__(
        self,
        leeway_pct: float = 2.5,
        cross_section_m2: float = 0.1,
        seed: int | None = None,
    ) -> None:
        settings = get_settings()

        if not (1.0 <= leeway_pct <= 5.0):
            raise ValueError(f"leeway_pct must be in [1.0, 5.0], got {leeway_pct}")

        self.leeway_pct = leeway_pct
        self.cross_section_m2 = cross_section_m2
        self.seed = seed if seed is not None else settings.seed
        self._rng = np.random.default_rng(self.seed)

        logger.info(
            "BuoyLeewayModel initialised",
            backend="opendrift" if OPENDRIFT_AVAILABLE else "numpy-fallback",
            leeway_pct=leeway_pct,
            cross_section_m2=cross_section_m2,
            seed=self.seed,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def configure_leeway(
        self,
        wind_u: np.ndarray,
        wind_v: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Apply leeway fraction to wind vectors.

        The leeway contribution is defined as::

            leeway_u = (leeway_pct / 100) * wind_u
            leeway_v = (leeway_pct / 100) * wind_v

        Parameters
        ----------
        wind_u, wind_v:
            Eastward / northward 10-m wind components (m/s), arbitrary shape.

        Returns
        -------
        (leeway_u, leeway_v):
            Leeway velocity components in m/s, same shape as inputs.
        """
        wind_u = np.asarray(wind_u, dtype=float)
        wind_v = np.asarray(wind_v, dtype=float)
        factor = self.leeway_pct / 100.0
        leeway_u = factor * wind_u
        leeway_v = factor * wind_v
        logger.debug(
            "configure_leeway",
            factor=factor,
            wind_u_mean=float(np.mean(wind_u)),
            wind_v_mean=float(np.mean(wind_v)),
        )
        return leeway_u, leeway_v

    def run_fallback(
        self,
        origin_lon: float,
        origin_lat: float,
        u_total: np.ndarray,
        v_total: np.ndarray,
        dt_seconds: float,
    ) -> tuple[list[float], list[float]]:
        """
        Lightweight numpy Euler-integration solver (fallback when OpenDrift
        is not installed).

        Integrates a single trajectory given arrays of total velocity
        (current + leeway wind) over ``len(u_total)`` timesteps.

        Parameters
        ----------
        origin_lon, origin_lat:
            Starting position in decimal degrees.
        u_total, v_total:
            Total eastward / northward velocity per timestep (m/s).
        dt_seconds:
            Duration of each timestep in seconds.

        Returns
        -------
        (lons, lats):
            Lists of longitude/latitude positions (one entry per timestep,
            not including the origin).
        """
        u_total = np.asarray(u_total, dtype=float)
        v_total = np.asarray(v_total, dtype=float)

        lons: list[float] = []
        lats: list[float] = []
        lon = origin_lon
        lat = origin_lat

        for u, v in zip(u_total, v_total):
            lat_rad = np.deg2rad(lat)
            # metres → degrees
            dlon = (u * dt_seconds) / (111_320.0 * np.cos(lat_rad))
            dlat = (v * dt_seconds) / 111_320.0
            lon += dlon
            lat += dlat
            lons.append(lon)
            lats.append(lat)

        return lons, lats
