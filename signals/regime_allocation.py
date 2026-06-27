"""
Master signal construction for the regime-aware SPY-TLT strategy.

This module combines regime classification, relative-value signals, and
crash-sensitive overlays into a single portfolio allocation process.

The design separates three layers:
    1. Regime detection
    2. Regime-conditional base positioning
    3. Crash overlay and final normalization

The output is a normalized two-asset allocation series for SPY and TLT.
"""
# pylint: disable=import-error

from typing import Dict, Optional

import numpy as np
import pandas as pd

from utils import apply_conditional_normalization
from config import CrashParams, SignalParams, VIX_WINDOW

from signals.bollinger import generate_bollinger_signals
from signals.regime import compute_regime
from signals.spread import generate_spread_signals


def generate_regime_allocation_signals(
    returns: pd.DataFrame,
    prices: pd.DataFrame,
    signal_params: SignalParams,
    crash_params: CrashParams,
    cached_features: Optional[Dict] = None,
) -> pd.DataFrame:
    """
    Generate regime-aware SPY/TLT portfolio signals with a crash overlay.

    The function combines regime classification with regime-conditional base
    signals and a crash-sensitive SPY de-risking overlay.

    Args:
        returns: DataFrame of asset returns.
        prices: DataFrame of asset prices. Must include 'SPY', 'TLT', and '^VIX'.
        signal_params: Parameter set for regime classification and base signals.
        crash_params: Parameter set for crash detection and overlay strength.
        cached_features: Optional dictionary of precomputed rolling features.

    Returns:
        DataFrame with normalized portfolio weights:
            - 'SPY_pos'
            - 'TLT_pos'

    Raises:
        KeyError: If required columns are missing.
        ValueError: If rolling-window parameters are invalid or input is too short.
    """
    _validate_inputs(returns, prices, signal_params, crash_params)

    low_vol, trend = _compute_regime_states(prices, returns, signal_params)
    spread, bollinger = _generate_base_signal_frames(returns, prices, signal_params)
    spy_pos, tlt_pos = _build_regime_positions(prices.index, low_vol, trend, spread, bollinger)

    crash_intensity = _compute_crash_intensity(
        prices=prices,
        returns=returns,
        crash_params=crash_params,
        cached_features=cached_features,
    ).fillna(0.0)
    crash_active = crash_intensity > 0.05

    spy_pos = _apply_crash_overlay(spy_pos, crash_intensity, crash_active)
    signals = pd.DataFrame({"SPY_pos": spy_pos, "TLT_pos": tlt_pos}, index=prices.index)

    return apply_conditional_normalization(signals, crash_active)


def _validate_inputs(
    returns: pd.DataFrame,
    prices: pd.DataFrame,
    signal_params: SignalParams,
    crash_params: CrashParams,
) -> None:
    """
    Validate inputs for master signal generation.

    Args:
        returns: Return data used by the strategy.
        prices: Price data used by the strategy.
        signal_params: Base-signal parameter set.
        crash_params: Crash parameter set.

    Raises:
        KeyError: If required columns are missing.
        ValueError: If parameters are invalid or the dataset is too short.
    """
    required_price_cols = {"SPY", "TLT", "^VIX"}
    missing_price = required_price_cols - set(prices.columns)
    if missing_price:
        raise KeyError(f"prices missing required columns: {missing_price}")

    if "SPY" not in returns.columns:
        raise KeyError("returns must contain 'SPY' column")

    if signal_params.z_window < 2:
        raise ValueError(f"z_window must be >= 2, got {signal_params.z_window}")

    if crash_params.slow_window < 2:
        raise ValueError(
            f"slow_window must be >= 2, got {crash_params.slow_window}"
        )

    if crash_params.dd_window < 2:
        raise ValueError(f"dd_window must be >= 2, got {crash_params.dd_window}")

    min_required = max(
        signal_params.z_window,
        crash_params.slow_window,
        crash_params.dd_window,
    ) + 1
    if len(prices) < min_required:
        raise ValueError("Insufficient data for rolling windows")


def _compute_regime_states(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    signal_params: SignalParams,
) -> tuple[pd.Series, pd.Series]:
    """
    Compute low-volatility and trend regime states.

    Args:
        prices: Price data.
        returns: Return data.
        signal_params: Base-signal parameter set.

    Returns:
        Tuple of (low_vol, trend) Boolean series.
    """
    regimes = compute_regime(
        prices=prices,
        returns=returns,
        use_vix=signal_params.use_vix,
    )
    return regimes["low_vol"], regimes["trend"]


def _generate_base_signal_frames(
    returns: pd.DataFrame,
    prices: pd.DataFrame,
    signal_params: SignalParams,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate the spread and Bollinger base signal frames.

    Args:
        returns: Return data.
        prices: Price data.
        signal_params: Base-signal parameter set.

    Returns:
        Tuple of (spread_signals, bollinger_signals).
    """
    spread = generate_spread_signals(
        returns=returns,
        window=signal_params.z_window,
        threshold=signal_params.threshold,
    )
    bollinger = generate_bollinger_signals(
        prices=prices,
        window=signal_params.z_window,
        num_std=2,
    )
    return spread, bollinger


def _build_regime_positions(
    index: pd.Index,
    low_vol: pd.Series,
    trend: pd.Series,
    spread: pd.DataFrame,
    bollinger: pd.DataFrame,
) -> tuple[pd.Series, pd.Series]:
    """
    Build base SPY/TLT positions from regime-conditional signal selection.

    Args:
        index: Output index.
        low_vol: Low-volatility regime indicator.
        trend: Trend regime indicator.
        spread: Spread signal DataFrame.
        bollinger: Bollinger signal DataFrame.

    Returns:
        Tuple of (spy_pos, tlt_pos) before crash overlay.
    """
    spy_pos = pd.Series(0.0, index=index, dtype=np.float64)
    tlt_pos = pd.Series(0.0, index=index, dtype=np.float64)

    low_vol_uptrend = low_vol & trend
    low_vol_downtrend = low_vol & (~trend)
    high_vol = ~low_vol

    spy_pos[low_vol_uptrend] = 1.0

    spy_pos[low_vol_downtrend] = bollinger.loc[low_vol_downtrend, "SPY_pos"]
    tlt_pos[low_vol_downtrend] = bollinger.loc[low_vol_downtrend, "TLT_pos"]

    spy_pos[high_vol] = spread.loc[high_vol, "SPY_pos"]
    tlt_pos[high_vol] = spread.loc[high_vol, "TLT_pos"]

    return spy_pos, tlt_pos


def _apply_crash_overlay(
    spy_pos: pd.Series,
    crash_intensity: pd.Series,
    crash_active: pd.Series,
) -> pd.Series:
    """
    Apply the crash overlay to SPY positions and clip extreme exposure.

    Args:
        spy_pos: Base SPY position series.
        crash_intensity: Crash-intensity series.
        crash_active: Boolean indicator of active crash conditions.

    Returns:
        Adjusted SPY position series.
    """
    adjusted_spy = spy_pos + (-1.0 * (crash_intensity**1.5) * crash_active)
    return adjusted_spy.clip(-2.0, 1.5)


def _compute_crash_intensity(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    crash_params: CrashParams,
    cached_features: Optional[Dict] = None,
) -> pd.Series:
    """
    Compute the crash-intensity score used in the defensive overlay.

    Args:
        prices: Price data used for VIX and drawdown features.
        returns: Return data used for rolling loss features.
        crash_params: Crash parameter set.
        cached_features: Optional precomputed rolling features.

    Returns:
        Series of crash-intensity values indexed like `prices`.
    """
    vix_rolling_mean = _get_vix_rolling_mean(prices, cached_features)
    spy_rolling_max = _get_spy_rolling_max(prices, crash_params.dd_window, cached_features)

    vix_score = ((prices["^VIX"] / vix_rolling_mean) - 1).clip(0, 2)
    drawdown = prices["SPY"] / spy_rolling_max - 1
    dd_score = (-drawdown).clip(0, 0.2)

    base_crash = 0.6 * vix_score + 0.4 * dd_score
    slow_crash = _compute_slow_crash_flag(returns, drawdown, crash_params)

    return base_crash * (1 + crash_params.crash_weight * slow_crash.astype(float))


def _get_vix_rolling_mean(
    prices: pd.DataFrame,
    cached_features: Optional[Dict],
) -> pd.Series:
    """
    Return the rolling VIX mean from cache or compute it.

    Args:
        prices: Price data containing '^VIX'.
        cached_features: Optional precomputed feature dictionary.

    Returns:
        Rolling VIX mean series.
    """
    if cached_features and "vix_rolling_mean" in cached_features:
        return cached_features["vix_rolling_mean"]
    return prices["^VIX"].rolling(VIX_WINDOW, min_periods=VIX_WINDOW).mean()


def _get_spy_rolling_max(
    prices: pd.DataFrame,
    dd_window: int,
    cached_features: Optional[Dict],
) -> pd.Series:
    """
    Return the rolling SPY max from cache or compute it.

    Args:
        prices: Price data containing 'SPY'.
        dd_window: Drawdown window length.
        cached_features: Optional precomputed feature dictionary.

    Returns:
        Rolling maximum SPY price series.
    """
    if cached_features and "spy_rolling_max" in cached_features:
        return cached_features["spy_rolling_max"].get(
            dd_window,
            prices["SPY"].rolling(dd_window, min_periods=dd_window).max(),
        )
    return prices["SPY"].rolling(dd_window, min_periods=dd_window).max()


def _compute_slow_crash_flag(
    returns: pd.DataFrame,
    drawdown: pd.Series,
    crash_params: CrashParams,
) -> pd.Series:
    """
    Compute the slow-crash Boolean indicator.

    Args:
        returns: Return data containing 'SPY'.
        drawdown: SPY drawdown series.
        crash_params: Crash parameter set.

    Returns:
        Boolean series indicating slow-crash conditions.
    """
    short_window = crash_params.slow_window
    long_window = crash_params.slow_window * 3

    rolling_ret_short = returns["SPY"].rolling(
        short_window,
        min_periods=short_window,
    ).sum()
    rolling_ret_long = returns["SPY"].rolling(
        long_window,
        min_periods=long_window,
    ).sum()

    return (
        (rolling_ret_short < crash_params.slow_threshold)
        & (rolling_ret_long < 2 * crash_params.slow_threshold)
        & (drawdown < crash_params.dd_threshold)
    )
