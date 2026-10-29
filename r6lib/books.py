"""R6 books (spec/prereg_r6.yaml candidates; D6.1–D6.3, D6.6). Every rung is built by the registered R2–R5 code
(`robust.build_core(end=…)`, `regime`, `rungs`), unchanged (R5-locked modules are imported, never edited); R6 only
composes targets (`compose`, a pure function of the parents' targets and the keeps) and books.

One line per transform (value at t uses data ≤ t; targets decided at close t, traded t + 1 by `accounting.run`):
- 5y leg: `data.build.bond_leg(read_gsw(raw), 5)` → `to_sessions` on the KF sessions (the panel's own construction);
- R6a: L2's daily target × carry(SPY trend keep) (`regime.trend_keep` column 0; the TLT column set to 1); unbanded;
- R6b: `build_core(maturity=m)` (5 and 10 years) L3/L4/L5/L7; the vol zoo re-selected on the m-year L4 book;
- R6c_L6-63: core.T["L6-63"] (R3, unchanged); R6c_infl: L5 × carry(inflation keep) (`cpi.keep`, month M reads
  CPI months ≤ M − 1); 5 pp band as L5;
- R6d: L5 × carry(trend keep with the SPY column set to 1); 5 pp band;
- R6e (D6.1): L2's target SPY weight raw_t through `asym` (cuts the same row; step-ups weekly or EWMA α = 1/3); NaN rows
  pass through without updating the state; unbanded;
- R6f (D6.3): `blend` of the L2, L3, L7 books (fund of books; monthly reset at the offset-0 trade row).
Complexity: build_core O(T·N) per maturity + one GARCH series per new L4 book (cached on disk by the vol zoo);
`asym` O(T) numba (plain reference tests/reference/r6_ref.py); `blend` O(T·K·N) plain loop.
"""

from __future__ import annotations

from dataclasses import dataclass

import numba
import numpy as np
import pandas as pd

from r6lib import cpi, spec
from rspy import paths, regime, robust, rungs
from rspy.accounting import Book
from rspy.data import build as dbuild
from rspy.data import readers

STRESS = {"1x": {}, "2x": {"cost_mult": 2.0}, "3x": {"cost_mult": 3.0}, "f75": {"stress_bp": 75.0}}
REFS = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7"]   # 25y books built (L4, L6: R6b / R6c parents)
UNBANDED = robust.UNBANDED


def end() -> str:
    return str(spec()["windows"]["test"]["end"])


# ---- data -------------------------------------------------------------------------------------------------------------
def leg5(panel: pd.DataFrame) -> pd.Series:
    """The GSW 5y constant-maturity TR on the KF sessions, built exactly as the panel's tlt<M> columns."""
    bc = paths.rules()["bonds"]
    curve = readers.read_gsw(dbuild.raw_files()["gsw_nominal"])
    r, _ = dbuild.bond_leg(curve, 5, max_gap_days=bc["max_gap_days"], m=bc["coupons_per_year"])
    return dbuild.to_sessions(r.dropna(), pd.DatetimeIndex(panel.index)).rename("tlt5")


# ---- D6.1 -----------------------------------------------------------------------------------------------------------
def week_end(index: pd.DatetimeIndex) -> np.ndarray:
    """True at the last session of each ISO calendar week (a short week: its last actual session)."""
    iso = index.isocalendar()
    key = (iso.year.to_numpy().astype(np.int64) * 100 + iso.week.to_numpy().astype(np.int64))
    return np.r_[key[1:] != key[:-1], True]


@numba.njit(cache=True)
def _asym(raw, wk, mode, alpha):  # pragma: no cover - compiled; equal to tests/reference/r6_ref.asym_ref
    out = np.full(raw.shape[0], np.nan)
    h = np.nan
    for t in range(raw.shape[0]):
        x = raw[t]
        if np.isnan(x):
            continue
        if np.isnan(h) or x < h:
            h = x
        elif mode == 0:
            if wk[t]:
                h = x
        else:
            h = h + alpha * (x - h)
        out[t] = h
    return out


def asym(raw: np.ndarray, index: pd.DatetimeIndex, mode: str) -> np.ndarray:
    """mode 'weekly' (row of record) or 'ewma5' (sensitivity, α = 2/(5 + 1))."""
    return _asym(np.ascontiguousarray(raw, np.float64), week_end(index), 0 if mode == "weekly" else 1, 1.0 / 3.0)


# ---- D6.3 -----------------------------------------------------------------------------------------------------------
def blend(books: list[Book], dec_rows: np.ndarray, *, cost_rates: np.ndarray, cost_mult: float = 1.0) -> dict:
    """Fund of K books, shares reset to 1/K at the close after each decision row (prereg_r6 candidates.R6f).
    Returns row arrays: net, held (T, N), gross_exposure, turnover, cost, financing, reset_turnover, shares (T, K)."""
    K = len(books)
    T, N = books[0].held.shape
    r = np.column_stack([b.net for b in books])
    held = np.stack([b.held for b in books], axis=0)            # (K, T, N), carried into row t
    v = np.full(K, 1.0 / K)
    shares = np.empty((T, K))
    net = np.empty(T)
    reset_to = np.zeros(T)
    reset_cost = np.zeros(T)
    for t in range(T):
        shares[t] = v
        rt = float(v @ r[t])
        u = v * (1.0 + r[t]) / (1.0 + rt)
        if t >= 1 and dec_rows[t - 1] and t + 1 < T:
            dw = ((1.0 / K - u)[:, None] * held[:, t + 1, :]).sum(axis=0)
            reset_to[t] = np.abs(dw).sum()
            reset_cost[t] = cost_mult * float(cost_rates @ np.abs(dw))
            v = np.full(K, 1.0 / K)
        else:
            v = u
        net[t] = rt - reset_cost[t]
    w = lambda name: (shares * np.column_stack([getattr(b, name) for b in books])).sum(axis=1)  # noqa: E731
    H = (shares.T[:, :, None] * held).sum(axis=0)
    return {"net": net, "held": H, "gross_exposure": (shares.T * np.abs(held).sum(axis=2)).sum(axis=0),
            "turnover": w("turnover") + reset_to, "cost": w("cost") + reset_cost, "financing": w("financing"),
            "reset_turnover": reset_to, "shares": shares}


@dataclass
class Fund:
    """Book-like view of a blend (the fields the evaluation reads)."""
    index: pd.DatetimeIndex
    net: np.ndarray
    held: np.ndarray
    turnover: np.ndarray
    cost: np.ndarray
    financing: np.ndarray
    gross_exposure: np.ndarray
    reset_turnover: np.ndarray


# ---- targets ------------------------------------------------------------------------------------------------------------
def _ones_col(k: np.ndarray, col: int) -> np.ndarray:
    k = k.copy()
    on = np.isfinite(k).all(axis=1)
    k[on, col] = 1.0
    return k


def compose(T: dict, k_trend: np.ndarray, k_infl: np.ndarray, idx: pd.DatetimeIndex) -> dict:
    """The gate / recursion candidates from the parents' daily targets T (L2, L5) and the month-end keeps (decided ≤ t;
    `regime.gate` carries them): R6a = L2 × SPY trend keep; R6c_infl = L5 × inflation keep; R6d = L5 × TLT trend keep;
    R6e = [asym(L2's SPY weight), 0]. Each target row t is traded at t + 1 by the accounting."""
    def two(col0):
        t = np.column_stack([col0, np.zeros_like(col0)])
        t[np.isnan(col0)] = np.nan
        return t

    raw = T["L2"][:, 0]
    return {"R6a_L2_trend": regime.gate(T["L2"], _ones_col(k_trend, 1)),
            "R6c_infl": regime.gate(T["L5"], k_infl),
            "R6d_L5_bondtrend": regime.gate(T["L5"], _ones_col(k_trend, 0)),
            "R6e_weekly": two(asym(raw, idx, "weekly")),
            "R6e_ewma5": two(asym(raw, idx, "ewma5"))}


GATES = {"R6a_L2_trend": ("L2", 0), "R6c_infl": ("L5", 1), "R6d_L5_bondtrend": ("L5", 1), "R6c_L6-63": ("L5", 1)}


def gate_keep(B: dict, name: str) -> np.ndarray:
    """The month-end keep each R6 gate applies to its parent (D6.6), as `compose` / R3 use it."""
    k = B["keep"]
    return {"R6a_L2_trend": _ones_col(k["trend"], 1), "R6c_infl": k["infl"], "R6d_L5_bondtrend": _ones_col(k["trend"], 0),
            "R6c_L6-63": k["corr63"]}[name]


def build(panel: pd.DataFrame, cpi_state: pd.DataFrame) -> dict:
    """Every candidate and reference book (1×, 2×, 3×, +75 bp) over 1986-01-02 → the test end."""
    e = end()
    core = robust.build_core(panel, end=e)
    core10 = robust.build_core(panel, maturity=10, end=e, l1=False)
    core5 = robust.build_core(panel.assign(tlt5=leg5(panel)), maturity=5, end=e, l1=False)
    inp, idx, rows = core.inp, core.inp.index, core.rows
    dev = np.asarray(idx >= pd.Timestamp("1990-01-01"))
    band = core.band

    k_trend = core.keep["trend"]
    k_infl = cpi.keep(idx, rows, cpi_state)
    carried = int((~np.isfinite(k_infl[rows & dev])).any(axis=1).sum())
    regime.check_coverage("R6c_infl", k_infl, rows & dev)   # raises on any undefined scored decision
    raw = core.T["L2"][:, 0]
    C = compose(core.T, k_trend, k_infl, idx)
    T = {k: (v, None if k.startswith(("R6a", "R6e")) else band, core) for k, v in C.items()}
    T["R6c_L6-63"] = (core.T["L6-63"], band, core)
    for row in spec()["candidates"]["R6b"]["rows"]:
        c = core5 if row["maturity"] == 5 else core10
        T[row["id"]] = (c.T[row["rung"]], None if row["rung"] in UNBANDED else band, c)

    books = {}
    for name, (tg, b, c) in T.items():
        books[name] = {k: rungs.book(tg, c.inp, band=b, **kw) for k, kw in STRESS.items()}
    for r in REFS:
        books[r] = {k: robust.book(core, r, **kw) for k, kw in STRESS.items()}
    kw = rungs.acc_kw()
    ids = spec()["candidates"]["R6f"]["books"]
    books["R6f_blend"] = {}
    for k, s in STRESS.items():
        f = blend([books[i][k] for i in ids], rows, cost_rates=kw["cost_rates"], cost_mult=s.get("cost_mult", 1.0))
        books["R6f_blend"][k] = Fund(idx, f["net"], f["held"], f["turnover"], f["cost"], f["financing"],
                                     f["gross_exposure"], f["reset_turnover"])
    return {"core": core, "core10": core10, "core5": core5, "books": books, "inp": inp, "rows": rows,
            "keep": {"trend": k_trend, "infl": k_infl, "corr63": core.keep["corr63"]}, "infl_carried_scored": carried,
            "raw_l2": raw}
