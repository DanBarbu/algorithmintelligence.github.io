"""
WESF Electricity Price Forecaster.
Uses N-BEATS (Neural Basis Expansion Analysis for Time Series) via the Darts library
to predict spot-market electricity prices with weather feature integration.

Falls back to SARIMA (statsmodels) if torch/darts is not available in the environment.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from src.api.schemas import MarketID, PriceForecast
from src.core.config import get_settings

if TYPE_CHECKING:
    import pandas as pd
    import numpy as np

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports
# ---------------------------------------------------------------------------
try:
    import numpy as _np  # type: ignore

    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False
    _np = None  # type: ignore

try:
    import pandas as _pd  # type: ignore

    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False
    _pd = None  # type: ignore

# Darts / PyTorch (may not be installed)
try:
    from darts import TimeSeries as _DartsTimeSeries  # type: ignore
    from darts.models import NBEATSModel as _NBEATSModel  # type: ignore

    _DARTS_AVAILABLE = True
    logger.debug("darts+torch available — N-BEATS model enabled")
except ImportError:
    _DARTS_AVAILABLE = False
    _DartsTimeSeries = None  # type: ignore
    _NBEATSModel = None  # type: ignore
    logger.warning("darts/torch not available; N-BEATS disabled")

# Statsmodels SARIMA fallback
try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX as _SARIMAX  # type: ignore

    _STATSMODELS_AVAILABLE = True
    logger.debug("statsmodels available — SARIMA fallback enabled")
except ImportError:
    _STATSMODELS_AVAILABLE = False
    _SARIMAX = None  # type: ignore
    logger.warning("statsmodels not available; SARIMA fallback disabled")


# ---------------------------------------------------------------------------
# Module-level utility: synthetic price series
# ---------------------------------------------------------------------------

def _synthetic_price_series(n_hours: int = 8760, seed: int = 42) -> "pd.Series":
    """
    Generate a realistic synthetic hourly electricity price series.

    The series combines:
    - Daily seasonality: peak at 08:00 and 18:00, trough at 03:00
    - Weekly seasonality: lower prices on weekends
    - Random noise
    - Occasional negative price spikes (simulating high renewables surplus)

    Parameters
    ----------
    n_hours : int
        Number of hourly observations to generate.
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    pd.Series
        Series with a UTC hourly DatetimeIndex and price values in €/MWh.
    """
    if not _NUMPY_AVAILABLE:
        raise ImportError("numpy is required to generate synthetic price series")
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required to generate synthetic price series")

    rng = _np.random.default_rng(seed)
    hours = _np.arange(n_hours, dtype=float)

    # Daily seasonality (period = 24 h)
    daily = 30.0 * _np.sin(2 * _np.pi * (hours - 6) / 24.0)

    # Weekly seasonality (period = 168 h) — weekends ~15 €/MWh lower
    weekly = -15.0 * _np.sin(2 * _np.pi * hours / 168.0)

    # White noise
    noise = rng.normal(0.0, 8.0, n_hours)

    # Base price
    base = 55.0

    prices = base + daily + weekly + noise

    # Inject negative price events (≈ 5 % of hours) — renewable surplus
    n_neg = max(1, int(n_hours * 0.05))
    neg_idx = rng.choice(n_hours, size=n_neg, replace=False)
    prices[neg_idx] -= rng.uniform(30.0, 120.0, n_neg)

    # Inject occasional high-price spikes (scarcity events)
    n_spike = max(1, int(n_hours * 0.01))
    spike_idx = rng.choice(n_hours, size=n_spike, replace=False)
    prices[spike_idx] += rng.uniform(200.0, 600.0, n_spike)

    # Clamp to physical range
    prices = _np.clip(prices, -500.0, 3000.0)

    start = _pd.Timestamp("2025-01-01 00:00:00", tz="UTC")
    index = _pd.date_range(start=start, periods=n_hours, freq="h")
    return _pd.Series(prices, index=index, name="price_eur_mwh")


# ---------------------------------------------------------------------------
# Main model class
# ---------------------------------------------------------------------------

class ElectricityPriceModel:
    """
    Electricity spot market price forecaster.

    Tries N-BEATS (via Darts) if available; falls back to SARIMA otherwise.
    A further fallback (naive seasonal mean) is used when neither ML library
    is present, so the class is always importable and testable.

    Parameters
    ----------
    market : str
        Market identifier (e.g. "EPEX_DE").  Must correspond to ``MarketID``.
    seed : int
        RNG seed for reproducibility of stochastic training steps.
    """

    _INPUT_CHUNK: int = 24
    _OUTPUT_CHUNK: int = 24
    _N_EPOCHS: int = 20

    def __init__(self, market: str = "EPEX_DE", seed: int = 42) -> None:
        self.settings = get_settings()
        self.market_str = market
        self.seed = seed
        self.run_id: str = str(uuid.uuid4())

        self._model: Any = None
        self._model_name: str = "naive_seasonal"
        self._fitted: bool = False
        self._training_series: "pd.Series | None" = None

        logger.info(
            "ElectricityPriceModel initialised",
            market=market,
            seed=seed,
            darts_available=_DARTS_AVAILABLE,
            statsmodels_available=_STATSMODELS_AVAILABLE,
        )

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        price_series: "pd.Series",
        weather_features: "pd.DataFrame | None" = None,
    ) -> None:
        """
        Fit the forecasting model.

        Tries N-BEATS first, then SARIMA, then falls back to a naive
        seasonal (hour-of-day mean) model that requires only numpy+pandas.

        Parameters
        ----------
        price_series : pd.Series
            Hourly price observations with a UTC DatetimeIndex.
        weather_features : pd.DataFrame | None
            Optional weather covariates (used by Darts if available).
        """
        self._training_series = price_series.copy()

        # ── Attempt 1: Darts N-BEATS ──────────────────────────────────
        if _DARTS_AVAILABLE:
            try:
                self._train_nbeats(price_series, weather_features)
                logger.info("N-BEATS training complete", market=self.market_str)
                return
            except Exception as exc:
                logger.warning(
                    "N-BEATS training failed; falling back to SARIMA",
                    error=str(exc),
                    market=self.market_str,
                )

        # ── Attempt 2: SARIMA ────────────────────────────────────────
        if _STATSMODELS_AVAILABLE:
            try:
                self._train_sarima(price_series)
                logger.info("SARIMA training complete", market=self.market_str)
                return
            except Exception as exc:
                logger.warning(
                    "SARIMA training failed; falling back to naive seasonal model",
                    error=str(exc),
                    market=self.market_str,
                )

        # ── Fallback: naive seasonal (hour-of-day means) ─────────────
        self._train_naive(price_series)
        logger.warning(
            "Using naive seasonal fallback model (no ML library available)",
            market=self.market_str,
        )

    def _train_nbeats(
        self,
        price_series: "pd.Series",
        weather_features: "pd.DataFrame | None",
    ) -> None:
        """Fit Darts NBEATSModel."""
        ts = _DartsTimeSeries.from_series(price_series)
        model = _NBEATSModel(
            input_chunk_length=self._INPUT_CHUNK,
            output_chunk_length=self._OUTPUT_CHUNK,
            n_epochs=self._N_EPOCHS,
            random_state=self.seed,
        )
        if weather_features is not None and _DARTS_AVAILABLE:
            try:
                cov_ts = _DartsTimeSeries.from_dataframe(weather_features)
                model.fit(ts, past_covariates=cov_ts)
            except Exception:
                model.fit(ts)
        else:
            model.fit(ts)
        self._model = model
        self._model_name = "N-BEATS"
        self._fitted = True

    def _train_sarima(self, price_series: "pd.Series") -> None:
        """Fit SARIMA(1,1,1)(1,1,1,24)."""
        model = _SARIMAX(
            price_series,
            order=(1, 1, 1),
            seasonal_order=(1, 1, 1, 24),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        self._model = model.fit(disp=False)
        self._model_name = "SARIMA"
        self._fitted = True

    def _train_naive(self, price_series: "pd.Series") -> None:
        """Compute hour-of-day means as a naive seasonal baseline."""
        if not _PANDAS_AVAILABLE or not _NUMPY_AVAILABLE:
            # Ultra-minimal fallback — just store the mean
            self._model = {"mean": 55.0, "std": 20.0}
            self._model_name = "naive_constant"
            self._fitted = True
            return

        hour_means = price_series.groupby(price_series.index.hour).mean()
        hour_stds = price_series.groupby(price_series.index.hour).std().fillna(0.0)
        self._model = {"hour_means": hour_means, "hour_stds": hour_stds}
        self._model_name = "naive_seasonal"
        self._fitted = True

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        n_hours: int = 24,
        weather_features: "pd.DataFrame | None" = None,
    ) -> PriceForecast:
        """
        Produce an hourly price forecast.

        Parameters
        ----------
        n_hours : int
            Forecast horizon in hours.
        weather_features : pd.DataFrame | None
            Optional weather covariates for Darts models.

        Returns
        -------
        PriceForecast
        """
        if not self._fitted:
            raise RuntimeError("Model must be trained before calling predict(). Call train() first.")

        if self._model_name == "N-BEATS":
            raw_prices = self._predict_nbeats(n_hours, weather_features)
        elif self._model_name == "SARIMA":
            raw_prices = self._predict_sarima(n_hours)
        else:
            raw_prices = self._predict_naive(n_hours)

        # Physical clamping
        if _NUMPY_AVAILABLE:
            prices = list(map(float, _np.clip(raw_prices, -500.0, 3000.0)))
        else:
            prices = [float(max(-500.0, min(3000.0, p))) for p in raw_prices]

        # Build forecast timestamps — start from last known time + 1h
        if self._training_series is not None and _PANDAS_AVAILABLE:
            last_ts = self._training_series.index[-1]
            forecast_start = last_ts + _pd.Timedelta(hours=1)
            intervals = list(
                _pd.date_range(start=forecast_start, periods=n_hours, freq="h")
                .to_pydatetime()
            )
        else:
            now = datetime.now(tz=timezone.utc)
            intervals = [now + timedelta(hours=i + 1) for i in range(n_hours)]

        # Ensure timestamps are UTC-aware
        intervals = [
            ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
            for ts in intervals
        ]

        neg_flags = [p < 0.0 for p in prices]

        try:
            market_id = MarketID(self.market_str)
        except ValueError:
            market_id = MarketID.EPEX_DE
            logger.warning("Unknown market_id; defaulting to EPEX_DE", market=self.market_str)

        return PriceForecast(
            run_id=self.run_id,
            market=market_id,
            forecast_generated_at=datetime.now(tz=timezone.utc),
            forecast_intervals=intervals,
            forecast_prices_eur_mwh=prices,
            negative_pricing_flags=neg_flags,
            model_name=self._model_name,
        )

    def _predict_nbeats(
        self, n_hours: int, weather_features: "pd.DataFrame | None"
    ) -> list[float]:
        """Generate predictions from fitted N-BEATS model."""
        pred_ts = self._model.predict(n=n_hours)
        return [float(v) for v in pred_ts.values().flatten()]

    def _predict_sarima(self, n_hours: int) -> list[float]:
        """Generate predictions from fitted SARIMA model."""
        forecast = self._model.forecast(steps=n_hours)
        return [float(v) for v in forecast]

    def _predict_naive(self, n_hours: int) -> list[float]:
        """Generate predictions from naive seasonal model."""
        if not _PANDAS_AVAILABLE or not _NUMPY_AVAILABLE:
            mean_val = self._model.get("mean", 55.0)
            return [float(mean_val) for _ in range(n_hours)]

        # Start from 1 h after last training observation
        last_ts = self._training_series.index[-1]
        forecast_start = last_ts + _pd.Timedelta(hours=1)
        future_index = _pd.date_range(start=forecast_start, periods=n_hours, freq="h")

        hour_means = self._model["hour_means"]
        prices = [float(hour_means.get(ts.hour, 55.0)) for ts in future_index]
        return prices

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_epex_csv(self, path: Path) -> "pd.Series":
        """
        Load EPEX SPOT CSV format and return a price Series.

        Expected columns: ``datetime``, ``price_eur_mwh``.
        The datetime column is parsed as UTC.

        Parameters
        ----------
        path : Path
            Path to the EPEX SPOT CSV file.

        Returns
        -------
        pd.Series
            Hourly price series with UTC DatetimeIndex.
        """
        if not _PANDAS_AVAILABLE:
            raise ImportError("pandas is required to load EPEX CSV files")

        df = _pd.read_csv(path, parse_dates=["datetime"])
        if "datetime" not in df.columns or "price_eur_mwh" not in df.columns:
            raise ValueError(
                "CSV must contain columns 'datetime' and 'price_eur_mwh'."
                f" Got: {list(df.columns)}"
            )
        df = df.sort_values("datetime").set_index("datetime")
        series = df["price_eur_mwh"].copy()

        # Ensure UTC-aware index
        if series.index.tzinfo is None:
            series.index = series.index.tz_localize("UTC")
        else:
            series.index = series.index.tz_convert("UTC")

        logger.info(
            "Loaded EPEX CSV",
            path=str(path),
            n_rows=len(series),
            start=str(series.index[0]),
            end=str(series.index[-1]),
        )
        return series

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, test_series: "pd.Series") -> float:
        """
        Compute Mean Absolute Error on a held-out test series.

        Generates a forecast of the same length as ``test_series`` and
        computes point-wise MAE.

        Parameters
        ----------
        test_series : pd.Series
            Ground-truth hourly prices.

        Returns
        -------
        float
            MAE in €/MWh.
        """
        if not self._fitted:
            raise RuntimeError("Model must be trained before evaluate().")

        n = len(test_series)
        forecast = self.predict(n_hours=n)
        pred_prices = forecast.forecast_prices_eur_mwh
        true_prices = list(test_series.values)

        mae = sum(abs(p - t) for p, t in zip(pred_prices, true_prices)) / n
        logger.info(
            "Model evaluation",
            mae=round(mae, 4),
            n_samples=n,
            model_name=self._model_name,
            market=self.market_str,
        )
        return float(mae)
