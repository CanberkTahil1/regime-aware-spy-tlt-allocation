"""R1 legacy reconciliation (D1.4, D1.5): v1 (frozen `legacy/`, its selected params) taken from its own accounting to
the charter's, one correction per step, then onto permitted data. S7 = L1.

v1's decision: `scaled[t]` (v1 backtest.py:57-70) = signals[t−1] × vol scaling from rows ≤ t−1, held over row t, i.e.
decided at close t−1 and traded at that same close (same-close execution). Mirrored here line for line by `v1_scaled`
and proven equal to v1's own `compute_strategy_returns` (tests/test_legacy_bridge.py); v1's code is never edited.

Steps (cumulative; `spec/rules.yaml` legacy.steps):
- S0 v1 as committed: net = scaledᵀR − 5 bp·Σ|Δscaled| (v1's own function).
- S1 t+1: held = scaled shifted one more row (decided at close t−1, traded at close t, earns row t+1); v1 costs.
- S2 + cash at the bill on max(1 − Σheld, 0) and financing (mmy + 25 bp) on Σmax(held, 0) − 1 > 0; v1 costs.
- S3 `rspy.accounting.run` (drift, true traded turnover, 3/2 bp per side), shorts still allowed.
- S4 = S3 returns; metrics switch to excess Sharpe and standard Sortino.
- S5 targets floored at 0 (no shorts).
- S6 v1's `^VIX` column replaced by the 20-session realised vol of v1's SPY (D1.5); signals recomputed.
- S7 permitted data: SPY → KF Hi 20, TLT → GSW 25y proxy, ^VIX → realised vol of Hi 20, KF calendar (= L1).
Timing: every v1 signal uses data ≤ its decision close (v1's own rolling windows); the realised-vol proxy at t uses
returns ≤ t (rolling std, min_periods 20). Bills/financing use the previous session's H.15 rate (D1.1).
Callers must install the yfinance stub before importing `legacy` (tests.legacy_support, D0.2).
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd

from rspy import accounting

V1_COST = 0.0005
STEPS = ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"]


def _legacy(mod: str):
    return importlib.import_module(f"legacy.{mod}")


def v1_params() -> pd.Series:
    """v1's selected parameters (legacy/results/tables/summary_metrics.csv)."""
    s = pd.read_csv(_legacy("config").TABLES_DIR / "summary_metrics.csv").iloc[0]
    keys = {"z": "z_window", "th": "threshold", "sw": "slow_window", "sth": "slow_threshold", "ddw": "dd_window",
            "ddt": "dd_threshold", "cw": "crash_weight"}
    return pd.Series({k: s[v] for k, v in keys.items()})


def v1_signals(prices: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    run = _legacy("run")
    return run.build_strategy_from_params(v1_params())(returns, prices.loc[returns.index])


def v1_scaled(signals: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """legacy/backtest.py:57-70 verbatim (target 15%, 20-day window, cap 2): weights held over each row."""
    bt = _legacy("backtest")
    positions = signals.loc[:, bt.POSITION_COLUMNS].shift(1).fillna(0.0)
    asset_returns = returns.loc[:, bt.ASSET_COLUMNS]
    raw_returns = positions["SPY_pos"] * asset_returns["SPY"] + positions["TLT_pos"] * asset_returns["TLT"]
    realized_vol = raw_returns.shift(1).rolling(bt.VOL_WINDOW).std() * np.sqrt(bt.TRADING_DAYS)
    realized_vol = realized_vol.replace(0, np.nan)
    scaling = (bt.TARGET_VOL / realized_vol).clip(0, 2.0).fillna(0.0)
    return positions.mul(scaling, axis=0)


def v1_book(held: pd.DataFrame, returns: pd.DataFrame, cost: float = V1_COST) -> pd.DataFrame:
    """v1's accounting on any held-weight path: gross, v1 cost (5 bp × Σ|Δheld|, no drift), net, turnover."""
    R = returns.loc[:, ["SPY", "TLT"]]
    gross = held["SPY_pos"] * R["SPY"] + held["TLT_pos"] * R["TLT"]
    turn = held.diff().abs().sum(axis=1)
    return pd.DataFrame({"gross": gross, "cost": turn * cost, "net": gross - turn * cost, "turnover": turn,
                         "cash": 0.0, "financing": 0.0, "gross_exp": held.abs().sum(axis=1),
                         "w_SPY": held["SPY_pos"], "w_TLT": held["TLT_pos"]})


def add_cash_and_financing(book: pd.DataFrame, held: pd.DataFrame, bills: pd.DataFrame, spread: float) -> pd.DataFrame:
    """S2: cash max(1 − Σheld, 0)·bill; financing via quantkit accrual on the weights held over each row (as
    `accounting._financing`)."""
    b = bills.reindex(held.index)
    h = held.to_numpy()
    cash = np.maximum(1.0 - h.sum(axis=1), 0.0) * b["bill"].to_numpy()
    fin = accounting._financing(h, b["mmy"].to_numpy(), b["dt"].to_numpy(), spread, 0.0)
    out = book.copy()
    out["cash"], out["financing"] = cash, fin
    out["net"] = out["gross"] + cash - fin - out["cost"]
    return out


def run_accounting(scaled: pd.DataFrame, returns: pd.DataFrame, bills: pd.DataFrame, *, rates, spread: float,
                   allow_shorts: bool, floor_zero: bool = False) -> pd.DataFrame:
    """S3+: v1's decision (scaled[t] decided at close t−1) through rspy.accounting (traded at close t, earns t+1)."""
    target = scaled.shift(-1)  # target[s] = decision made at close s
    target.iloc[-1] = np.nan
    if floor_zero:
        target = target.clip(lower=0.0)
    b = bills.reindex(returns.index)
    bk = accounting.run(target.to_numpy(), returns[["SPY", "TLT"]].to_numpy(), b["bill"].to_numpy(),
                        b["mmy"].to_numpy(), b["dt"].to_numpy(), cost_rates=rates, spread=spread,
                        allow_shorts=allow_shorts, index=returns.index)
    df = pd.DataFrame({"gross": bk.gross, "cost": bk.cost, "net": bk.net, "turnover": bk.turnover, "cash": bk.cash,
                       "financing": bk.financing, "gross_exp": np.abs(bk.held).sum(axis=1)}, index=returns.index)
    df[["w_SPY", "w_TLT"]] = bk.held
    return df


def rv_proxy(spy_returns: pd.Series, index: pd.Index, window: int) -> pd.Series:
    """D1.5: rolling std of SPY returns (ddof 1, min_periods = window), value at t uses returns ≤ t; on `index`."""
    return spy_returns.rolling(window, min_periods=window).std().reindex(index)


def v1_metrics(net: pd.Series, window) -> dict:
    """v1's own definitions (compute_performance / compute_detailed_metrics): Sharpe without rf, its Sortino."""
    bt = _legacy("backtest")
    x = net.loc[window[0]:window[1]]
    d = bt.compute_detailed_metrics(x)
    return {"cagr": d["Annual Return"], "vol": d["Volatility"], "sharpe": d["Sharpe"], "sortino": d["Sortino"],
            "max_dd": d["Max Drawdown"], "n": len(x)}


def charter_metrics(net: pd.Series, bill: pd.Series, window) -> dict:
    x, b = net.loc[window[0]:window[1]], bill.reindex(net.index).loc[window[0]:window[1]]
    e = (x - b).to_numpy()
    from quantkit.stats import max_drawdown, sharpe

    return {"cagr": float((1 + x).prod() ** (252 / len(x)) - 1), "vol": float(x.std() * np.sqrt(252)),
            "sharpe": float(sharpe(e)), "sortino": accounting.sortino(e), "max_dd": float(max_drawdown(x.to_numpy())),
            "n": len(x)}


def reconcile(v1_prices: pd.DataFrame, v1_returns: pd.DataFrame, v1_bills: pd.DataFrame, new_prices: pd.DataFrame,
              new_returns: pd.DataFrame, new_bills: pd.DataFrame, rules: dict) -> dict[str, pd.DataFrame]:
    """All eight steps as daily books {step: DataFrame(gross, cost, net, turnover, cash, financing, gross_exp, ...)}."""
    acc = rules["accounting"]
    rates = np.array([acc["cost_bp_per_side"]["spy"], acc["cost_bp_per_side"]["tlt"]]) * 1e-4
    spread = acc["financing_spread_bp"] * 1e-4
    w = rules["legacy"]["vix_proxy"]["window"]
    out: dict[str, pd.DataFrame] = {}
    sig = v1_signals(v1_prices, v1_returns)
    scaled = v1_scaled(sig, v1_returns)
    out["S0"] = v1_book(scaled, v1_returns)
    held1 = scaled.shift(1).fillna(0.0)
    out["S1"] = v1_book(held1, v1_returns)
    out["S2"] = add_cash_and_financing(out["S1"], held1, v1_bills, spread)
    out["S3"] = run_accounting(scaled, v1_returns, v1_bills, rates=rates, spread=spread, allow_shorts=True)
    out["S4"] = out["S3"]
    out["S5"] = run_accounting(scaled, v1_returns, v1_bills, rates=rates, spread=spread, allow_shorts=False,
                               floor_zero=True)
    p6 = v1_prices.copy()
    p6["^VIX"] = rv_proxy(v1_returns["SPY"], p6.index, w)
    sig6 = v1_signals(p6, v1_returns)
    out["S6"] = run_accounting(v1_scaled(sig6, v1_returns), v1_returns, v1_bills, rates=rates, spread=spread,
                               allow_shorts=False, floor_zero=True)
    sig7 = v1_signals(new_prices, new_returns)
    out["S7"] = run_accounting(v1_scaled(sig7, new_returns), new_returns, new_bills, rates=rates, spread=spread,
                               allow_shorts=False, floor_zero=True)
    out["_scaled_S0"], out["_scaled_S7"] = scaled, v1_scaled(sig7, new_returns)
    out["_vix_score_corr_inputs"] = pd.DataFrame({"vix": v1_prices["^VIX"], "rv": p6["^VIX"]})
    return out


def new_data_inputs(panel: pd.DataFrame, start, end, window: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """S7 inputs on the KF calendar over [start, end]: price indices from the permitted legs (base 100 at the first
    session), v1-style returns (pct_change), bills; ^VIX = realised vol of Hi 20 (D1.5)."""
    p = panel.loc[start:end]
    if p[["hi20", "tlt25", "bill"]].iloc[1:].isna().any().any():
        raise ValueError("a permitted leg is missing inside the reconciliation window")
    r = p[["hi20", "tlt25"]].copy()
    r.iloc[0] = 0.0  # the base session: price index starts at 100
    prices = 100 * (1 + r).cumprod()
    prices.columns = ["SPY", "TLT"]
    returns = prices.pct_change().dropna()
    prices["^VIX"] = rv_proxy(returns["SPY"], prices.index, window)
    bills = p[["bill", "mmy", "dt"]]
    return prices, returns, bills
