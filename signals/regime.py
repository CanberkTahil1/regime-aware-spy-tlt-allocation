"""
Regime classification for the SPY-TLT allocation framework.

This module identifies market states from volatility and trend information.
Volatility can be estimated either from VIX or from realized SPY volatility,
while trend is based on SPY momentum.

The resulting regime labels are used to switch between different allocation
rules in the broader strategy.
"""
# pylint: disable=import-error

import pandas as pd

from config import (
    VIX_WINDOW,
    MOMENTUM_WINDOW,
    REALIZED_VOL_WINDOW,
    REALIZED_VOL_AVG_WINDOW,
)


def compute_regime(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    use_vix: bool = True,
    vix_window: int = VIX_WINDOW,
    momentum_window: int = MOMENTUM_WINDOW,
) -> pd.DataFrame:
    """
    Compute volatility and trend regimes for the allocation model.

    The regime state is represented by two Boolean series:
        - low_vol: whether volatility is below its reference level
        - trend: whether SPY momentum is positive

    Args:
        prices: DataFrame containing 'SPY' and, when `use_vix=True`, '^VIX'.
        returns: DataFrame containing 'SPY' returns.
        use_vix: If True, classify volatility using VIX relative to its
            rolling mean. Otherwise use realized volatility.
        vix_window: Rolling window used in volatility classification.
        momentum_window: Window used to compute SPY momentum.

    Returns:
        DataFrame with:
            - 'low_vol'
            - 'trend'

        The index matches `prices`.

    Raises:
        KeyError: If required inputs are missing.
        ValueError: If parameters are invalid or the dataset is too short.

    Notes:
        These regime features are intentionally simple and interpretable so
        they can be used cleanly in downstream portfolio rules.
    """
    _validate_inputs(prices, returns, use_vix, vix_window, momentum_window)

    # Compute volatility regime (low_vol is True when volatility is low)
    low_vol = _compute_volatility_regime(
        prices,
        returns,
        use_vix=use_vix,
        vix_window=vix_window,
    )

    # Compute trend regime (positive_trend is True when momentum > 0)
    positive_trend = _compute_trend_regime(
        prices["SPY"],
        momentum_window=momentum_window,
    )

    # Assemble regimes DataFrame
    regimes = pd.DataFrame(
        {
            "low_vol": low_vol.shift(1).eq(True),
            "trend": positive_trend.shift(1).eq(True),
        },
        index=prices.index,
    )

    return regimes


def _validate_inputs(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    use_vix: bool,
    vix_window: int,
    momentum_window: int,
) -> None:
    """
    Validate inputs for regime computation.

    Confirms required columns exist and that the dataset is long enough for
    the requested rolling calculations.
    """
    # Check required price columns
    if "SPY" not in prices.columns:
        raise KeyError(f"prices must contain 'SPY' column, got {set(prices.columns)}")

    if use_vix and "^VIX" not in prices.columns:
        raise KeyError(
            f"use_vix=True but '^VIX' not in prices columns. "
            f"Available: {set(prices.columns)}"
        )

    if not use_vix and "SPY" not in returns.columns:
        raise KeyError("use_vix=False but 'SPY' not in returns columns")

    # Check parameter ranges
    if vix_window < 2:
        raise ValueError(f"vix_window must be >= 2, got {vix_window}")

    if momentum_window < 2:
        raise ValueError(f"momentum_window must be >= 2, got {momentum_window}")

    # Check data length
    min_length = max(vix_window, momentum_window) + 1
    if len(prices) < min_length:
        raise ValueError(
            f"Insufficient data: need >= {min_length} rows, got {len(prices)}"
        )


def _compute_volatility_regime(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    use_vix: bool,
    vix_window: int,
) -> pd.Series:
    """
    Compute the volatility regime series.

    Args:
        prices: Price data containing SPY and optionally VIX.
        returns: Return data containing SPY.
        use_vix: Whether to use VIX-based or realized-volatility-based logic.
        vix_window: Rolling window used in the volatility benchmark.

    Returns:
        Boolean Series where True indicates a low-volatility regime.
    """
    if use_vix:
        vix = prices["^VIX"]
        vix_rolling_mean = vix.rolling(vix_window, min_periods=vix_window).mean()
        low_volatility = vix < vix_rolling_mean
    else:
        # Realized volatility approach (parameter-invariant, can be pre-computed)
        realized_volatility = returns["SPY"].rolling(
            REALIZED_VOL_WINDOW, min_periods=REALIZED_VOL_WINDOW).std()
        realized_volatility_mean = realized_volatility.rolling(
            REALIZED_VOL_AVG_WINDOW, min_periods=REALIZED_VOL_AVG_WINDOW).mean()
        low_volatility = realized_volatility < realized_volatility_mean

    return low_volatility.astype(bool)


def _compute_trend_regime(
    spy_prices: pd.Series,
    momentum_window: int,
) -> pd.Series:
    """
    Compute the trend regime from SPY momentum.

    Args:
        spy_prices: SPY price series.
        momentum_window: Lookback window used for momentum.

    Returns:
        Boolean Series where True indicates positive momentum.
    """
    momentum = spy_prices.pct_change(momentum_window)
    positive_trend = momentum > 0

    return positive_trend.astype(bool)
