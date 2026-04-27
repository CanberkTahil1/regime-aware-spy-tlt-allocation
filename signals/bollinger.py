"""
Bollinger-band signal generation for the SPY-TLT allocation framework.

This module builds relative-value signals from the SPY/TLT price ratio.
When the ratio moves far from its rolling mean, the strategy shifts
exposure toward a mean-reversion view.

Main output:
    - SPY_pos
    - TLT_pos

The implementation is fully vectorized and produces normalized portfolio
weights suitable for backtesting and downstream portfolio construction.
"""
# pylint: disable=import-error

from typing import Tuple

import numpy as np
import pandas as pd

from config import BOLLINGER_NUM_STD, BOLLINGER_WINDOW


def generate_bollinger_signals(
    prices: pd.DataFrame,
    window: int = BOLLINGER_WINDOW,
    num_std: float = BOLLINGER_NUM_STD,
) -> pd.DataFrame:
    """
    Generate normalized SPY/TLT allocation signals using Bollinger bands.

    The signal is constructed from the SPY/TLT price ratio. A rolling mean
    and rolling standard deviation define upper and lower bands around the
    ratio. When the ratio moves outside those bands, the portfolio shifts
    toward a mean-reversion stance.

    Args:
        prices: DataFrame containing 'SPY' and 'TLT' price columns.
        window: Rolling window used to compute the ratio mean and standard
            deviation.
        num_std: Number of rolling standard deviations used to define the
            Bollinger bands.

    Returns:
        DataFrame indexed like `prices` with columns:
            - 'SPY_pos': SPY portfolio weight
            - 'TLT_pos': TLT portfolio weight

        Positions are normalized to unit gross exposure.

    Raises:
        KeyError: If required columns are missing.
        ValueError: If parameters are invalid or the input is too short.

    Notes:
        - Uses the SPY/TLT ratio rather than returns.
        - Early rows are NaN until the rolling window is available.
        - Output is suitable for direct use in portfolio backtests.
    """
    _validate_inputs(prices, window, num_std)

    # Compute ratio once, reuse in all operations
    ratio = prices["SPY"] / prices["TLT"]
    ratio = ratio.shift(1)

    # Compute rolling statistics with explicit min_periods
    rolling_mean = ratio.rolling(window, min_periods=window).mean()
    rolling_std = ratio.rolling(window, min_periods=window).std()

    # Calculate Bollinger bands
    upper_band = rolling_mean + num_std * rolling_std
    lower_band = rolling_mean - num_std * rolling_std

    # Build base positions with direct initialization
    index = prices.index
    spy_pos = pd.Series(1.0, index=index, dtype=np.float64)
    tlt_pos = pd.Series(0.0, index=index, dtype=np.float64)

    # Vectorized signal generation (no .loc[] loops)
    short_spy_mask = ratio > upper_band
    long_spy_mask = ratio < lower_band

    spy_pos[short_spy_mask] = 0
    tlt_pos[short_spy_mask] = 1

    spy_pos[long_spy_mask] = 1.0
    tlt_pos[long_spy_mask] = -0.5

    # Normalize to unit gross exposure
    spy_pos, tlt_pos = _normalize_positions(spy_pos, tlt_pos)

    # Assemble output
    signals = pd.DataFrame(
        {"SPY_pos": spy_pos, "TLT_pos": tlt_pos},
        index=prices.index,
    )

    return signals


def _validate_inputs(
    prices: pd.DataFrame,
    window: int,
    num_std: float,
) -> None:
    """
    Validate inputs for Bollinger signal generation.

    Checks required columns, parameter bounds, and minimum sample length.
    Raises a descriptive exception on invalid input.
    """
    required_cols = {"SPY", "TLT"}
    missing = required_cols - set(prices.columns)
    if missing:
        raise KeyError(
            f"Missing required price columns: {missing}. "
            f"Available columns: {set(prices.columns)}"
        )

    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")

    if num_std <= 0:
        raise ValueError(f"num_std must be > 0, got {num_std}")

    if len(prices) < window + 1:
        raise ValueError(
            f"Insufficient data: need >= {window + 1} rows for rolling window + lag, "
            f"got {len(prices)}"
        )


def _normalize_positions(
    spy_pos: pd.Series,
    tlt_pos: pd.Series,
) -> Tuple[pd.Series, pd.Series]:
    """
    Normalize SPY and TLT weights to unit gross exposure.

    Args:
        spy_pos: Raw SPY position series.
        tlt_pos: Raw TLT position series.

    Returns:
        Tuple of normalized SPY and TLT position series.
    """
    gross_exposure = spy_pos.abs() + tlt_pos.abs()
    gross_exposure = gross_exposure.replace(0, 1.0)  # Prevent division by zero

    spy_normalized = spy_pos / gross_exposure
    tlt_normalized = tlt_pos / gross_exposure

    return spy_normalized, tlt_normalized
