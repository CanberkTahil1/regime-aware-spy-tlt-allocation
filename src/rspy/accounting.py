"""The one accounting function every rung uses (charter "Accounting (binding, R1)"; D1.1, D1.3).

`run(target, R, bill, mmy, dt, cost_rates=…, spread=…)`: target (T, N) weights DECIDED at close t (a NaN row = no
decision that day); R (T, N) asset returns earned over row t (close t−1 → close t); bill (T,) the bill return of row t
(D1.1: from the rate dated ≤ the previous session); mmy (T,) the money-market yield behind it; dt (T,) calendar days/360.

Timing, one line per transform (value at t uses data ≤ t):
- execution: a target decided at close t is traded at close t+1 and earns from row t+2 (lag 1 session, never 0);
- holdings drift between trades: w ← w ⊙ (1 + R_t) / (1 + r_pre,t), r_pre = wᵀR_t + max(1 − Σw, 0)·bill_t
  (the drift ignores the cost's and financing's own NAV effect: second order, as quantkit.alloc.backtest);
- traded turnover at the execution row = Σ|w_target − w_drifted| (one-way; vol-scaling and drift trades included);
- cost of row t = mult · Σ_i rate_i·|dw_i| (`quantkit.costs.Proportional`, per side), charged in the execution row;
- cash: max(1 − Σw_held, 0) earns bill_t; financing: `quantkit.costs.financing.accrual` on the held weights at the
  row-t rate mmy_t + spread (+ stress), dt_t (borrowed = Σmax(w,0) − 1 > 0 only);
- net_t = wᵀR_t + cash_t − financing_t − cost_t.
No shorts: a negative target raises unless `allow_shorts=True` (only the R1 legacy reconciliation rows S3–S4, D1.4).
Metrics: Sharpe = quantkit.stats.sharpe(net − bill) (rf=None, D1.3), Sortino = √252·mean(e)/√mean(min(e, 0)²).
Complexity: O(T·N) time, O(T·N) memory; the path loop is numba-compiled (charter performance contract).
Reference: tests/reference/accounting_ref.py (plain Python loop) ≤ 1e-10 (tests/test_accounting.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import numba
import numpy as np
import pandas as pd
from quantkit import costs as qcosts
from quantkit.costs import financing as qfin
from quantkit.stats import max_drawdown, sharpe

ANN = 252


@dataclass(frozen=True)
class Book:
    """Row arrays (T,): held (T, N) = weights carried into row t; gross = heldᵀR; cash; financing; cost; net;
    turnover = one-way Σ|dw| traded at the close of row t; traded = a trade happened at that close."""

    index: pd.DatetimeIndex
    held: np.ndarray
    gross: np.ndarray
    cash: np.ndarray
    financing: np.ndarray
    cost: np.ndarray
    net: np.ndarray
    turnover: np.ndarray
    traded: np.ndarray

    def frame(self, names=None) -> pd.DataFrame:
        names = names or [f"w{i}" for i in range(self.held.shape[1])]
        df = pd.DataFrame(self.held, index=self.index, columns=[f"w_{n}" for n in names])
        for k in ("gross", "cash", "financing", "cost", "net", "turnover"):
            df[k] = getattr(self, k)
        return df


@numba.njit(cache=True)
def _walk(target, R, bill):  # pragma: no cover - compiled; equivalence-tested against the reference loop
    T, N = R.shape
    held = np.zeros((T, N))
    dw = np.zeros((T, N))
    traded = np.zeros(T, np.bool_)
    h = np.zeros(N)
    for t in range(T):
        held[t] = h
        inv = 0.0
        gross = 0.0
        for i in range(N):
            inv += h[i]
            gross += h[i] * R[t, i]
        r_pre = gross + max(1.0 - inv, 0.0) * bill[t]
        if 1.0 + r_pre <= 0.0:
            raise ValueError("book wiped out (1 + r <= 0)")
        nxt = np.empty(N)
        for i in range(N):
            nxt[i] = h[i] * (1.0 + R[t, i]) / (1.0 + r_pre)
        if t >= 1 and not np.isnan(target[t - 1, 0]):
            for i in range(N):
                dw[t, i] = target[t - 1, i] - nxt[i]
                nxt[i] = target[t - 1, i]
            traded[t] = True
        h = nxt
    return held, dw, traded


def _check(name, a, shape):
    a = np.asarray(a, np.float64)
    if a.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {a.shape}")
    if not np.isfinite(a).all():
        raise ValueError(f"{name} must be finite (slice to the rows where every leg is live)")
    return np.ascontiguousarray(a)


def run(target, R, bill, mmy, dt, *, cost_rates, spread: float, stress_spread: float = 0.0, cost_mult: float = 1.0,
        allow_shorts: bool = False, index=None) -> Book:
    """See module docstring. Inputs are positional arrays (or DataFrames/Series, read by position)."""
    R = np.asarray(R, np.float64)
    T, N = R.shape
    R = _check("R", R, (T, N))
    bill, mmy, dt = (_check(n, x, (T,)) for n, x in (("bill", bill), ("mmy", mmy), ("dt", dt)))
    tg = np.ascontiguousarray(np.asarray(target, np.float64))
    if tg.shape != (T, N):
        raise ValueError(f"target must have shape {(T, N)}")
    rows = ~np.isnan(tg).all(axis=1)
    if np.isnan(tg[rows]).any() or np.isinf(tg).any():
        raise ValueError("a decision row must be finite in every column (NaN row = no decision)")
    if not allow_shorts and (tg[rows] < 0).any():
        raise ValueError("negative target: shorts are forbidden (charter)")
    held, dw, traded = _walk(tg, R, bill)
    gross = (held * R).sum(axis=1)
    cash = np.maximum(1.0 - held.sum(axis=1), 0.0) * bill
    model = qcosts.Proportional(np.asarray(cost_rates, np.float64) * cost_mult)
    cost = np.array([model(dw[t], t) if traded[t] else 0.0 for t in range(T)])
    fin = _financing(held, mmy, dt, spread, stress_spread)
    net = gross + cash - fin - cost
    turnover = np.abs(dw).sum(axis=1)
    idx = pd.DatetimeIndex(index) if index is not None else pd.RangeIndex(T)
    return Book(idx, held, gross, cash, fin, cost, net, turnover, traded)


def _financing(held, mmy, dt, spread, stress):
    """Financing of row t on the weights carried into row t (held[t]) at row t's yield mmy[t], via
    `quantkit.costs.financing.accrual`, which charges out[s] = borrowed(W[s−1])·(rate[s−1] + spread + stress)·dt[s].
    Feeding W[s] = held[s], rate[s] = mmy[s] and dt shifted by one row gives out[t+1] = borrowed(held[t])·(mmy[t] + …)·dt[t]."""
    T = len(dt)
    W = np.vstack([held, held[-1:]])
    rate = np.append(mmy, mmy[-1])
    dts = np.append(dt[:1], dt)
    out = qfin.accrual(W, rate, spread=spread, dt=dts, stress_spread=np.full(T + 1, stress))
    return out[1:]


# ---- metrics --------------------------------------------------------------------------------------------------------
def sortino(excess) -> float:
    e = np.asarray(excess, np.float64)
    dd = np.sqrt(np.mean(np.minimum(e, 0.0) ** 2))
    return float(np.sqrt(ANN) * e.mean() / dd) if dd > 0 else float("nan")


def metrics(book: Book, bill, window: tuple[str, str] | None = None) -> dict:
    """Window statistics of a book (dates inclusive): CAGR, vol, excess Sharpe, Sortino, max DD, traded turnover per
    year, average gross, cost and financing per year."""
    df = pd.DataFrame({"net": book.net, "bill": np.asarray(bill, np.float64), "turn": book.turnover,
                       "cost": book.cost, "fin": book.financing, "gross_exp": np.abs(book.held).sum(axis=1)},
                      index=book.index)
    if window is not None:
        df = df.loc[window[0]:window[1]]
    n = len(df)
    e = (df["net"] - df["bill"]).to_numpy()
    return {
        "n": n,
        "cagr": float((1 + df["net"]).prod() ** (ANN / n) - 1),
        "vol": float(df["net"].std(ddof=1) * np.sqrt(ANN)),
        "sharpe_excess": float(sharpe(e)),
        "sortino": sortino(e),
        "max_dd": float(max_drawdown(df["net"].to_numpy())),
        "turnover_pa": float(df["turn"].mean() * ANN),
        "avg_gross": float(df["gross_exp"].mean()),
        "cost_pa": float(df["cost"].mean() * ANN),
        "financing_pa": float(df["fin"].mean() * ANN),
    }
