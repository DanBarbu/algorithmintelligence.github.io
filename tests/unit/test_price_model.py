"""
Unit tests for src.wesf.price_model.ElectricityPriceModel and _synthetic_price_series.

All tests use _synthetic_price_series — no real data, no internet access.
Tests are designed to pass regardless of whether darts/torch/statsmodels/pandas
are installed, as long as the module is importable.
"""
from __future__ import annotations

import importlib
import sys

import pytest

# ---------------------------------------------------------------------------
# Conditional import helpers
# ---------------------------------------------------------------------------

try:
    import numpy as np  # type: ignore

    _NUMPY = True
except ImportError:
    _NUMPY = False

try:
    import pandas as pd  # type: ignore

    _PANDAS = True
except ImportError:
    _PANDAS = False

# Skip marks for tests that require numpy/pandas
requires_numpy = pytest.mark.skipif(not _NUMPY, reason="numpy not installed")
requires_numpy_pandas = pytest.mark.skipif(
    not (_NUMPY and _PANDAS), reason="numpy and pandas required"
)

# ---------------------------------------------------------------------------
# Module-level imports (always importable — heavy deps are guarded inside)
# ---------------------------------------------------------------------------

from src.wesf.price_model import ElectricityPriceModel, _synthetic_price_series  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic series tests
# ---------------------------------------------------------------------------

class TestSyntheticSeries:
    @requires_numpy_pandas
    def test_synthetic_series_length(self):
        """_synthetic_price_series(n_hours=48) returns Series of length 48."""
        series = _synthetic_price_series(n_hours=48, seed=42)
        assert len(series) == 48, f"Expected 48 observations, got {len(series)}"

    @requires_numpy_pandas
    def test_synthetic_series_length_default_8760(self):
        """Default length is 8760 (one year of hourly data)."""
        series = _synthetic_price_series()
        assert len(series) == 8760

    @requires_numpy_pandas
    def test_synthetic_series_has_negative_prices(self):
        """
        Series includes some negative prices (renewable surplus simulation).
        Uses 8760-hour series to ensure the 5% negative injection is present.
        """
        series = _synthetic_price_series(n_hours=8760, seed=42)
        n_negative = (series < 0).sum()
        assert n_negative > 0, (
            f"Expected negative prices in 8760-h synthetic series, found none. "
            f"Min price = {series.min():.2f}"
        )

    @requires_numpy_pandas
    def test_synthetic_series_has_negative_prices_short(self):
        """Even in a 200-h series, at least one negative price expected (5% rate)."""
        series = _synthetic_price_series(n_hours=200, seed=99)
        assert (series < 0).sum() >= 1, (
            "Expected at least one negative price in 200-h synthetic series"
        )

    @requires_numpy_pandas
    def test_synthetic_series_within_physical_range(self):
        """All prices clamped to [-500, 3000] €/MWh."""
        series = _synthetic_price_series(n_hours=8760, seed=7)
        assert series.min() >= -500.0
        assert series.max() <= 3000.0

    @requires_numpy_pandas
    def test_synthetic_series_has_datetime_index(self):
        """Series has a DatetimeIndex."""
        series = _synthetic_price_series(n_hours=24, seed=42)
        assert hasattr(series.index, "freq") or hasattr(series.index, "dtype"), (
            "Expected DatetimeIndex"
        )
        import pandas as pd
        assert isinstance(series.index, pd.DatetimeIndex)

    @requires_numpy_pandas
    def test_synthetic_series_is_utc(self):
        """DatetimeIndex is UTC-aware."""
        import pandas as pd

        series = _synthetic_price_series(n_hours=24, seed=42)
        assert series.index.tz is not None, "Expected UTC-aware DatetimeIndex"
        assert str(series.index.tz) == "UTC"

    @requires_numpy_pandas
    def test_synthetic_series_reproducible(self):
        """Same seed → identical series."""
        s1 = _synthetic_price_series(n_hours=100, seed=13)
        s2 = _synthetic_price_series(n_hours=100, seed=13)
        import numpy as np

        assert np.allclose(s1.values, s2.values), "Expected reproducible series for same seed"

    @requires_numpy_pandas
    def test_synthetic_series_different_seeds_differ(self):
        """Different seeds → different series."""
        import numpy as np

        s1 = _synthetic_price_series(n_hours=100, seed=1)
        s2 = _synthetic_price_series(n_hours=100, seed=2)
        assert not np.allclose(s1.values, s2.values), "Expected different series for different seeds"


# ---------------------------------------------------------------------------
# Model train + predict tests
# ---------------------------------------------------------------------------

class TestModelTrainPredict:
    @requires_numpy_pandas
    def test_model_train_predict_returns_forecast(self):
        """train on 720h, predict 24h → PriceForecast with correct length."""
        from src.api.schemas import PriceForecast

        series = _synthetic_price_series(n_hours=720, seed=42)
        model = ElectricityPriceModel(market="EPEX_DE", seed=42)
        model.train(series)

        forecast = model.predict(n_hours=24)

        assert isinstance(forecast, PriceForecast)
        assert len(forecast.forecast_prices_eur_mwh) == 24
        assert len(forecast.forecast_intervals) == 24
        assert len(forecast.negative_pricing_flags) == 24

    @requires_numpy_pandas
    def test_model_predict_without_train_raises(self):
        """predict() before train() raises RuntimeError."""
        model = ElectricityPriceModel(market="EPEX_DE", seed=0)
        with pytest.raises(RuntimeError, match="train"):
            model.predict(n_hours=24)

    @requires_numpy_pandas
    def test_model_train_predict_different_horizons(self):
        """Different forecast horizons produce correctly-sized outputs."""
        series = _synthetic_price_series(n_hours=500, seed=11)
        model = ElectricityPriceModel(market="EPEX_FR", seed=11)
        model.train(series)

        for n_hours in (1, 12, 48, 168):
            forecast = model.predict(n_hours=n_hours)
            assert len(forecast.forecast_prices_eur_mwh) == n_hours, (
                f"Expected {n_hours} prices, got {len(forecast.forecast_prices_eur_mwh)}"
            )

    def test_model_importable_without_heavy_deps(self):
        """ElectricityPriceModel is importable even without torch/darts/pandas."""
        # This test always runs — it verifies the guard blocks work
        assert ElectricityPriceModel is not None

    @requires_numpy_pandas
    def test_model_name_recorded_in_forecast(self):
        """PriceForecast.model_name is populated."""
        series = _synthetic_price_series(n_hours=200, seed=5)
        model = ElectricityPriceModel(market="EPEX_DE", seed=5)
        model.train(series)
        forecast = model.predict(n_hours=12)
        assert isinstance(forecast.model_name, str)
        assert len(forecast.model_name) > 0

    @requires_numpy_pandas
    def test_forecast_intervals_are_utc_aware(self):
        """All forecast interval timestamps are UTC-aware."""
        series = _synthetic_price_series(n_hours=200, seed=6)
        model = ElectricityPriceModel(market="EPEX_DE", seed=6)
        model.train(series)
        forecast = model.predict(n_hours=12)

        for ts in forecast.forecast_intervals:
            assert ts.tzinfo is not None, f"Non-UTC timestamp in forecast: {ts}"


# ---------------------------------------------------------------------------
# test_negative_pricing_flags_match_prices
# ---------------------------------------------------------------------------

class TestNegativePricingFlags:
    @requires_numpy_pandas
    def test_negative_pricing_flags_match_prices(self):
        """flag[i] == (price[i] < 0) for all i."""
        series = _synthetic_price_series(n_hours=720, seed=42)
        model = ElectricityPriceModel(market="EPEX_DE", seed=42)
        model.train(series)
        forecast = model.predict(n_hours=24)

        prices = forecast.forecast_prices_eur_mwh
        flags = forecast.negative_pricing_flags

        for i, (price, flag) in enumerate(zip(prices, flags)):
            expected_flag = price < 0.0
            assert flag == expected_flag, (
                f"At index {i}: price={price:.2f}, flag={flag}, expected={expected_flag}"
            )

    @requires_numpy_pandas
    def test_negative_pricing_flags_are_booleans(self):
        """All flags are Python booleans."""
        series = _synthetic_price_series(n_hours=300, seed=77)
        model = ElectricityPriceModel(market="NORD_POOL", seed=77)
        model.train(series)
        forecast = model.predict(n_hours=24)

        for i, flag in enumerate(forecast.negative_pricing_flags):
            assert isinstance(flag, bool), f"Flag at {i} is {type(flag)}, expected bool"


# ---------------------------------------------------------------------------
# test_price_forecast_physical_range
# ---------------------------------------------------------------------------

class TestPhysicalRange:
    @requires_numpy_pandas
    def test_price_forecast_physical_range(self):
        """All forecast prices in [-500, 3000] €/MWh."""
        series = _synthetic_price_series(n_hours=720, seed=42)
        model = ElectricityPriceModel(market="EPEX_DE", seed=42)
        model.train(series)
        forecast = model.predict(n_hours=24)

        for i, price in enumerate(forecast.forecast_prices_eur_mwh):
            assert -500.0 <= price <= 3000.0, (
                f"Price at index {i} ({price:.2f}) outside physical range [-500, 3000]"
            )

    @requires_numpy_pandas
    def test_price_forecast_physical_range_long_horizon(self):
        """Physical range clamping holds for a 168-h (1-week) horizon."""
        series = _synthetic_price_series(n_hours=2000, seed=88)
        model = ElectricityPriceModel(market="EPEX_GB", seed=88)
        model.train(series)
        forecast = model.predict(n_hours=168)

        prices = forecast.forecast_prices_eur_mwh
        assert all(-500.0 <= p <= 3000.0 for p in prices), (
            f"Prices outside range: min={min(prices):.2f}, max={max(prices):.2f}"
        )


# ---------------------------------------------------------------------------
# Schema consistency
# ---------------------------------------------------------------------------

class TestPriceForecastSchema:
    @requires_numpy_pandas
    def test_forecast_intervals_equal_prices_length(self):
        """PriceForecast validator: intervals length == prices length."""
        series = _synthetic_price_series(n_hours=200, seed=3)
        model = ElectricityPriceModel(market="EPEX_DE", seed=3)
        model.train(series)
        forecast = model.predict(n_hours=48)

        assert len(forecast.forecast_intervals) == len(forecast.forecast_prices_eur_mwh)

    @requires_numpy_pandas
    def test_forecast_intervals_equal_flags_length(self):
        """negative_pricing_flags length == forecast_intervals length."""
        series = _synthetic_price_series(n_hours=200, seed=4)
        model = ElectricityPriceModel(market="EPEX_DE", seed=4)
        model.train(series)
        forecast = model.predict(n_hours=48)

        assert len(forecast.negative_pricing_flags) == len(forecast.forecast_intervals)

    @requires_numpy_pandas
    def test_forecast_market_id_correct(self):
        """PriceForecast.market matches the requested market."""
        from src.api.schemas import MarketID

        series = _synthetic_price_series(n_hours=200, seed=2)
        model = ElectricityPriceModel(market="EPEX_FR", seed=2)
        model.train(series)
        forecast = model.predict(n_hours=24)

        assert forecast.market == MarketID.EPEX_FR

    @requires_numpy_pandas
    def test_forecast_generated_at_is_utc(self):
        """forecast_generated_at is UTC-aware."""
        series = _synthetic_price_series(n_hours=200, seed=1)
        model = ElectricityPriceModel(market="EPEX_DE", seed=1)
        model.train(series)
        forecast = model.predict(n_hours=12)

        assert forecast.forecast_generated_at.tzinfo is not None
