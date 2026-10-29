"""R2 rungs L0–L5 (charter ladder; D2.1–D2.7): target weights decided at close t (NaN row = no decision), every book run
through the one accounting function (`rspy.accounting.run`, traded at close t+1).

Inputs `Inputs`: the KF session calendar from `start` to `end`; R (T, 2) = [Hi 20 (SPY proxy), GSW 25y (TLT proxy)]
returns of row t; bill, mmy, dt as rspy.accounting (D1.1). One line per transform (value at t uses data ≤ t):
- monthly decision rows (D2.5): the session before quantkit `offset_masks` offset o's trade row (o = 0: the last
  session of month m, traded on the first session of m+1, the rung of record);
- L0: [1, 0] decided at row 0 only (buy and hold, drifts);
- L1: v1 (frozen `legacy/`, selected params) on permitted data = R1's S7 construction (`legacy_bridge`), shorts floored;
- L2 (D2.3): v1's scaling on an all-SPY signal: scaled[t] = min(0.15 / σ̂, 2), σ̂ = 20-row std (ddof 1) of the book's
  own returns through row t − 1, ×√252 (`legacy_bridge.v1_scaled` mirror); decided at close t − 1; unbanded;
- L3: [0.6, 0.4] at each monthly decision row; 5 pp band;
- L4 (D2.7): w_i ∝ 1/σ_i, σ_i = sample std (ddof 1) of the 63 returns ending at the decision row (all 63 required);
- L4b (D2.6): `quantkit.alloc.risk.erc` on the same 63-row sample covariance (= L4 for two assets);
- vol layer (L2-u, L5, L5-lev; D2.1/D2.2): scale_t = min(target / √(252·f_t), cap), f_t the forecast stamped t of the
  parent's daily log return; target_t = scale_t × the parent's latest decided weights (decided ≤ t); daily rows.
Complexity: O(T·N) per book (numba walk); rolling σ O(T) (pandas rolling); ERC per month-end O(1) for 2×2.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd
from quantkit.alloc.risk import erc
from quantkit.trade.tranche import offset_masks

from rspy import accounting, paths

ANN = 252


@dataclass(frozen=True)
class Inputs:
    index: pd.DatetimeIndex
    R: np.ndarray
    bill: np.ndarray
    mmy: np.ndarray
    dt: np.ndarray

    @staticmethod
    def from_panel(panel: pd.DataFrame, start, end) -> Inputs:
        p = panel.loc[start:end, ["hi20", "tlt25", "bill", "mmy", "dt"]]
        if p.isna().any().any():
            raise ValueError("a leg is missing inside the R2 window")
        return Inputs(pd.DatetimeIndex(p.index), p[["hi20", "tlt25"]].to_numpy(), p["bill"].to_numpy(),
                      p["mmy"].to_numpy(), p["dt"].to_numpy())


def acc_kw() -> dict:
    a = paths.rules()["accounting"]
    return {"cost_rates": np.array([a["cost_bp_per_side"]["spy"], a["cost_bp_per_side"]["tlt"]]) * 1e-4,
            "spread": a["financing_spread_bp"] * 1e-4}


def book(target, inp: Inputs, *, band: float | None = None, cost_mult: float = 1.0, stress_bp: float = 0.0):
    return accounting.run(target, inp.R, inp.bill, inp.mmy, inp.dt, band=band, cost_mult=cost_mult,
                          stress_spread=stress_bp * 1e-4, index=inp.index, **acc_kw())


# ---- decision rows -----------------------------------------------------------------------------------------------
def decision_rows(index: pd.DatetimeIndex, offset: int = 0) -> np.ndarray:
    """Rows deciding for offset o's trade rows: one session before each trade row (D2.5 amendment 2)."""
    tr = np.flatnonzero(offset_masks(index, [offset])[offset])
    dec = np.zeros(len(index), bool)
    dec[tr[tr >= 1] - 1] = True  # a trade row at 0 has no prior close to decide on
    return dec


def _on(rows: np.ndarray, W: np.ndarray) -> np.ndarray:
    out = np.full(W.shape, np.nan)
    out[rows] = W[rows]
    return out


# ---- monthly rungs -----------------------------------------------------------------------------------------------
def l0_target(inp: Inputs) -> np.ndarray:
    t = np.full(inp.R.shape, np.nan)
    t[0] = (1.0, 0.0)
    return t


def l3_target(inp: Inputs, rows: np.ndarray) -> np.ndarray:
    w = paths.rules()["r2"]["L3"]["weights"]
    return _on(rows, np.tile([w["spy"], w["tlt"]], (len(inp.index), 1)))


def sigma63(inp: Inputs, window: int = 63) -> np.ndarray:
    """(T, 2) sample std (ddof 1) of the `window` returns ending at row t; NaN until all are present."""
    return pd.DataFrame(inp.R).rolling(window, min_periods=window).std(ddof=1).to_numpy()


def l4_target(inp: Inputs, rows: np.ndarray) -> np.ndarray:
    s = sigma63(inp, paths.rules()["r2"]["L4"]["window"])
    iv = 1.0 / s
    W = iv / iv.sum(axis=1, keepdims=True)
    return _on(rows & np.isfinite(W).all(axis=1), W)


def l4b_target(inp: Inputs, rows: np.ndarray, window: int = 63) -> np.ndarray:
    W = np.full(inp.R.shape, np.nan)
    for t in np.flatnonzero(rows):
        if t + 1 >= window:
            W[t] = erc(np.cov(inp.R[t - window + 1:t + 1].T, ddof=1))
    return W


# ---- vol layer -----------------------------------------------------------------------------------------------------
def carry(target: np.ndarray) -> np.ndarray:
    """The latest decided weights at each row (decided ≤ t), NaN before the first decision."""
    return pd.DataFrame(target).ffill().to_numpy()


def vol_scaled(parent_w: np.ndarray, f: np.ndarray, target_vol: float, cap: float) -> np.ndarray:
    sig = np.sqrt(ANN * np.asarray(f, np.float64))
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.minimum(target_vol / sig, cap)
    T = parent_w * scale[:, None]
    T[~np.isfinite(T).all(axis=1)] = np.nan
    return T


def vol_target(parent_target: np.ndarray, f: pd.Series, index: pd.DatetimeIndex, target_vol: float,
               cap: float) -> np.ndarray:
    """The vol layer as wired for every vol-targeted rung: row t uses the forecast STAMPED t (data ≤ t, quantkit) and the
    parent's latest decided weights (decided ≤ t); traded at t+1 by the accounting. Review R2 MATERIAL 2: tested."""
    return vol_scaled(carry(parent_target), f.reindex(index).to_numpy(), target_vol, cap)


def log_book_returns(bk) -> pd.Series:
    """The parent book's daily log net return from its first invested row (the series the vol zoo forecasts)."""
    s = pd.Series(np.log1p(bk.net), index=bk.index)
    first = int(np.argmax(bk.held.sum(axis=1) > 0))
    return s.iloc[first:]


# ---- v1-derived rungs (legacy code is imported with the yfinance stub, D0.2) --------------------------------------------
def _legacy():
    from tests.legacy_support import yfinance_stub

    sys.modules.setdefault("yfinance", yfinance_stub())
    from rspy import legacy_bridge

    return legacy_bridge


def v1_target(scaled: pd.DataFrame) -> np.ndarray:
    """`legacy_bridge.run_accounting`'s mapping: scaled[t] (decided at close t − 1) → target row t − 1, shorts floored.
    tests/test_r2.py pins rspy's L1/L2 books to `legacy_bridge.run_accounting` on the same inputs (review R2 MATERIAL 2)."""
    t = scaled.shift(-1)
    t.iloc[-1] = np.nan
    return t.clip(lower=0.0).to_numpy()


def l1_target(panel: pd.DataFrame, inp: Inputs) -> np.ndarray:
    lb = _legacy()
    w = paths.rules()["legacy"]["vix_proxy"]["window"]
    start = inp.index[0] - pd.Timedelta(days=7)
    prices, rets, _ = lb.new_data_inputs(panel, panel.loc[:start].index[-1], inp.index[-1], w)
    sig = lb.v1_signals(prices, rets)
    R = pd.DataFrame(inp.R, index=inp.index, columns=["SPY", "TLT"])
    return v1_target(lb.v1_scaled(sig.reindex(inp.index).fillna(0.0), R))


def l2_target(inp: Inputs) -> np.ndarray:
    lb = _legacy()
    R = pd.DataFrame(inp.R, index=inp.index, columns=["SPY", "TLT"])
    sig = pd.DataFrame({"SPY_pos": 1.0, "TLT_pos": 0.0}, index=inp.index)
    return v1_target(lb.v1_scaled(sig, R))
