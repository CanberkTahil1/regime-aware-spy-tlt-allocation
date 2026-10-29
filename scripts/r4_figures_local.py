"""R4 LOCAL curve figures (owner O1.1) -> reports/figures_local/R4/<name>.png|svg, gitignored, never committed: the
headline (`quantkit.viz.headline`) of the core mix with the three O3.1 zoo rows, 60/40, v1, SPY and the SPY+T-bills line;
the headline of the built rungs; rolling 5-year ΔSharpe of each layer vs its parent (matched once); the overlays' and the
GBM row's exposure. Source: data/r4/{books,rolling}.parquet (KF-derived) written by `make ladder`. Development 1990–2019
only (in-sample, descriptive; built rungs, none promoted)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import figures as fg  # noqa: E402
from rspy import paths  # noqa: E402

plt.rcParams.update(fg.RC)
OUT = paths.REPORTS / "figures_local" / "R4"
N = {**fg.NAMES, **fg.NAMES_R3, **fg.NAMES_R4}
b = pd.read_parquet(paths.data_dir() / "r4" / "books.parquet")
roll = pd.read_parquet(paths.data_dir() / "r4" / "rolling.parquet")
PAR = paths.prereg()["r4_evaluation"]["parents"]
SUB = "Development 1990–2019 (in-sample, descriptive; built rungs, none promoted; zoo rows never promoted)"

# 1. headline: the core mix and the three O3.1 zoo rows ------------------------------------------------------------------
lines = {N["gbm_risk_sizing"]: b["gbm_risk_sizing_net"], N["v1_spread_overlay_on_L5"]: b["v1_spread_overlay_on_L5_net"],
         N["v1_bollinger_overlay_on_L5"]: b["v1_bollinger_overlay_on_L5_net"], N["L5"]: b["L5_net"],
         N["L3"]: b["L3_net"], N["L0"]: b["L0_net"], N["L0-line"]: b["L5_line"]}
t1 = fg.save_headline(lines, b["bill"], OUT, "headline_zoo_rows", tier="in-sample",
                      title="The O3.1 zoo rows vs the core mix (InvVol+VT), 60/40 and SPY, 1990–2019",
                      subtitle=SUB + ". SPY+T-bills line matched ex ante to InvVol+VT")

# 2. headline: the built rungs --------------------------------------------------------------------------------------------
lines = {N["L5"]: b["L5_net"], N["L6"]: b["L6_net"], N["L7"]: b["L7_net"], N["L4"]: b["L4_net"], N["L3"]: b["L3_net"],
         N["L2"]: b["L2_net"], N["L1"]: b["L1_net"], N["L0"]: b["L0_net"]}
t2 = fg.save_headline(lines, b["bill"], OUT, "headline_built_rungs", tier="in-sample",
                      title="The built rungs, 1990–2019 (none promoted)", subtitle=SUB)

# 3. rolling 5-year ΔSharpe of each layer vs its parent ---------------------------------------------------------------------
cols = [(r, f"{r}_vs_{p}_dsr") for r, p in PAR.items() if f"{r}_vs_{p}_dsr" in roll]
fig, axes = plt.subplots(len(cols), 1, figsize=(10, 1.25 * len(cols)), sharex=True)
for ax, (r, col) in zip(axes, cols, strict=True):
    s = roll[col].dropna()
    ax.fill_between(s.index, 0, s, where=s > 0, color=fg.BLUE, alpha=0.5, lw=0)
    ax.fill_between(s.index, 0, s, where=s <= 0, color=fg.RED, alpha=0.5, lw=0)
    ax.axhline(0, color=fg.BASE, lw=0.8)
    ax.set_ylabel(f"{r} vs {PAR[r]}", rotation=0, ha="right", va="center", fontsize=8)
    ax.tick_params(labelsize=7)
fig.suptitle("Rolling 5-year ΔSharpe of each layer vs its parent (parent matched once to the layer's development vol)",
             fontsize=10, fontweight="bold", color=fg.INK, y=1.0)
fg.save(fig, OUT, "rolling_5y_dsharpe_vs_parent")

# 4. exposure of the zoo rows vs L5 ------------------------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(10, 4.6), sharex=True)
gs = b[["L5_w_spy", "L5_w_tlt"]].sum(axis=1).resample("ME").mean()
axes[0].plot(gs.index, gs, color=fg.NEUTRAL, lw=1.2, label="InvVol+VT gross (monthly mean)")
axes[0].set_ylabel("gross weight")
axes[0].legend(fontsize=8)
axes[0].set_title("L5's gross exposure (the vol layer the GBM row re-sizes; GBM weights are not stored, see zoo.csv)", fontsize=9)
for k, colr in [("v1_spread_overlay_on_L5", fg.ORANGE), ("v1_bollinger_overlay_on_L5", fg.BLUE), ("gbm_risk_sizing", fg.AQUA)]:
    d = (b[f"{k}_net"] - b["L5_net"]).rolling(252).std() * 252**0.5
    axes[1].plot(d.index, d, color=colr, lw=1.1, label=fg.SHORT[N[k]])
axes[1].set_ylabel("tracking error vs L5\n(trailing 1y, ann.)")
axes[1].legend(fontsize=8, ncol=3)
fg.save(fig, OUT, "zoo_rows_tracking_vs_L5")
print("R4 local figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")), "| headline:",
      {k: round(v["sharpe"], 3) for k, v in t1.items()})
