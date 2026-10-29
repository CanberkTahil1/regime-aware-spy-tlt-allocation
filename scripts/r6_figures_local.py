"""R6 LOCAL curve figures (owner O1.1) -> reports/figures_local/R6/<name>.png|svg, gitignored, never committed: headlines
(`quantkit.viz.headline`) of the R6 candidates against VT SPY, 60/40 and SPY on the development window (tier
"in-sample") and on the test window (tier "disclosed-reuse": ideas inspired by this window); stacked exposure (SPY / TLT /
cash) of the bond-side ideas on the test window. Source: data/r6/books.parquet (KF-derived) written by `make r6`."""

import argparse
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import figures as fg  # noqa: E402
from rspy import paths  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--local", default=str(paths.data_dir() / "r6" / "books.parquet"))
ap.add_argument("--src", default=str(paths.REPORTS / "r6"))
ap.add_argument("--out", default=str(paths.REPORTS / "figures_local" / "R6"))
a = ap.parse_args()
OUT = pathlib.Path(a.out)
plt.rcParams.update(fg.RC)
b = pd.read_parquet(a.local)
W = json.loads((pathlib.Path(a.src) / "facts.json").read_text())["windows"]
# viz.headline raises on a label over ~17 characters (figures.py SHORT); these are the R6 chart names
N = {"R6a_L2_trend": "VT SPY + trend", "R6c_infl": "Infl-vol gate", "R6d_L5_bondtrend": "Bond-only trend",
     "R6b_L7@5y": "+Trend @5y", "R6b_L3@5y": "60/40 @5y", "R6f_blend": "1/3 blend", "R6e_weekly": "Asym VT weekly",
     "L2": "VT SPY", "L3": "60/40", "L5": "InvVol+VT", "L7": "+Trend", "L0": "SPY"}
KEY = ("Key: VT SPY + trend = vol-targeted SPY held only above its 10-month SMA; Infl-vol gate = InvVol+VT with TLT to "
       "cash when CPI inflation volatility is above its 10-year median (BLS CPI-U NSA); Bond-only trend = InvVol+VT with "
       "the 10-month trend rule on TLT only; +Trend @5y = the +Trend rung on a 5-year GSW leg; 1/3 blend = VT SPY, 60/40 "
       "and +Trend at one-third each, reset monthly; Asym VT weekly = VT SPY with exposure increases only on Fridays.")
tables = {}
for w, tier, sub in (("development", "in-sample", "in-sample (the ideas were suggested after seeing 2020-2026)"),
                     ("test", "disclosed-reuse", "disclosed reuse: ideas inspired by this window")):
    s = b.loc[W[w]["first"]:W[w]["last"]]
    lines = {N[r]: s[f"{r}_net"] for r in ["R6a_L2_trend", "R6c_infl", "R6d_L5_bondtrend", "R6b_L7@5y", "R6f_blend",
                                            "L2", "L3", "L5", "L0"]}
    tables[w] = fg.save_headline(lines, s["bill"], OUT, f"headline_r6_{w}", tier=tier,
                                 title=f"Ideas tried after the test, {w} {W[w]['first'][:4]}-{W[w]['last'][:4]}",
                                 subtitle=f"{W[w]['first']} to {W[w]['last']}, {sub}",
                                 footer=fg.FOOTER + " " + KEY)

s = b.loc[W["test"]["first"]:W["test"]["last"]]
rs = ["L5", "R6c_infl", "R6d_L5_bondtrend", "L7", "R6b_L7@5y"]
fig, axes = plt.subplots(len(rs), 1, figsize=(10, 8.5), sharex=True)
for ax, r in zip(axes, rs, strict=True):
    w = s[[f"{r}_w_spy", f"{r}_w_tlt"]].resample("W").last()
    cash = (1 - w.sum(axis=1)).clip(lower=0)
    ax.stackplot(w.index, w.iloc[:, 0], w.iloc[:, 1], cash, colors=[fg.BLUE, fg.ORANGE, fg.GRID], lw=0)
    ax.set_ylim(0, 1)
    ax.set_ylabel(N[r], rotation=0, ha="right", va="center")
axes[0].legend(["SPY", "TLT (or 5y leg)", "cash"], fontsize=8, ncol=3, loc="upper right")
fig.suptitle("Exposure over the test window, bond-side ideas (held weights, weekly; disclosed reuse)", fontsize=10,
             fontweight="bold", color=fg.INK)
fg.save(fig, OUT, "exposure_bond_ideas_test")
print("R6 local figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")), "| headline Sharpe:",
      {w: {k: round(v["sharpe"], 3) for k, v in t.items()} for w, t in tables.items()})
