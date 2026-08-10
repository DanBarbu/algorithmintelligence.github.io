"""
Centralised configuration via Pydantic Settings.
All agents import from here — never hardcode paths or env vars.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Runtime mode ────────────────────────────────────────────────────────
    air_gap_mode: bool = Field(
        default=False,
        description="Disable all outbound HTTP; use local data/input/ only.",
    )
    seed: int = Field(default=42, description="Monte Carlo random seed (reproducibility).")
    log_level: str = Field(default="INFO", description="structlog log level.")

    # ── Credentials (live mode only) ────────────────────────────────────────
    cmems_username: str = Field(default="", description="Copernicus Marine username.")
    cmems_password: str = Field(default="", description="Copernicus Marine password.")

    # ── Remote endpoints ────────────────────────────────────────────────────
    aifs_base_url: str = "https://data.ecmwf.int/forecasts"
    graphcast_gcs_bucket: str = "weatherbench2"  # public GCS bucket

    # ── Data paths ──────────────────────────────────────────────────────────
    data_input_dir: Path = Path("data/input")
    data_output_dir: Path = Path("data/output")
    data_samples_dir: Path = Path("data/samples")

    # ── Pipeline defaults ───────────────────────────────────────────────────
    forecast_hours: int = Field(default=24, ge=1, le=240)
    monte_carlo_particles: int = Field(default=100, ge=10, le=10_000)
    leeway_pct: float = Field(default=2.5, ge=1.0, le=5.0)

    # ── Performance ─────────────────────────────────────────────────────────
    max_concurrent_downloads: int = Field(default=4, ge=1)
    target_grid_resolution_deg: float = Field(
        default=0.25,
        description="Unified mesh resolution in degrees (atmospheric).",
    )
    ocean_grid_resolution_deg: float = Field(
        default=1 / 12,
        description="Ocean grid native resolution (CMEMS GLORYS 1/12°).",
    )

    # ── WESF ────────────────────────────────────────────────────────────────
    turbine_cutout_ms: float = Field(
        default=25.0,
        description="Wind speed (m/s) above which turbines brake automatically.",
    )
    solar_cloud_threshold_oktas: float = Field(
        default=7.0,
        description="Cloud cover (oktas) above which GHI drop alert fires.",
    )
    cvi_alert_threshold: float = Field(
        default=65.0,
        description="CVI score above which a CRITICAL alert is emitted.",
    )

    # ── Market ──────────────────────────────────────────────────────────────
    market_id: str = Field(default="EPEX_DE", description="Default electricity market.")

    def ensure_dirs(self) -> None:
        """Create all data directories if they do not exist."""
        for d in (self.data_input_dir, self.data_output_dir, self.data_samples_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call)."""
    s = Settings()
    s.ensure_dirs()
    return s
