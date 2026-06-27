"""
Spread-based mean-reversion signals for the SPY-TLT allocation framework.

This module constructs relative-value signals from the return spread between
SPY and TLT. The spread is standardized using a rolling z-score, and the
portfolio shifts when the spread becomes unusually wide in either direction.

The output is a normalized two-asset positioning series that can be used
directly in the strategy backtest.
"""
# pylint: disable=import-error

from typing import Tuple

import numpy as np
import pandas as pd

from config import SPREAD_THRESHOLD, SPREAD_WINDOW


def generate_spread_signals(
    returns: pd.DataFrame,
    window: int = SPREAD_WINDOW,
    threshold: float = SPREAD_THRESHOLD,
) -> pd.DataFrame:
    """
    Generate SPY/TLT spread mean-reversion signals from return data.

    The signal is based on the close-to-close return spread between SPY and TLT.
    A rolling z-score is used to identify unusually large relative moves,
    after which the portfolio is tilted toward a mean-reversion view.

    Args:
        returns: DataFrame containing 'SPY' and 'TLT' return columns.
        window: Rolling window used to compute the spread mean and standard
            deviation.
        threshold: Absolute z-score threshold required to trigger a signal.

    Returns:
        DataFrame with normalized position columns:
            - 'SPY_pos'
            - 'TLT_pos'

    Raises:
        KeyError: If required columns are missing.
        ValueError: If parameters are invalid or the dataset is too short.

    Notes:
        - Execution lagging is handled centrally by the backtest.
        - Output weights are normalized to unit gross exposure.
        - The implementation is fully vectorized.
    """
    _validate_inputs(returns, window, threshold)

    z_score = _compute_spread_z_score(returns, window)
    spy_pos, tlt_pos = _build_base_positions(z_score, threshold)
    spy_pos, tlt_pos = _normalize_positions(spy_pos, tlt_pos)

    signals = pd.DataFrame(
        {"SPY_pos": spy_pos, "TLT_pos": tlt_pos},
        index=returns.index,
    )

    return signals


def _validate_inputs(
    returns: pd.DataFrame,
    window: int,
    threshold: float,
) -> None:
    """
    Validate inputs for spread signal generation.

    Confirms required columns, checks parameter bounds, and ensures that
    enough observations are available for the rolling calculations.
    """
    required_cols = {"SPY", "TLT"}
    missing = required_cols - set(returns.columns)
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    if threshold <= 0:
        raise ValueError(f"threshold must be > 0, got {threshold}")
    if len(returns) < window + 1:
        raise ValueError(
            f"Insufficient data: need >= {window + 1} rows, got {len(returns)}"
        )


def _compute_spread_z_score(
    returns: pd.DataFrame,
    window: int,
) -> pd.Series:
    """
    Compute the rolling z-score of the SPY-TLT return spread.

    Args:
        returns: Return DataFrame containing 'SPY' and 'TLT'.
        window: Rolling window used for normalization.

    Returns:
        Series of spread z-scores.
    """
    spread = returns["SPY"] - returns["TLT"]

    spread_history = spread.shift(1)
    rolling_mean = spread_history.rolling(window, min_periods=window).mean()
    rolling_std = spread_history.rolling(window, min_periods=window).std()

    z_score = (spread - rolling_mean) / rolling_std.replace(0, np.nan)
    return z_score


def _build_base_positions(
    z_score: pd.Series,
    threshold: float,
) -> Tuple[pd.Series, pd.Series]:
    """
    Convert z-scores into raw SPY and TLT position series.

    Args:
        z_score: Spread z-score series.
        threshold: Absolute threshold required to change positioning.

    Returns:
        Tuple of raw SPY and TLT position series before normalization.
    """
    index = z_score.index
    spy_pos = pd.Series(1.0, index=index, dtype=np.float64)
    tlt_pos = pd.Series(0.0, index=index, dtype=np.float64)

    short_spy_mask = z_score > threshold
    long_spy_mask = z_score < -threshold

    spy_pos[short_spy_mask] = 0.0
    tlt_pos[short_spy_mask] = 1.0

    spy_pos[long_spy_mask] = 1.0
    tlt_pos[long_spy_mask] = -0.5

    return spy_pos, tlt_pos


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
    gross_exposure = gross_exposure.replace(0, 1.0)

    return spy_pos / gross_exposure, tlt_pos / gross_exposure
