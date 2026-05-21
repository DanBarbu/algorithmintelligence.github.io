"""
Geostrophic velocity computation from Sea Surface Height (SSH) anomaly gradients.
Corrects for sub-grid mesoscale eddies absent from raw Eulerian current fields.

Theory:
  u_geo = -(g/f) * dSSH/dy
  v_geo = +(g/f) * dSSH/dx
  where f = 2Ω sin(φ) is the Coriolis parameter.
"""
from __future__ import annotations

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Physical constants
_GRAVITY: float = 9.81           # m/s²
_OMEGA: float = 7.2921e-5        # Earth rotation rate (rad/s)
_M_PER_DEG_LAT: float = 111_320.0  # metres per degree latitude
_GEO_SPEED_CLIP: float = 3.0    # m/s – physical sanity limit
_EQUATORIAL_LAT: float = 0.5    # degrees – singularity guard


class GeostrophicCorrector:
    """
    Compute geostrophic surface-current corrections from SSH anomaly fields.

    Usage
    -----
    >>> corr = GeostrophicCorrector()
    >>> u_geo, v_geo = corr.compute(ssh, lat, lon)
    """

    def compute(
        self,
        ssh: np.ndarray,
        lat: np.ndarray,
        lon: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Derive geostrophic velocity components from SSH gradients.

        Parameters
        ----------
        ssh:
            Sea Surface Height anomaly in metres.  Shape (ny, nx).
        lat:
            Latitude coordinate array in decimal degrees.
            - 1-D of length ny  OR  2-D of shape (ny, nx).
        lon:
            Longitude coordinate array in decimal degrees.
            - 1-D of length nx  OR  2-D of shape (ny, nx).

        Returns
        -------
        u_geo:
            Eastward geostrophic velocity (m/s), shape (ny, nx).
        v_geo:
            Northward geostrophic velocity (m/s), shape (ny, nx).

        Notes
        -----
        * Cells where |lat| < 0.5° are set to zero (equatorial singularity).
        * Speeds are clipped to ±3.0 m/s.
        """
        ssh = np.asarray(ssh, dtype=float)
        lat = np.asarray(lat, dtype=float)
        lon = np.asarray(lon, dtype=float)

        ny, nx = ssh.shape

        # Broadcast lat/lon to (ny, nx) grids
        if lat.ndim == 1:
            lat_2d = np.broadcast_to(lat[:, np.newaxis], (ny, nx)).copy()
        else:
            lat_2d = lat.copy()

        if lon.ndim == 1:
            lon_2d = np.broadcast_to(lon[np.newaxis, :], (ny, nx)).copy()
        else:
            lon_2d = lon.copy()

        lat_rad = np.deg2rad(lat_2d)

        # ── Grid spacing in metres ────────────────────────────────────────────
        # dy: spacing between rows in metres (latitude direction)
        if lat.ndim == 1 and lat.size > 1:
            dy_deg = np.abs(np.gradient(lat))               # (ny,)
            dy_m = (dy_deg * _M_PER_DEG_LAT)[:, np.newaxis]  # (ny, 1)
            dy_m = np.broadcast_to(dy_m, (ny, nx)).copy()
        else:
            dy_m_2d = np.abs(np.gradient(lat_2d, axis=0)) * _M_PER_DEG_LAT
            dy_m = dy_m_2d

        # dx: spacing between columns in metres (longitude direction, lat-dependent)
        if lon.ndim == 1 and lon.size > 1:
            dx_deg = np.abs(np.gradient(lon))               # (nx,)
            dx_m = (dx_deg[np.newaxis, :] *
                    _M_PER_DEG_LAT * np.cos(lat_rad))       # (ny, nx)
        else:
            dx_m = (np.abs(np.gradient(lon_2d, axis=1)) *
                    _M_PER_DEG_LAT * np.cos(lat_rad))

        # Guard against division-by-zero spacing (single-cell grids)
        dy_m = np.where(dy_m == 0, 1.0, dy_m)
        dx_m = np.where(dx_m == 0, 1.0, dx_m)

        # ── SSH spatial gradients ─────────────────────────────────────────────
        # np.gradient returns [dSSH/drow, dSSH/dcol] in SSH units per index unit;
        # we divide by grid spacing to get dSSH/dy and dSSH/dx in m/m (dimensionless).
        d_ssh_dy = np.gradient(ssh, axis=0) / dy_m   # dSSH/dy
        d_ssh_dx = np.gradient(ssh, axis=1) / dx_m   # dSSH/dx

        # ── Coriolis parameter ────────────────────────────────────────────────
        f = 2.0 * _OMEGA * np.sin(lat_rad)

        # ── Geostrophic velocities ────────────────────────────────────────────
        # Avoid division by near-zero f (equatorial guard applied after)
        safe_f = np.where(np.abs(f) < 1e-10, np.nan, f)
        u_geo = -(_GRAVITY / safe_f) * d_ssh_dy
        v_geo = +(_GRAVITY / safe_f) * d_ssh_dx

        # Replace NaN from safe_f with 0
        u_geo = np.where(np.isnan(u_geo), 0.0, u_geo)
        v_geo = np.where(np.isnan(v_geo), 0.0, v_geo)

        # ── Equatorial singularity mask ───────────────────────────────────────
        equatorial = np.abs(lat_2d) < _EQUATORIAL_LAT
        u_geo = np.where(equatorial, 0.0, u_geo)
        v_geo = np.where(equatorial, 0.0, v_geo)

        # ── Physical speed clipping ───────────────────────────────────────────
        u_geo = np.clip(u_geo, -_GEO_SPEED_CLIP, _GEO_SPEED_CLIP)
        v_geo = np.clip(v_geo, -_GEO_SPEED_CLIP, _GEO_SPEED_CLIP)

        logger.debug(
            "geostrophic_compute",
            u_geo_max=float(np.max(np.abs(u_geo))),
            v_geo_max=float(np.max(np.abs(v_geo))),
            equatorial_cells=int(np.sum(equatorial)),
        )

        return u_geo, v_geo
