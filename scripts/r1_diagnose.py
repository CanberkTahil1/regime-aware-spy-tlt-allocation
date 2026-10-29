"""R1 E1.2 diagnosis (reviewer R1 MINOR 3): regenerates every number in the ledger's "E1.2 diagnosis" paragraph ->
reports/r1/e12_diagnosis.json. Post-hoc DIAGNOSTIC configurations (run after the E1.2 result): registered in
reports/variants.csv as role "diagnostic", never candidates. v1's own accounting on its local data (as S0/S1).
Timing: v1's held weights shifted k extra rows (k = 0 is v1 as committed); nothing else changes."""

import contextlib
import io
import json
import os
import sys

os.environ.setdefault("MPLBACKEND", "Agg")
from tests.legacy_support import check_v1_data, yfinance_stub  # noqa: E402

sys.modules["yfinance"] = yfinance_stub()

import numpy as np  # noqa: E402

from rspy import legacy_bridge as lb  # noqa: E402
from rspy import paths  # noqa: E402

v1data = __import__("legacy.data", fromlist=["x"])
v1data.DATA_PATH = check_v1_data()
with contextlib.redirect_stdout(io.StringIO()):
    P, R = v1data.prepare_data()
scaled = lb.v1_scaled(lb.v1_signals(P, R), R)
nets = {k: lb.v1_book(scaled.shift(k).fillna(0.0), R)["net"] for k in range(4)}
held1 = scaled.shift(1).fillna(0.0)
by_hand = (held1["SPY_pos"] * R["SPY"] + held1["TLT_pos"] * R["TLT"]) - lb.V1_COST * held1.diff().abs().sum(axis=1)
out = {"s1_by_hand_vs_bridge_max_abs": float(np.abs(by_hand - nets[1]).max())}
for w, (a, z) in {"train": ("2005-01-01", "2014-12-31"), "validation": ("2015-01-01", "2019-12-31")}.items():
    out[w] = {
        "sharpe_v1_def_by_lag": {str(k): lb.v1_metrics(v, (a, z))["sharpe"] for k, v in nets.items()},
        "sharpe_v1_def_ex_2008_2009H1_by_lag": {
            str(k): lb.v1_metrics(v.drop(v.loc["2008-01-01":"2009-06-30"].index), (a, z))["sharpe"]
            for k, v in nets.items()},
        "spy_lag1_autocorr": float(R["SPY"].loc[a:z].autocorr(1)),
    }
(paths.REPORTS / "r1" / "e12_diagnosis.json").write_text(json.dumps(out, indent=1, sort_keys=True))
print(json.dumps(out, indent=1))
