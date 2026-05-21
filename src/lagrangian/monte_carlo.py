"""
Monte Carlo particle ensemble for probabilistic drift simulation.
Injects Gaussian noise into forcing vectors to produce a spread of trajectories
representing forecast uncertainty.

Default noise parameters (from PRD):
  currents: σ = 0.05 m/s (±5 cm/s)
  winds:    σ = 1.5 m/s
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import structlog

from src.api.schemas import ParticleTrack
from src.core.config import get_settings

logger = structlog.get_logger(__name__)

_M_PER_DEG_LAT: float = 111_320.0  # metres per degree latitude


class MonteCarloEnsemble:
    """
    Probabilistic Lagrangian particle-tracking ensemble.

    Initialises ``n_particles`` at a common origin and propagates each one
    using Euler integration with per-step Gaussian noise injected into the
    forcing fields (ocean currents and 10-m winds).

    Parameters
    ----------
    n_particles:
        Number of ensemble members (≥ 10).
    seed:
        Integer RNG seed for fully reproducible results.
    current_sigma:
        Standard deviation of current noise (m/s).  Default 0.05.
    wind_sigma:
        Standard deviation of wind noise (m/s).  Default 1.5.
    """

    def __init__(
        self,
        n_particles: int = 100,
        seed: int | None = None,
        current_sigma: float = 0.05,
        wind_sigma: float = 1.5,
    ) -> None:
        settings = get_settings()

        if n_particles < 10:
            raise ValueError(f"n_particles must be ≥ 10, got {n_particles}")
        if current_sigma < 0:
            raise ValueError("current_sigma must be non-negative")
        if wind_sigma < 0:
            raise ValueError("wind_sigma must be non-negative")

        self.n_particles = n_particles
        self.seed = seed if seed is not None else settings.seed
        self.current_sigma = current_sigma
        self.wind_sigma = wind_sigma

        logger.info(
            "MonteCarloEnsemble initialised",
            n_particles=n_particles,
            seed=self.seed,
            current_sigma=current_sigma,
            wind_sigma=wind_sigma,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        origin_lon: float,
        origin_lat: float,
        u_current: float,
        v_current: float,
        u_wind: float,
        v_wind: float,
        u_geo: float,
        v_geo: float,
        leeway_pct: float,
        dt_hours: float,
        n_steps: int,
    ) -> list[ParticleTrack]:
        """
        Execute the Monte Carlo particle ensemble.

        All forcing inputs are scalar values representing spatially- and
        temporally-averaged forcing at the origin point for the forecast
        period.  Per-step Gaussian noise is added to each particle
        independently.

        Parameters
        ----------
        origin_lon, origin_lat:
            Last known position of the drifting object (decimal degrees).
        u_current, v_current:
            Background ocean current (m/s), eastward / northward.
        u_wind, v_wind:
            10-m wind components (m/s), eastward / northward.
        u_geo, v_geo:
            Geostrophic correction components (m/s), eastward / northward.
        leeway_pct:
            Wind leeway percentage (1.0–5.0).
        dt_hours:
            Duration of each timestep in hours.
        n_steps:
            Number of integration timesteps.

        Returns
        -------
        list[ParticleTrack]
            One ``ParticleTrack`` per ensemble member.  Each track contains
            ``n_steps`` positions (the origin is *not* included).
        """
        if not (1.0 <= leeway_pct <= 5.0):
            raise ValueError(f"leeway_pct must be in [1.0, 5.0], got {leeway_pct}")
        if n_steps < 1:
            raise ValueError("n_steps must be ≥ 1")
        if dt_hours <= 0:
            raise ValueError("dt_hours must be positive")

        rng = np.random.default_rng(self.seed)
        dt_seconds = dt_hours * 3600.0
        leeway_factor = leeway_pct / 100.0

        # Shape: (n_particles, n_steps) — pre-sample ALL noise at once for
        # reproducibility regardless of Python loop ordering.
        du_cur = rng.normal(0.0, self.current_sigma, size=(self.n_particles, n_steps))
        dv_cur = rng.normal(0.0, self.current_sigma, size=(self.n_particles, n_steps))
        du_win = rng.normal(0.0, self.wind_sigma,    size=(self.n_particles, n_steps))
        dv_win = rng.normal(0.0, self.wind_sigma,    size=(self.n_particles, n_steps))

        tracks: list[ParticleTrack] = []

        for pid in range(self.n_particles):
            lon = origin_lon
            lat = origin_lat
            positions: list[list[float]] = []

            for step in range(n_steps):
                # Total velocity components (m/s)
                u_total = (
                    (u_current + du_cur[pid, step])
                    + u_geo
                    + leeway_factor * (u_wind + du_win[pid, step])
                )
                v_total = (
                    (v_current + dv_cur[pid, step])
                    + v_geo
                    + leeway_factor * (v_wind + dv_win[pid, step])
                )

                lat_rad = math.radians(lat)
                cos_lat = math.cos(lat_rad)

                # Euler step: convert m/s → degrees
                dlon = (u_total * dt_seconds) / (_M_PER_DEG_LAT * (cos_lat if cos_lat != 0 else 1e-9))
                dlat = (v_total * dt_seconds) / _M_PER_DEG_LAT

                lon += dlon
                lat += dlat

                positions.append([lon, lat])

            tracks.append(
                ParticleTrack(
                    particle_id=pid,
                    positions=positions,
                    final_position=positions[-1],
                )
            )

        logger.info(
            "MonteCarloEnsemble.run complete",
            n_particles=self.n_particles,
            n_steps=n_steps,
            dt_hours=dt_hours,
            origin_lon=origin_lon,
            origin_lat=origin_lat,
        )

        return tracks
