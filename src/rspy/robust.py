"""R4 robustness and the three O3.1 zoo rows (D4.1–D4.7; spec/prereg.yaml r4_zoo / r4_evaluation, rules.yaml r4).

Every R4 number is descriptive (no walk, no promotion). One line per transform (value at t uses data ≤ t):
- `build_core(panel, maturity, band, quarterly)`: the ladder L0–L8 (+ L5-lev) rebuilt with R2/R3's own functions
  (`rungs`, `volzoo`, `regime.targets`) on one TLT leg (GSW `maturity`-year proxy in place of the 25-year one, D4.5),
  one band width and one decision calendar (quarterly = the offset-0 month-end rows of Mar/Jun/Sep/Dec, D4.5
  amendment 3). At (25, 0.05, monthly) every target equals R2/R3's (checked by the script against data/r2, data/r3);
- `overlay_keep(...)` (D4.1): v1's frozen `legacy/signals/{spread,bollinger}.py` on the L1/S7 inputs; a signal stamped
  t (v1 code: z_t / ratio_t against the window ending at t − 1) sets keep_t = [SPY_pos ≠ 0, TLT_pos ≥ 0]: z > th (or
  ratio above the upper band) ⇒ SPY to cash, z < −th (below the lower band) ⇒ TLT to cash, else 1; applied to L5's
  daily target through `regime.gate` (decided ≤ t, traded t + 1);
- `gbm_design(core)` (D4.2): features at row t from data ≤ t; label y_t = log √(252·mean r²) of the L4 book's daily log
  net return over rows t + 2 … t + 22 (label_end_t = t + 22); `gbm_predict` fits one fixed-parameter LightGBM per
  year-end y (1989 … 2018) through `quantkit.ml.fit_cv` on hand-built walk-forward `cv.Split`s (train = label_end ≤
  last row of y, test = year y + 1, purge 22, embargo 0; `cv.check_split` on each); `gbm_sigma` blends
  log σ = log σ_zoo + h·(log σ_gbm − log σ_zoo); rows without a prediction (warm-up, and the last 22 development rows
  whose label is undefined) keep σ_zoo (= L5's sizing, counted and disclosed);
- `waterfall(book, bill)` (D4.4): per-day identity gross + cash − cost − financing = net, split by sleeve cost; the
  vol drag apart: (1 + mean daily net)^252 − 1 − CAGR (≥ 0);
- `v1_grid_net(...)` (D4.6): v1's 648 grid configs on the L1/S7 path (permitted data, realised-vol proxy, charter
  accounting), for the DSR trial pool.
Complexity: build_core O(T·N) plus the vol zoo (cached Parquet forecasts; picks cached as JSON by the series key);
GBM 30 fits × 200 trees on ≤ 8,600 rows; v1 grid 648 × O(T) in a process pool.
"""

from __future__ import annotations

import itertools
import json
import math
import pathlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from rspy import paths, regime, rungs, volzoo

ANN = 252


def spec() -> dict:
    return paths.rules()["r4"]


# ---- the ladder on one (maturity, band, calendar) --------------------------------------------------------------------
@dataclass
class Core:
    panel: pd.DataFrame
    inp: rungs.Inputs
    rows: np.ndarray
    dev: np.ndarray
    band: float
    T: dict
    s5: pd.Series
    r4: pd.Series
    keep: dict
    rt: dict | None = None


UNBANDED = ("L0", "L1", "L2")


def leg_panel(panel: pd.DataFrame, maturity: int) -> pd.DataFrame:
    """The panel with the TLT leg replaced by the GSW `maturity`-year proxy (D4.5); asserts it is reported from the
    1986 warm-up start (D4.5 amendment 1)."""
    if maturity == paths.rules()["bonds"]["maturity_years"]:
        return panel
    col = f"tlt{maturity}"
    seg = panel.loc["1986-01-02":"2019-12-31", col]
    if seg.isna().any():
        raise ValueError(f"{col} is not reported on every session 1986-01-02 .. 2019-12-31")
    return panel.assign(tlt25=panel[col])


def picks_cached(F: pd.DataFrame, r: pd.Series, years) -> dict:
    """`volzoo.select` cached as JSON by the forecast series key (performance contract: shared inputs built once)."""
    f = paths.ROOT / ".cache" / "volzoo" / f"picks_{volzoo._key(r)}_{min(years)}_{max(years)}.json"
    if f.exists():
        return {int(k): v for k, v in json.loads(f.read_text()).items()}
    out = volzoo.select(F, r, years)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, default=float))
    return out


def decision_rows(index: pd.DatetimeIndex, quarterly: bool = False) -> np.ndarray:
    """The record-offset month-end decision rows; quarterly = those in Mar/Jun/Sep/Dec (D4.5 amendment 3)."""
    rows = rungs.decision_rows(index, paths.rules()["r2"]["tranche"]["record"])
    return rows & np.isin(index.month, spec()["sensitivity"]["quarter_months"]) if quarterly else rows


def build_core(panel: pd.DataFrame, *, maturity: int = 25, band: float | None = None, quarterly: bool = False,
               l1: bool = True) -> Core:
    R2 = paths.rules()["r2"]
    sc = paths.rules()["r4"]["scored"]
    B = R2["band"]["width"] if band is None else float(band)
    p = leg_panel(panel, maturity)
    inp = rungs.Inputs.from_panel(p, "1986-01-02", str(sc[1]))
    idx = inp.index
    dev = np.asarray(idx >= pd.Timestamp(str(sc[0])))
    rows = decision_rows(idx, quarterly)
    T = {"L0": rungs.l0_target(inp), "L2": rungs.l2_target(inp), "L3": rungs.l3_target(inp, rows),
         "L4": rungs.l4_target(inp, rows)}
    if l1:
        T["L1"] = rungs.l1_target(p, inp)
    r4 = rungs.log_book_returns(rungs.book(T["L4"], inp, band=B))
    F4 = volzoo.forecasts(r4)
    s5 = volzoo.stitched(F4, picks_cached(F4, r4, range(1989, int(str(sc[1])[:4]))))
    T["L5"] = rungs.vol_target(T["L4"], s5, idx, R2["L5"]["target_vol"], R2["L5"]["cap"])
    T["L5-lev"] = rungs.vol_target(T["L4"], s5, idx, R2["L5-lev"]["target_vol"], R2["L5-lev"]["cap"])
    RT = regime.targets(inp, rows, dev, T["L5"], band=B)
    for k in ("corr126", "trend"):
        regime.check_coverage(k, RT["keep"][k], rows & dev)
    T.update(RT["targets"])  # L6, L7, L8 and R3's descriptive rows (L6-63, L6-th±0.2, L7-on-L5, L7-63)
    return Core(p, inp, rows, dev, B, T, s5, r4, RT["keep"], RT)


def book(core: Core, name: str, target=None, *, cost_mult: float = 1.0, stress_bp: float = 0.0):
    tg = core.T[name] if target is None else target
    return rungs.book(tg, core.inp, band=None if name in UNBANDED else core.band, cost_mult=cost_mult,
                      stress_bp=stress_bp)


# ---- D4.1: v1 overlays ------------------------------------------------------------------------------------------------
def _v1_inputs(panel: pd.DataFrame, inp: rungs.Inputs):
    lb = rungs._legacy()
    w = paths.rules()["legacy"]["vix_proxy"]["window"]
    start = panel.loc[: inp.index[0] - pd.Timedelta(days=7)].index[-1]
    prices, rets, _ = lb.new_data_inputs(panel, start, inp.index[-1], w)
    return lb, prices, rets


def overlay_keep(panel: pd.DataFrame, inp: rungs.Inputs, kind: str) -> np.ndarray:
    """(T, 2) keep from v1's frozen signal state stamped t (D4.1): SPY_pos == 0 ⇒ SPY to cash; TLT_pos < 0 ⇒ TLT to
    cash; else keep. Rows before v1's first signal row keep both (warm-up only)."""
    lb, prices, rets = _v1_inputs(panel, inp)
    c = spec()["overlays"][kind]
    if kind == "spread":
        sig = lb._legacy("signals.spread").generate_spread_signals(rets, window=c["window"], threshold=c["threshold"])
    elif kind == "bollinger":
        sig = lb._legacy("signals.bollinger").generate_bollinger_signals(prices[["SPY", "TLT"]], window=c["window"],
                                                                          num_std=c["num_std"])
    else:
        raise ValueError(kind)
    sig = sig.reindex(inp.index)
    keep = np.ones((len(inp.index), 2))
    keep[(sig["SPY_pos"] == 0).to_numpy(), 0] = 0.0
    keep[(sig["TLT_pos"] < 0).to_numpy(), 1] = 0.0
    return keep


# ---- D4.2: GBM risk-side sizing ------------------------------------------------------------------------------------
def _log_rv(r2: pd.Series, w: int) -> pd.Series:
    return 0.5 * np.log(ANN * r2.rolling(w, min_periods=w).mean())


def gbm_design(core: Core) -> dict:
    """X (T, 7) features at row t (data ≤ t), y (T,) label over rows t + 2 … t + 22, label_end (T,) = t + 22; NaN where
    undefined. The L4 book's log net return is aligned to the session index (NaN before its first invested row)."""
    g = spec()["gbm"]
    idx = core.inp.index
    r = core.r4.reindex(idx)
    r2 = r**2
    f = core.s5.reindex(idx)
    X = {"log_sigma_zoo": 0.5 * np.log(ANN * f)}
    for w in g["rv_windows"]:
        X[f"log_rv{w}"] = _log_rv(r2, w)
    X["corr63"] = pd.Series(regime.corr(core.inp, g["corr_window"]), index=idx)
    spy = pd.Series(core.inp.R[:, 0], index=idx)
    X["spy_ret21"] = np.exp(np.log1p(spy).rolling(g["ret_window"], min_periods=g["ret_window"]).sum()) - 1
    X["mmy"] = pd.Series(core.inp.mmy, index=idx)
    X = pd.DataFrame(X)
    h, lag = g["horizon"], g["label_lag"]
    end = h + lag - 1                                       # = 22: label rows t + 2 … t + 22
    y = _log_rv(r2, h).shift(-end)
    return {"X": X, "y": y, "label_end": np.arange(len(idx)) + end}


def gbm_splits(idx: pd.DatetimeIndex, rows: np.ndarray, label_end_full: np.ndarray, years) -> tuple[list, np.ndarray]:
    """Walk-forward purged splits over the usable positions `rows` (contiguous, sorted): groups = calendar years;
    split for year-end y: test = rows of year y + 1, train = rows whose label ends ≤ the last session of year y."""
    from quantkit.cv import Split

    g = spec()["gbm"]
    pos = np.asarray(rows)
    if not (np.diff(pos) == 1).all():
        raise ValueError("GBM rows must be contiguous")
    yrs = idx[pos].year
    groups = sorted(set(yrs))
    bounds = tuple((int(np.flatnonzero(yrs == u)[0]), int(np.flatnonzero(yrs == u)[-1])) for u in groups)
    le = label_end_full[pos] - pos[0]                      # label end in local positions
    last_full = {u: int(np.flatnonzero(idx.year == u)[-1]) for u in set(idx.year)}
    out = []
    n = len(pos)
    for y in years:
        if y + 1 not in groups:
            continue
        k = groups.index(y + 1)
        test = np.zeros(n, bool)
        test[bounds[k][0]: bounds[k][1] + 1] = True
        train = label_end_full[pos] <= last_full[y]
        out.append(Split(train=train, test=test, test_groups=(k,), bounds=bounds, purge=g["purge"],
                         embargo=g["embargo"], label_end=le))
    return out, le


def gbm_predict(core: Core, *, n_jobs: int = 1) -> dict:
    """Out-of-sample log σ_gbm per session (NaN where no split tested the row). Every split passes `check_split`."""
    from quantkit.cv import check_split
    from quantkit.ml import fit_cv, lightgbm

    g = spec()["gbm"]
    D = gbm_design(core)
    X, y = D["X"].to_numpy(), D["y"].to_numpy()
    ok = np.isfinite(X).all(axis=1) & np.isfinite(y)
    pos = np.flatnonzero(ok)
    if not (np.diff(pos) == 1).all():
        raise ValueError("a usable GBM row is followed by an unusable one inside the sample")
    years = range(g["refit_years"][0], g["refit_years"][1] + 1)
    cv, le = gbm_splits(core.inp.index, pos, D["label_end"], years)
    for sp in cv:
        check_split(sp, g["purge"], g["embargo"], le)
    model = lightgbm("regression", **g["params"])
    fr = fit_cv(model, X[pos], y[pos], cv=cv, label_end=le, purge=g["purge"], embargo=g["embargo"], seed=g["seed"],
                n_jobs=n_jobs, threads=g["threads"])
    pred = np.full(len(core.inp.index), np.nan)
    for s in fr.splits:
        pred[pos[s.test_rows]] = s.pred
    return {"log_sigma_gbm": pred, "n_usable": int(len(pos)), "n_splits": len(cv),
            "dropped_dev_rows": int((core.dev & ~np.isfinite(pred)).sum()), "flags": fr.flags,
            "first_pred": str(core.inp.index[np.isfinite(pred)][0].date()), "cv": cv, "label_end": le}


def gbm_sigma(core: Core, log_sigma_gbm: np.ndarray, haircut: float) -> np.ndarray:
    """Annualised σ used for sizing: exp(log σ_zoo + h·(log σ_gbm − log σ_zoo)); σ_zoo where no prediction."""
    lz = 0.5 * np.log(ANN * core.s5.reindex(core.inp.index).to_numpy())
    lg = np.where(np.isfinite(log_sigma_gbm), log_sigma_gbm, lz)
    return np.exp(lz + (1.0 - haircut) * (lg - lz))


def gbm_target(core: Core, sigma: np.ndarray) -> np.ndarray:
    g = spec()["gbm"]
    return rungs.vol_scaled(rungs.carry(core.T["L4"]), sigma**2 / ANN, g["target_vol"], g["cap"])


# ---- D4.4: loss waterfall -------------------------------------------------------------------------------------------
def waterfall(bk, bk_spy_cost_only, bill) -> dict:
    """Per-day identity gross + cash − cost − financing = net (checked ≤ 1e-10), annualised arithmetic means;
    cost split by sleeve via a book with the TLT cost rate at 0 (the cost never moves the path: drift ignores it)."""
    resid = bk.gross + bk.cash - bk.cost - bk.financing - bk.net
    if np.abs(resid).max() > 1e-10:
        raise AssertionError(f"waterfall identity broken: {np.abs(resid).max():.2e}")
    if not np.array_equal(bk.held, bk_spy_cost_only.held):
        raise AssertionError("the cost split changed the path")
    c_spy = bk_spy_cost_only.cost
    a = lambda v: float(np.mean(v) * ANN)  # noqa: E731
    n = len(bk.net)
    cagr = float(np.prod(1 + bk.net) ** (ANN / n) - 1)
    return {"gross_pa": a(bk.gross), "cash_pa": a(bk.cash), "cost_spy_pa": a(c_spy), "cost_tlt_pa": a(bk.cost - c_spy),
            "financing_pa": a(bk.financing), "net_pa": a(bk.net), "bill_pa": a(bill),
            "excess_pa": a(bk.net - np.asarray(bill)), "cagr": cagr,
            # vol drag = the mean daily return compounded over a year minus the CAGR (≥ 0 by AM–GM); the arithmetic
            # mean·252 − CAGR also contains the compounding of the mean and can be negative for low-vol books
            "compounded_mean_pa": float((1 + np.mean(bk.net)) ** ANN - 1),
            "vol_drag_pa": float((1 + np.mean(bk.net)) ** ANN - 1) - cagr, "max_resid": float(np.abs(resid).max())}


# ---- D4.6: v1's grid on permitted data ------------------------------------------------------------------------------
def v1_grid() -> list[pd.Series]:
    cfg = rungs._legacy()._legacy("config")
    keys = ("z", "th", "sw", "sth", "ddw", "ddt", "cw")
    space = itertools.product(cfg.Z_WINDOWS, cfg.THRESHOLDS, cfg.SLOW_WINDOWS, cfg.SLOW_THRESHOLDS, cfg.DD_WINDOWS,
                              cfg.DD_THRESHOLDS, cfg.CRASH_WEIGHTS)
    return [pd.Series(dict(zip(keys, v, strict=True))) for v in space]


def v1_target_for(panel: pd.DataFrame, inp: rungs.Inputs, params: pd.Series) -> np.ndarray:
    """`rungs.l1_target` with v1's parameters replaced (the L1/S7 path; v1 code unedited)."""
    lb, prices, rets = _v1_inputs(panel, inp)
    run = lb._legacy("run")
    sig = run.build_strategy_from_params(params)(rets, prices.loc[rets.index])
    R = pd.DataFrame(inp.R, index=inp.index, columns=["SPY", "TLT"])
    return rungs.v1_target(lb.v1_scaled(sig.reindex(inp.index).fillna(0.0), R))


def _grid_worker(args):
    panel_path, params_list = args
    panel = pd.read_parquet(panel_path)
    sc = spec()["scored"]
    inp = rungs.Inputs.from_panel(panel, "1986-01-02", str(sc[1]))
    dev = np.asarray(inp.index >= pd.Timestamp(str(sc[0])))
    return [rungs.book(v1_target_for(panel, inp, p), inp).net[dev].astype(np.float64) for p in params_list]


def v1_grid_net(panel_path: pathlib.Path, *, workers: int = 4, grid: list | None = None) -> np.ndarray:
    """(T_dev, 648) development net returns of v1's grid on the L1/S7 path; grid order = v1's `product` order;
    chunks are contiguous, so 1 vs N workers give the same columns (each config is deterministic)."""
    from joblib import Parallel, delayed  # loky: children never re-run the calling script (spawn would)

    grid = v1_grid() if grid is None else grid
    k = max(1, math.ceil(len(grid) / workers))
    chunks = [(panel_path, grid[i:i + k]) for i in range(0, len(grid), k)]
    if workers == 1:
        res = [_grid_worker(c) for c in chunks]
    else:
        res = Parallel(n_jobs=workers, backend="loky")(delayed(_grid_worker)(c) for c in chunks)
    return np.column_stack([x for part in res for x in part])
