"""Owner O1.1 local charts (as naive-vs-optimal O4.2 @ 7d48e5b, COPIED.md): curve figures and the full chart page built
from the gitignored daily series (data/r1/books.parquet: Yahoo/Cboe/KF-derived) into the gitignored
reports/site_local/ and reports/figures_local/Rn/. Never committed: tests/test_site_local.py pins the ignore rules and the
pre-commit hook refuses both paths.

- `rolling_sharpe(r, bill, window)`: trailing excess Sharpe, value at t uses rows ≤ t (window rows, ddof 1, √252).
- `rebased(df)`: growth of $1 from the first row of a window (the window's first return included).
- `bundle()`: the committed statistics bundle (rspy.site) + `series` (daily net returns of S0, L1 = S7 and the SPY proxy)
  + `rolling` (5-year excess Sharpe). Tiers: dates < 2020 "in-sample", ≥ 2020 "disclosed-reuse" (seen by owner in v1).
Timing: none of its own (ex post).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from quantkit import results as qr

from rspy import paths, site

TEST_START = "2020-01-01"


def rolling_sharpe(r: pd.Series, bill: pd.Series, window: int = 1260) -> pd.Series:
    e = (r - bill.reindex(r.index)).dropna()
    return (e.rolling(window).mean() / e.rolling(window).std(ddof=1) * np.sqrt(252)).dropna()


def rebased(df: pd.DataFrame) -> pd.DataFrame:
    return (1 + df).cumprod()


def _tiers(dates: pd.DatetimeIndex) -> pd.DataFrame:
    test = dates >= pd.Timestamp(TEST_START)
    w = paths.rules()["legacy"]["windows"]
    return pd.DataFrame({"tier": np.where(test, "disclosed-reuse", "in-sample"),
                         "window_start": np.where(test, TEST_START, str(w["train"][0])),
                         "window_end": np.where(test, str(w["test"][1]), str(w["validation"][1]))}, index=dates)


def bundle() -> qr.Bundle:
    b = site.bundle()
    books = pd.read_parquet(paths.data_dir() / "r1" / "books.parquet")
    series, rolling = [], []
    for sid, col, bill, gx, turn in [("S0", "S0_net", "bill_v1", "S0_gross_exp", "S0_turnover"),
                                     ("S7", "S7_net", "bill_new", "S7_gross_exp", "S7_turnover"),
                                     ("SPY_proxy", "spy_proxy", "bill_new", None, None)]:
        x = books[col].dropna()
        t = _tiers(x.index)
        series.append(pd.DataFrame({
            "strategy": sid, "date": x.index.strftime("%Y-%m-%d"), "freq": "D", "return_unit": "fraction",
            "gross": x.to_numpy(), "net": x.to_numpy(),
            "turnover": books[turn].reindex(x.index).to_numpy() if turn else 0.0,
            "gross_exposure": books[gx].reindex(x.index).to_numpy() if gx else 1.0,
            "tier": t["tier"].to_numpy(), "window_start": t["window_start"].to_numpy(),
            "window_end": t["window_end"].to_numpy()}))
        rs = rolling_sharpe(books[col], books[bill])
        rt = _tiers(rs.index)
        rolling.append(pd.DataFrame({
            "strategy": sid, "date": rs.index.strftime("%Y-%m-%d"), "metric": "excess Sharpe, trailing 5y",
            "value": rs.to_numpy(), "unit": "Sharpe", "tier": rt["tier"].to_numpy(),
            "window_start": rt["window_start"].to_numpy(), "window_end": rt["window_end"].to_numpy()}))
    m = dict(b.manifest)
    m["strategies"] = [*m["strategies"], {"id": "SPY_proxy", "family": "benchmark", "variant": "KF Hi 20",
                                          "frozen": True, "cost_model": "none", "gross_nav": False}]
    m["project"] = {**m["project"], "phase": "R1 (LOCAL page: series included; never committed, owner O1.1)"}
    tables = {**b.tables, "series": pd.concat(series, ignore_index=True), "rolling": pd.concat(rolling, ignore_index=True)}
    return qr.Bundle(m, tables)
