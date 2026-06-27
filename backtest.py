"""
Backtesting and evaluation utilities for the regime-aware SPY-TLT strategy.

This module provides strategy return construction, performance evaluation,
crisis-period analysis, turnover estimation, and test-period plotting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import (
    COST_PER_UNIT,
    CRISIS_DRAWDOWN_THRESHOLD,
    PLOT_FILENAME,
    TARGET_VOL,
    TRADING_DAYS,
    VOL_WINDOW,
    POSITION_COLUMNS,
    ASSET_COLUMNS,
)


def compute_strategy_returns(
    signals: pd.DataFrame,
    returns: pd.DataFrame,
    cost_per_unit: float = COST_PER_UNIT,
    target_vol: float = TARGET_VOL,
    vol_window: int = VOL_WINDOW,
    trading_days: int = TRADING_DAYS,
) -> pd.Series:
    """
    Compute daily strategy returns after signal lagging, volatility targeting,
    and transaction costs.

    Args:
        signals: DataFrame containing 'SPY_pos' and 'TLT_pos'.
        returns: DataFrame containing 'SPY' and 'TLT' daily returns.
        cost_per_unit: Transaction cost per unit of turnover.
        target_vol: Annualized target portfolio volatility.
        vol_window: Rolling window used for realized volatility estimation.
        trading_days: Annualization factor.

    Returns:
        Series of daily strategy returns after costs.

    Raises:
        KeyError: If required columns are missing.
        ValueError: If inputs are empty or misaligned.
    """
    _validate_signal_and_return_inputs(signals, returns)

    positions = signals.loc[:, POSITION_COLUMNS].shift(1).fillna(0.0)
    asset_returns = returns.loc[:, ASSET_COLUMNS]

    raw_returns = (
        positions["SPY_pos"] * asset_returns["SPY"]
        + positions["TLT_pos"] * asset_returns["TLT"]
    )

    realized_vol = raw_returns.shift(1).rolling(vol_window).std() * np.sqrt(trading_days)
    realized_vol = realized_vol.replace(0, np.nan)

    scaling = (target_vol / realized_vol).clip(0, 2.0).fillna(0.0)
    scaled_positions = positions.mul(scaling, axis=0)

    scaled_returns = (
        scaled_positions["SPY_pos"] * asset_returns["SPY"]
        + scaled_positions["TLT_pos"] * asset_returns["TLT"]
    )

    turnover = scaled_positions.diff().abs().sum(axis=1)
    costs = turnover * cost_per_unit

    return scaled_returns - costs


def compute_performance(
    strategy_returns: pd.Series,
    trading_days: int = TRADING_DAYS,
) -> dict[str, Any]:
    """
    Compute core performance statistics for a return series.

    Args:
        strategy_returns: Daily return series.
        trading_days: Annualization factor.

    Returns:
        Dictionary containing:
            - sharpe
            - volatility
            - annual_return
            - max_drawdown
            - win_rate
            - cumulative
            - drawdown

    Raises:
        ValueError: If the return series is empty.
    """
    _validate_return_series(strategy_returns)

    mean_return = strategy_returns.mean()
    daily_volatility = strategy_returns.std()

    sharpe = (
        np.sqrt(trading_days) * mean_return / daily_volatility
        if daily_volatility != 0
        else 0.0
    )

    cumulative = (1.0 + strategy_returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = cumulative / rolling_max - 1.0

    total_return = cumulative.iloc[-1] - 1.0
    annual_return = (1.0 + total_return) ** (trading_days / len(strategy_returns)) - 1.0
    win_rate = (strategy_returns > 0).mean()

    return {
        "sharpe": sharpe,
        "volatility": daily_volatility * np.sqrt(trading_days),
        "annual_return": annual_return,
        "max_drawdown": drawdown.min(),
        "win_rate": win_rate,
        "cumulative": cumulative,
        "drawdown": drawdown,
    }


def run_strategy(
    strategy_func: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame],
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    label: str = "",
) -> tuple[dict[str, Any], pd.Series]:
    """
    Run a strategy function on price and return data.

    Args:
        strategy_func: Callable mapping `(returns, prices)` to position signals.
        prices: Price DataFrame.
        returns: Return DataFrame.
        label: Optional label used in console output.

    Returns:
        Tuple of:
            - performance dictionary
            - strategy return series
    """
    signals = strategy_func(returns, prices)
    strategy_returns = compute_strategy_returns(signals, returns)
    performance = compute_performance(strategy_returns)

    if label:
        print(f"\n=== {label} ===")
        print_performance(performance)

    return performance, strategy_returns


def run_strategy_on_window(
    strategy_func: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame],
    context_prices: pd.DataFrame,
    context_returns: pd.DataFrame,
    evaluation_start: str | pd.Timestamp,
    evaluation_end: str | pd.Timestamp | None = None,
    label: str = "",
) -> dict[str, Any]:
    """
    Run a strategy on full historical context and score only an evaluation window.

    Signals and portfolio returns are constructed on the full context through
    `evaluation_end`, then sliced for performance. This preserves legitimate
    rolling-feature history, volatility-targeting history, execution lag, and
    first-window transaction costs without including pre-window P&L in metrics.
    """
    if context_prices.empty:
        raise ValueError("context_prices must be non-empty.")
    if context_returns.empty:
        raise ValueError("context_returns must be non-empty.")

    evaluation_start_ts = pd.Timestamp(evaluation_start)
    evaluation_end_ts = (
        pd.Timestamp(evaluation_end)
        if evaluation_end is not None
        else context_returns.index.max()
    )

    if evaluation_start_ts > evaluation_end_ts:
        raise ValueError("evaluation_start must be on or before evaluation_end.")

    scoped_returns = context_returns.loc[:evaluation_end_ts]
    if scoped_returns.empty:
        raise ValueError("No context returns available through evaluation_end.")

    scoped_prices = context_prices.loc[scoped_returns.index]

    full_signals = strategy_func(scoped_returns, scoped_prices)
    full_strategy_returns = compute_strategy_returns(full_signals, scoped_returns)

    evaluation_strategy_returns = full_strategy_returns.loc[
        evaluation_start_ts:evaluation_end_ts
    ]
    evaluation_signals = full_signals.loc[evaluation_start_ts:evaluation_end_ts]

    if evaluation_strategy_returns.empty:
        raise ValueError("Evaluation window contains no strategy returns.")

    performance = compute_performance(evaluation_strategy_returns)
    turnover = compute_turnover_on_window(
        full_signals,
        evaluation_start=evaluation_start_ts,
        evaluation_end=evaluation_end_ts,
    )

    if label:
        print(f"\n=== {label} ===")
        print_performance(performance)

    return {
        "performance": performance,
        "strategy_returns": evaluation_strategy_returns,
        "signals": evaluation_signals,
        "turnover": turnover,
        "full_strategy_returns": full_strategy_returns,
        "full_signals": full_signals,
        "context_prices": scoped_prices,
        "context_returns": scoped_returns,
    }


def print_performance(performance: dict[str, Any]) -> None:
    """
    Print a compact set of performance statistics.

    Args:
        performance: Performance dictionary returned by `compute_performance`.
    """
    print("\n--- PERFORMANCE ---")
    print(f"Sharpe Ratio     : {performance['sharpe']:.2f}")
    print(f"Annual Return    : {performance['annual_return']:.2%}")
    print(f"Volatility       : {performance['volatility']:.2%}")
    print(f"Max Drawdown     : {performance['max_drawdown']:.2%}")
    print(f"Win Rate         : {performance['win_rate']:.2%}")


def compute_detailed_metrics(
    returns: pd.Series,
    trading_days: int = TRADING_DAYS,
) -> dict[str, float]:
    """
    Compute an expanded set of performance metrics.

    Args:
        returns: Daily return series.
        trading_days: Annualization factor.

    Returns:
        Dictionary containing total return, annual return, volatility, Sharpe,
        Sortino, max drawdown, Calmar, and win rate.

    Raises:
        ValueError: If the return series is empty.
    """
    _validate_return_series(returns)

    cumulative = (1.0 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = cumulative / rolling_max - 1.0

    total_return = cumulative.iloc[-1] - 1.0
    annual_return = (1.0 + total_return) ** (trading_days / len(returns)) - 1.0

    daily_volatility = returns.std()
    annualized_volatility = daily_volatility * np.sqrt(trading_days)

    mean_return = returns.mean()
    sharpe = (
        np.sqrt(trading_days) * mean_return / daily_volatility
        if daily_volatility != 0
        else 0.0
    )

    max_drawdown = drawdown.min()

    downside_daily_volatility = returns[returns < 0].std()
    downside_volatility = downside_daily_volatility * np.sqrt(trading_days)
    sortino = annual_return / downside_volatility if downside_volatility != 0 else 0.0

    calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0.0
    win_rate = (returns > 0).mean()

    return {
        "Total Return": total_return,
        "Annual Return": annual_return,
        "Volatility": annualized_volatility,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max Drawdown": max_drawdown,
        "Calmar": calmar,
        "Win Rate": win_rate,
    }


def compute_crisis_returns(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> pd.Series:
    """
    Extract strategy returns during benchmark-defined crisis periods.

    Crisis periods are defined by benchmark drawdowns below
    `CRISIS_DRAWDOWN_THRESHOLD`.

    Args:
        strategy_returns: Strategy return series.
        benchmark_returns: Benchmark return series.

    Returns:
        Strategy returns observed during crisis periods.

    Raises:
        ValueError: If input series are empty or misaligned.
    """
    _validate_aligned_series(strategy_returns, benchmark_returns)

    benchmark_cumulative = (1.0 + benchmark_returns).cumprod()
    rolling_max = benchmark_cumulative.cummax()
    benchmark_drawdown = benchmark_cumulative / rolling_max - 1.0

    crisis_mask = benchmark_drawdown < CRISIS_DRAWDOWN_THRESHOLD
    return strategy_returns.loc[crisis_mask]


def compute_turnover(
    signals: pd.DataFrame,
    trading_days: int = TRADING_DAYS,
) -> float:
    """
    Compute annualized turnover from changes in position signals.

    Args:
        signals: DataFrame containing 'SPY_pos' and 'TLT_pos'.
        trading_days: Annualization factor.

    Returns:
        Annualized turnover.
    """
    missing_cols = set(POSITION_COLUMNS) - set(signals.columns)
    if missing_cols:
        raise KeyError(f"Missing required signal columns: {sorted(missing_cols)}")

    positions = signals.loc[:, POSITION_COLUMNS].fillna(0.0)
    turnover = positions.diff().abs().sum(axis=1)

    return float(turnover.mean() * trading_days)


def compute_turnover_on_window(
    signals: pd.DataFrame,
    evaluation_start: str | pd.Timestamp,
    evaluation_end: str | pd.Timestamp | None = None,
    trading_days: int = TRADING_DAYS,
) -> float:
    """
    Compute annualized turnover on a window after full-context differencing.

    The first evaluation-day turnover includes the transition from the prior
    context day when one exists.
    """
    missing_cols = set(POSITION_COLUMNS) - set(signals.columns)
    if missing_cols:
        raise KeyError(f"Missing required signal columns: {sorted(missing_cols)}")

    positions = signals.loc[:, POSITION_COLUMNS].fillna(0.0)
    turnover = positions.diff().abs().sum(axis=1)

    evaluation_start_ts = pd.Timestamp(evaluation_start)
    evaluation_end_ts = (
        pd.Timestamp(evaluation_end)
        if evaluation_end is not None
        else turnover.index.max()
    )
    evaluation_turnover = turnover.loc[evaluation_start_ts:evaluation_end_ts]

    if evaluation_turnover.empty:
        raise ValueError("Evaluation window contains no turnover observations.")

    return float(evaluation_turnover.mean() * trading_days)


def plot_test_period_performance(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    strategy_label: str = "Strategy",
    benchmark_label: str = "Benchmark",
    title: str = "Strategy vs Benchmark",
    filename: str | Path = PLOT_FILENAME,
) -> None:
    """
    Plot cumulative test-period performance for the strategy and benchmark.

    Args:
        strategy_returns: Strategy return series.
        benchmark_returns: Benchmark return series.
        strategy_label: Legend label for the strategy.
        benchmark_label: Legend label for the benchmark.
        title: Plot title.
        filename: Output path for the saved figure.

    Raises:
        ValueError: If input series are empty or misaligned.
    """
    _validate_aligned_series(strategy_returns, benchmark_returns)

    output_path = Path(filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    strategy_cumulative = (1.0 + strategy_returns).cumprod()
    benchmark_cumulative = (1.0 + benchmark_returns).cumprod()
    strategy_cumulative = strategy_cumulative / strategy_cumulative.iloc[0]
    benchmark_cumulative = benchmark_cumulative / benchmark_cumulative.iloc[0]

    plt.figure(figsize=(12, 6))
    plt.plot(
        strategy_cumulative.index,
        strategy_cumulative.to_numpy(),
        label=strategy_label,
        linewidth=2,
    )
    plt.plot(
        benchmark_cumulative.index,
        benchmark_cumulative.to_numpy(),
        label=benchmark_label,
        linewidth=2,
    )

    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Cumulative Growth")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def _validate_signal_and_return_inputs(
    signals: pd.DataFrame,
    returns: pd.DataFrame,
) -> None:
    """
    Validate inputs for strategy return construction.

    Args:
        signals: Signal DataFrame.
        returns: Return DataFrame.

    Raises:
        KeyError: If required columns are missing.
        ValueError: If inputs are empty or misaligned.
    """
    missing_signal_cols = set(POSITION_COLUMNS) - set(signals.columns)
    if missing_signal_cols:
        raise KeyError(f"Missing required signal columns: {sorted(missing_signal_cols)}")

    missing_return_cols = set(ASSET_COLUMNS) - set(returns.columns)
    if missing_return_cols:
        raise KeyError(f"Missing required return columns: {sorted(missing_return_cols)}")

    if signals.empty:
        raise ValueError("signals must be non-empty.")

    if returns.empty:
        raise ValueError("returns must be non-empty.")

    if not signals.index.equals(returns.index):
        raise ValueError("signals and returns must have identical indices.")


def _validate_return_series(returns: pd.Series) -> None:
    """
    Validate a return series.

    Args:
        returns: Return series.

    Raises:
        ValueError: If the series is empty.
    """
    if returns.empty:
        raise ValueError("return series must be non-empty.")


def _validate_aligned_series(
    left: pd.Series,
    right: pd.Series,
) -> None:
    """
    Validate two aligned return series.

    Args:
        left: First return series.
        right: Second return series.

    Raises:
        ValueError: If either series is empty or indices do not match.
    """
    if left.empty or right.empty:
        raise ValueError("input series must be non-empty.")

    if not left.index.equals(right.index):
        raise ValueError("input series must have identical indices.")
