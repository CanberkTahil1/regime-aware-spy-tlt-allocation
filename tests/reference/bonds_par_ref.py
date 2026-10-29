# REFERENCE ONLY (D1.2): copied verbatim from naive-vs-optimal `src/nvo/data/bonds.py` @ b29bb37 (sha256 71f025c6…;
# COPIED.md). The validated 25y construction ("QA vs TLT corr 0.99 / TE 2.06%/yr"); production uses quantkit.bonds.
"""Constant-maturity Treasury and TIPS total returns repriced off the Fed's GSW Svensson curves (D1.1, D1.3, D1.7).

Ported from enhanced-60-40 `src/six40/bonds.py` @ 427eeb3 (COPIED.md): the Svensson zero curve and the "buy a fresh
par bond at t−1, reprice the same bond on t's curve" construction, generalised from the fixed 10y to any maturity, to
zero-coupon bonds, and to the real (TIPS) curve. The reference implementation for quantkit Q14d `bonds.construct`.

Construction (par, maturity M, m = 2 coupons a year):
  coupon c_{t−1} solves c/m · Σ DF_{t−1}(k/m) + DF_{t−1}(M) = 1 on the t−1 curve (the curve's own par yield);
  R_t = Σ_k CF_k · DF_t(k/m − Δ) / 100 − 1, Δ = calendar days(t−1 → t) / 365, CF = 100·c/m (+100 at M).
  No coupon falls inside a one-day hold, so the dirty-price change is the total return.
Zero: R_t = exp(M·y_{t−1}(M) − (M − Δ)·y_t(M − Δ)) − 1 (bond-flows gsw.hold_return, same algebra).
Timing: R_t uses the curves of t−1 and t only (value at t uses data ≤ t, lag 0); a span > max_gap_days is NaN (not a
one-day return; six40 dropped the row, here it stays visible so a session can't silently earn 0) and counted.
Nothing here is a signal.
Reference: tests/reference/bonds_ref.py (plain per-day loop); equivalence ≤ 1e-10 (tests/test_bonds.py).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PCOLS = ["BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2"]


def fitted_params(curve: pd.DataFrame) -> pd.DataFrame:
    """Rows where GSW fitted a curve. The 4th factor is absent early on (BETA3 NA / 0, TAU2 NA or −999.99): its
    term is set to zero. Blank rows (holidays) are dropped; `n_gaps` counts what that does to the return series."""
    p = curve[PCOLS].astype(float).copy()
    bad = p["TAU2"].isna() | (p["TAU2"] <= 0) | p["BETA3"].isna()
    p.loc[bad, "BETA3"] = 0.0
    p.loc[bad, "TAU2"] = 1.0
    return p.dropna(subset=["BETA0", "BETA1", "BETA2", "TAU1"])


def svensson_zero(p: pd.DataFrame, T) -> np.ndarray:
    """Continuously compounded zero yields in percent (GSW 2007 eq. 22) at maturities T: (k,) shared or (n, k)."""
    a = p[PCOLS].to_numpy(float)
    b0, b1, b2, b3, t1, t2 = (a[:, i][:, None] for i in range(6))
    T = np.asarray(T, float)
    if T.ndim == 1:
        T = np.broadcast_to(T[None, :], (len(a), len(T)))
    with np.errstate(divide="ignore", invalid="ignore"):
        x1, x2 = T / t1, T / t2
        f1 = (1 - np.exp(-x1)) / x1
        f2 = (1 - np.exp(-x2)) / x2 - np.exp(-x2)
        f1 = np.where(T > 0, f1, 1.0)  # limit T → 0: (1 − e^{−x})/x → 1
        f2 = np.where(T > 0, f2, 0.0)
    return b0 + b1 * f1 + b2 * (f1 - np.exp(-x1)) + b3 * f2


def par_coupon(p: pd.DataFrame, maturity: float, m: int = 2) -> np.ndarray:
    """Annual par coupon (decimal) on each row's curve: c = m(1 − DF_n)/Σ DF_k."""
    t = np.arange(1, int(round(maturity * m)) + 1) / m
    df = np.exp(-svensson_zero(p, t) / 100.0 * t[None, :])
    return m * (1.0 - df[:, -1]) / df.sum(axis=1)


def reported(curve: pd.DataFrame, maturity: float, prefix: str) -> pd.Series:
    """True on fitted-curve dates on or after the first date GSW reported the maturity (column prefix +
    ceil(maturity), e.g. SVENY30 / TIPSY08). GSW's reported range only widened (nominal: 10y 1971-08-16, 20y
    1981-07-02, 30y 1985-11-25; real: 5-20y to 2004, 2-20y after; FEDS 2006-28, 2008-05), so a one-day blank inside the
    range (2008-03-21: parameters published, yields blank) is not extrapolation. A missing column = never reported."""
    col = f"{prefix}{int(np.ceil(maturity - 1e-9)):02d}"
    idx = fitted_params(curve).index
    if col not in curve.columns:
        return pd.Series(False, index=idx)
    return curve[col].reindex(idx).notna().cummax()


def _mask(r: pd.Series, curve: pd.DataFrame, maturity: float, prefix: str | None) -> pd.Series:
    """NaN unless the maturity is reported on both curve dates of the return (no extrapolation)."""
    if prefix is None:
        return r
    ok = reported(curve, maturity, prefix).to_numpy()
    return r.where(ok[1:] & ok[:-1])


def _spans(idx: pd.DatetimeIndex, year_days: float) -> np.ndarray:
    return np.diff(idx.to_numpy()).astype("timedelta64[D]").astype(float) / year_days


def par_total_return(curve: pd.DataFrame, maturity: float, *, m: int = 2, max_gap_days: int = 7,
                     year_days: float = 365.0, prefix: str | None = None) -> pd.Series:
    """Daily TR of a constant-maturity par bond (see module docstring). Index = the curve date t of each return.
    prefix ("SVENY" / "TIPSY"): NaN where the maturity was not reported (see `reported`)."""
    if round(maturity * m) != maturity * m:
        raise ValueError("maturity must be a whole number of coupon periods")
    p = fitted_params(curve)
    n = int(round(maturity * m))
    base = np.arange(1, n + 1) / m
    c = par_coupon(p, maturity, m)[:-1]
    dt = _spans(p.index, year_days)
    T = base[None, :] - dt[:, None]
    df = np.where(T > 0, np.exp(-svensson_zero(p.iloc[1:], T) / 100.0 * T), 0.0)
    cf = np.broadcast_to((100.0 * c / m)[:, None], (len(c), n)).copy()
    cf[:, -1] += 100.0
    r = pd.Series((cf * df).sum(axis=1) / 100.0 - 1.0, index=p.index[1:], name=f"par_{maturity:g}")
    return _mask(r.where(dt * year_days <= max_gap_days), curve, maturity, prefix)


def zero_total_return(curve: pd.DataFrame, maturity: float, *, max_gap_days: int = 7,
                      year_days: float = 365.0, prefix: str | None = None) -> pd.Series:
    """Daily TR of a constant-maturity zero: exp(M·y_{t−1}(M) − (M − Δ)·y_t(M − Δ)) − 1."""
    p = fitted_params(curve)
    dt = _spans(p.index, year_days)
    ya = svensson_zero(p.iloc[:-1], np.array([maturity]))[:, 0] / 100.0
    yb = svensson_zero(p.iloc[1:], (maturity - dt)[:, None])[:, 0] / 100.0
    r = pd.Series(np.expm1(maturity * ya - (maturity - dt) * yb), index=p.index[1:], name=f"zero_{maturity:g}")
    return _mask(r.where(dt * year_days <= max_gap_days), curve, maturity, prefix)


def n_gaps(curve: pd.DataFrame, max_gap_days: int = 7) -> int:
    """How many returns the constructors set to NaN for spanning more than max_gap_days calendar days."""
    idx = fitted_params(curve).index
    return int((np.diff(idx.to_numpy()).astype("timedelta64[D]").astype(float) > max_gap_days).sum())


# ---- TIPS: real TR × Treasury index ratio (D1.3; 31 CFR 356 App. B) ------------------------------------------------
def ref_cpi(dates: pd.DatetimeIndex, cpi: pd.Series) -> np.ndarray:
    """Treasury reference CPI on each date: RefCPI(day d of month M) = C(M−3) + (d − 1)/D_M · (C(M−2) − C(M−3)),
    C = NSA CPI-U by reference month (a monthly PeriodIndex Series; unrevised; fallback months already filled).
    Timing: uses CPI of months M−3 and M−2 only (published by the end of M−1 under D1.6, except listed shutdowns).
    Raises KeyError if a needed month is missing."""
    per = dates.to_period("M")
    c3 = cpi.reindex(per - 3).to_numpy(float)
    c2 = cpi.reindex(per - 2).to_numpy(float)
    if np.isnan(c3).any() or np.isnan(c2).any():
        miss = sorted({str(x) for x in (per - 3)[np.isnan(c3)]} | {str(x) for x in (per - 2)[np.isnan(c2)]})
        raise KeyError(f"reference CPI needs CPI months {miss[:5]}")
    d = dates.day.to_numpy(float)
    D = dates.days_in_month.to_numpy(float)
    return c3 + (d - 1.0) / D * (c2 - c3)


def tips_total_return(real_curve: pd.DataFrame, cpi: pd.Series, maturity: float, *, m: int = 2,
                      max_gap_days: int = 7, year_days: float = 365.0, prefix: str | None = "TIPSY") -> pd.DataFrame:
    """Daily nominal TR of a constant-maturity real par TIPS: (1 + R_real,t) · RefCPI_t / RefCPI_{t−1} − 1.
    Output columns: real (real TR), ratio (RefCPI_t / RefCPI_{t−1}), nominal. Deflation floor ignored (disclosed)."""
    real = par_total_return(real_curve, maturity, m=m, max_gap_days=max_gap_days, year_days=year_days, prefix=prefix)
    idx = fitted_params(real_curve).index
    rc = pd.Series(ref_cpi(idx, cpi), index=idx)
    ratio = (rc / rc.shift(1)).reindex(real.index)
    return pd.DataFrame({"real": real, "ratio": ratio, "nominal": (1.0 + real) * ratio - 1.0})
