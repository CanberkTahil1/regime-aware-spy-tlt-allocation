"""R3 research checks (reports/research/R3.md facts table): signal states only, development 1990-2019, no returns.
Run before any R3 rung existed (scratch copy at the time; committed after review R3 MINOR). Prints the table."""
import numpy as np
import pandas as pd
from quantkit.signals.trend import faber

from rspy import rungs
from rspy.data import build

p = build.load()
inp = rungs.Inputs.from_panel(p, "1986-01-02", "2019-12-31")
idx = inp.index
R = pd.DataFrame(inp.R, index=idx, columns=["spy", "tlt"])
rows = rungs.decision_rows(idx, 0)
dev = idx >= "1990-01-01"
me = rows & dev
for w in (63, 126):
    c = R.spy.rolling(w, min_periods=w).corr(R.tlt)
    cm = c[me]
    on = (cm > 0).astype(int)
    flips = int((on.diff().abs() == 1).sum())
    spells = on.groupby((on != on.shift()).cumsum()).agg(["first", "size"])
    print(f"corr{w}: month-ends {len(cm)}, share >0 {on.mean():.3f}, flips {flips} ({flips/30:.2f}/yr), "
          f"spell months median on {spells[spells['first']==1]['size'].median()} off {spells[spells['first']==0]['size'].median()}, "
          f"share >+0.2 {(cm>0.2).mean():.3f}, share >-0.2 {(cm>-0.2).mean():.3f}; daily share>0 {(c[dev]>0).mean():.3f}")
    for k, (a, z) in {"1994": ("1994-02-01", "1994-11-30"), "gfc": ("2007-10-01", "2009-03-31"), "q4_2018": ("2018-09-01", "2018-12-31")}.items():
        print(f"   {k}: month-end corr{w} values {np.round(c[me].loc[a:z].to_numpy(), 2).tolist()}; decision before window {round(float(c[me].loc[:a].iloc[-1]),2)}")
s = faber(inp.R, idx, months=10)
for j, n in enumerate(["spy", "tlt"]):
    x = pd.Series(s[:, j], idx)[dev]
    on = x.resample("ME").last()
    fl = int((on.diff().abs() == 1).sum())
    print(f"faber {n}: share of months out {1-on.mean():.3f}, switches {fl} ({fl/30:.2f}/yr)")
    for k, (a, z) in {"1994": ("1994-02-01", "1994-11-30"), "gfc": ("2007-10-01", "2009-03-31"), "q4_2018": ("2018-09-01", "2018-12-31")}.items():
        print(f"   {k}: in-trend share of days {x.loc[a:z].mean():.2f}")
c126 = R.spy.rolling(126).corr(R.tlt)[me]
tl = pd.Series(s[:, 1], idx).shift(-2)[me]
print("TLT out under L7 (corr126>0 or below SMA):", float(((c126 > 0) | (tl == 0)).mean()))
