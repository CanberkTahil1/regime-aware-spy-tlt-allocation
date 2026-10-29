"""
Data loading and preprocessing for the regime-aware SPY-TLT strategy.

This module handles market data retrieval, local caching, return
construction, and train/validation/test splitting.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

from config import DATA_PATH, START_DATE, TICKERS, TEST_END_DATE


def load_data(
    start: str = START_DATE,
    force_download: bool = False,
) -> pd.DataFrame:
    """
    Load adjusted close prices from cache or download them from Yahoo Finance.

    Args:
        start: Start date for the downloaded price history.
        force_download: If True, bypass the local cache and download fresh data.

    Returns:
        DataFrame of adjusted close prices indexed by date.

    Raises:
        ValueError: If downloaded data is empty or missing required columns.
        RuntimeError: If market data cannot be retrieved or parsed.
    """
    data_path = Path(DATA_PATH)

    if not force_download and data_path.exists():
        print(f"Loaded cached prices from {data_path}.")
        prices = pd.read_csv(data_path, index_col=0, parse_dates=True)
        _validate_price_data(prices)
        return prices

    print("Downloading market data...")
    prices = _download_price_data(start=start)
    _validate_price_data(prices)

    data_path.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(data_path)

    return prices


def prepare_data(
    start: str = START_DATE,
    force_download: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load price data and compute daily returns.

    Args:
        start: Start date for the downloaded price history.
        force_download: If True, bypass the local cache and download fresh data.

    Returns:
        Tuple of:
            - prices: Adjusted close price DataFrame
            - returns: Daily percentage return DataFrame
    """
    prices = load_data(start=start, force_download=force_download)
    prices = prices.loc[:TEST_END_DATE]          # <-- freeze the window
    returns = prices.pct_change().dropna()

    return prices, returns


def split_data(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    train_end: str,
    val_end: str,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Split prices and returns into train, validation, and test segments.

    Samples are split with non-overlapping date masks so boundary dates are
    not duplicated across adjacent samples.

    Args:
        prices: Price DataFrame indexed by date.
        returns: Return DataFrame indexed by date.
        train_end: End date for the training sample.
        val_end: End date for the validation sample.

    Returns:
        Tuple of:
            - train_prices
            - train_returns
            - val_prices
            - val_returns
            - test_prices
            - test_returns

    Raises:
        ValueError: If indices are misaligned or split dates are invalid.
    """
    _validate_split_inputs(prices, returns, train_end, val_end)

    aligned_prices = prices.loc[returns.index]

    train_end_ts = pd.Timestamp(train_end)
    val_end_ts = pd.Timestamp(val_end)

    train_mask = returns.index <= train_end_ts
    val_mask = (returns.index > train_end_ts) & (returns.index <= val_end_ts)
    test_mask = returns.index > val_end_ts

    train_prices = aligned_prices.loc[train_mask]
    val_prices = aligned_prices.loc[val_mask]
    test_prices = aligned_prices.loc[test_mask]

    train_returns = returns.loc[train_mask]
    val_returns = returns.loc[val_mask]
    test_returns = returns.loc[test_mask]

    return (
        train_prices,
        train_returns,
        val_prices,
        val_returns,
        test_prices,
        test_returns,
    )


def _download_price_data(start: str) -> pd.DataFrame:
    """
    Download adjusted close prices from Yahoo Finance.

    Args:
        start: Start date for the downloaded price history.

    Returns:
        DataFrame of adjusted close prices indexed by date.

    Raises:
        RuntimeError: If the download fails or the output cannot be parsed.
        ValueError: If the downloaded data is empty.
    """
    try:
        raw_data = yf.download(
            TICKERS,
            start=start,
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to download market data: {exc}") from exc

    if raw_data.empty:
        raise ValueError("Downloaded market data is empty.")

    try:
        prices = raw_data["Close"]
    except KeyError as exc:
        raise RuntimeError(
            "Downloaded market data does not contain a 'Close' field."
        ) from exc

    if isinstance(prices, pd.Series):
        prices = prices.to_frame()

    prices = prices.dropna()

    if prices.empty:
        raise ValueError("Price data is empty after dropping missing values.")

    return prices


def _validate_price_data(prices: pd.DataFrame) -> None:
    """
    Validate downloaded or cached price data.

    Args:
        prices: Price DataFrame to validate.

    Raises:
        ValueError: If the data is empty, malformed, or missing tickers.
    """
    if prices.empty:
        raise ValueError("Price data is empty.")

    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("Price data index must be a DatetimeIndex.")

    missing_tickers = set(TICKERS) - set(prices.columns)
    if missing_tickers:
        raise ValueError(f"Price data missing required tickers: {sorted(missing_tickers)}")


def _validate_split_inputs(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    train_end: str,
    val_end: str,
) -> None:
    """
    Validate inputs for dataset splitting.

    Args:
        prices: Price DataFrame.
        returns: Return DataFrame.
        train_end: Training sample end date.
        val_end: Validation sample end date.

    Raises:
        ValueError: If indices are misaligned or split dates are invalid.
    """
    if prices.empty:
        raise ValueError("prices must be non-empty.")

    if returns.empty:
        raise ValueError("returns must be non-empty.")

    if not prices.index.is_monotonic_increasing:
        raise ValueError("prices index must be sorted in increasing order.")

    if not returns.index.is_monotonic_increasing:
        raise ValueError("returns index must be sorted in increasing order.")

    if train_end >= val_end:
        raise ValueError("train_end must be earlier than val_end.")

    if prices.index.min() > pd.Timestamp(train_end):
        raise ValueError("train_end is earlier than the first available price date.")

    if prices.index.min() > pd.Timestamp(val_end):
        raise ValueError("val_end is earlier than the first available price date.")

    if not returns.index.equals(prices.index[1:]):
        raise ValueError(
            "returns index must align with prices after pct_change().dropna()."
        )
