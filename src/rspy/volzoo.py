"""The vol-model zoo for the vol target (D2.2): five quantkit forecasters, a yearly QLIKE + 90% MCS pick of the simplest
model, and the stitched forecast the vol target uses.

- `forecasts(r)`: h = 1 daily-variance forecasts of the log return series r (pd.Series) for every model in
  spec/rules.yaml r2.vol_zoo (quantkit `vol_forecast`, its leakage audit on), as columns; cached on disk (Parquet keyed
  by the series bytes, the model configs, the quantkit version and this file's hash: charter performance contract).
- `select(F, r, years)`: at each year-end y, losses QLIKE(r²_{t+1}, F_t) on rows whose realisation t+1 is ≤ y-end, every
  model finite and r²_{t+1} > 0 (rounded KF returns give zero days: dropped for all models together, counted); MCS
  (quantkit `vol.mcs`, size 0.10, reps 1000, block 21, seed 0, method R); pick = the first model of `selection_order`
  inside the set. Output: {y: {"pick", "included", "pvalues", "rows", "zero_proxy_dropped"}}, in year order. Years
  are computed latest first (E2.11 diagnosis): each MCS draws (reps, T) bootstrap arrays (~190 MB at T 7,500) and
  macOS keeps freed pages charged to the process, so growing T never reuses them (30 years: 2.2 GB peak); shrinking T
  does (≈ 400 MB). Each year is independent and seeded, so the order cannot change a pick.
- `stitched(F, picks, default)`: the forecast stamped t comes from pick[y − 1] for t in year y; before the first pick
  the default (selection_order[0], warm-up only).
Timing: a forecast stamped t uses returns ≤ t (quantkit convention) and is usable at t+1; the pick for year y uses
losses realised ≤ (y − 1)-end. Complexity: quantkit's (GARCH refits every 21 days), O(T·k) for QLIKE; the MCS
bootstrap O(reps·T·k) once per year.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import numpy as np
import pandas as pd
import quantkit
from quantkit import vol as qv

from rspy import paths

CLS = {"EWMAVar": qv.EWMAVar, "GarchVar": qv.GarchVar, "BetaTEgarch": qv.BetaTEgarch, "HAR": qv.HAR}


def spec() -> dict:
    return paths.rules()["r2"]["vol_zoo"]


def model(cfg: dict):
    kw = {k: v for k, v in cfg.items() if k not in ("cls", "label", "daily_variance")}
    if cfg["cls"] == "HAR":
        kw["overnight"] = False  # no OHLC: daily variance = r² only (D2.2 amendment 1)
    return CLS[cfg["cls"]](**kw)


def _key(r: pd.Series) -> str:
    h = hashlib.sha256()
    h.update(r.to_numpy(np.float64).tobytes())
    h.update(r.index.asi8.tobytes())
    h.update(json.dumps(spec()["models"], sort_keys=True).encode())
    h.update(quantkit.__version__.encode())
    h.update(pathlib.Path(__file__).read_bytes())
    return h.hexdigest()[:20]


def forecasts(r: pd.Series, cache: pathlib.Path | None = None) -> pd.DataFrame:
    cache = cache or paths.ROOT / ".cache" / "volzoo"
    f = cache / f"{_key(r)}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    data = qv.vol_data(r)
    cols = {}
    for name, cfg in spec()["models"].items():
        out = qv.vol_forecast(model(cfg), data, horizons=(1,), audit=8)
        cols[name] = out["h1"].reindex(r.index)
    F = pd.DataFrame(cols)[list(spec()["models"])]
    cache.mkdir(parents=True, exist_ok=True)
    F.to_parquet(f)
    return F


def losses(F: pd.DataFrame, r: pd.Series) -> pd.DataFrame:
    """QLIKE of the forecast stamped t against r²_{t+1}, indexed by the realisation date t+1."""
    proxy = (r**2).shift(-1)
    L = pd.DataFrame({m: qv.qlike(proxy.to_numpy(), F[m].to_numpy()) for m in F}, index=r.index)
    L.index = r.index.to_series().shift(-1).to_numpy()
    L = L.iloc[:-1]
    L.index = pd.DatetimeIndex(L.index)
    L["_proxy"] = proxy.iloc[:-1].to_numpy()
    return L


def select(F: pd.DataFrame, r: pd.Series, years) -> dict:
    s = spec()
    L = losses(F, r)
    order = s["selection_order"]
    out = {}
    for y in sorted(years, reverse=True):
        Ly = L.loc[: f"{y}-12-31"]
        fin = Ly[order].notna().all(axis=1) & np.isfinite(Ly[order]).all(axis=1)
        zero = fin & (Ly["_proxy"] <= 0)
        use = Ly.loc[fin & ~zero, order]
        m = qv.mcs(use.to_numpy(), size=s["mcs"]["size"], reps=s["mcs"]["reps"], block_size=s["mcs"]["block_size"],
                   method=s["mcs"]["method"], seed=s["mcs"]["seed"])
        inc = [order[i] for i in m["included"]]
        out[int(y)] = {"pick": next(k for k in order if k in inc), "included": inc,
                       "pvalues": dict(zip(order, map(float, m["pvalues"]), strict=True)), "rows": int(len(use)),
                       "zero_proxy_dropped": int(zero.sum()), "mean_qlike": use.mean().to_dict()}
    return dict(sorted(out.items()))


def stitched(F: pd.DataFrame, picks: dict) -> pd.Series:
    default = spec()["selection_order"][0]
    yr = F.index.year
    col = np.array([picks[y - 1]["pick"] if (y - 1) in picks else default for y in yr])
    vals = F.to_numpy()
    j = np.array([list(F.columns).index(c) for c in col])
    return pd.Series(vals[np.arange(len(F)), j], index=F.index, name="stitched")
