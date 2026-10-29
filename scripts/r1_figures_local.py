"""R1 LOCAL curve figures (owner O1.1) -> reports/figures_local/R1/<name>.png|svg, gitignored, never committed: growth +
drawdown, exposure, rolling 5-year excess Sharpe, crisis panels, all from the local daily books data/r1/books.parquet
(Yahoo/Cboe/KF-derived) written by `make reconcile`. Rolling Sharpe and crisis rebasing via rspy.site_local (tested).
Palette: the dataviz reference categorical slots 1-4 in fixed order (validated: all hard gates pass; slots 3-4 below
3:1 contrast, so every chart carries direct labels and reports/r1/reconciliation.md is the table view)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from quantkit import bench as qbench  # noqa: E402

from rspy import figures, paths, site_local  # noqa: E402
from rspy.data import build  # noqa: E402

BLUE, ORANGE, AQUA, YELLOW, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948"
INK, INK2, MUTED, GRID, BASE, SURF, NEUTRAL = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb", "#52514e"
OUT = paths.REPORTS / "figures_local" / "R1"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False, "font.size": 9,
                     "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": INK, "legend.frameon": False,
                     "lines.linewidth": 2})
TLT_LABEL = paths.rules()["bonds"]["label"]
STEP_NAMES = {"S0": "v1 as committed", "S1": "t+1 execution", "S2": "+ cash & financing", "S3": "+ true-turnover costs",
              "S4": "excess Sharpe", "S5": "no shorts", "S6": "VIX → realised vol", "S7": "permitted data (= L1)"}


def save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=160, bbox_inches="tight")
    plt.close(fig)


books = pd.read_parquet(paths.data_dir() / "r1" / "books.parquet")
panel_bills = build.load()[["mmy", "dt"]]
W = {k: [str(a), str(z)] for k, (a, z) in paths.rules()["legacy"]["windows"].items()}
wins = {k: (pd.Timestamp(a), pd.Timestamp(z)) for k, (a, z) in W.items()}

# 3. headline: growth of $1 with drawdown underneath (owner O2.1: quantkit viz.headline) ---------------------------------
# L1's SPY + T-bills line at matched vol (D2.8): bench.vol_matched ex ante, 63 rows, lag 1, financed above w = 1 at the
# lagged H.15 money-market yield + 25 bp, dt = calendar days / 360 (one bill series, spec/rules.yaml). Closes E1.12.
g = books[["S7_net", "S0_net", "spy_proxy", "bill_new"]].dropna()
pan = panel_bills.reindex(g.index)
acc = paths.rules()["accounting"]
line = qbench.vol_matched(g["S7_net"], g["spy_proxy"], g["bill_new"], mode="ex_ante", window=63, lag=1,
                          financing={"rate": pan["mmy"].to_numpy(), "spread": acc["financing_spread_bp"] * 1e-4,
                                     "dt": pan["dt"].to_numpy()})
g["line"] = line["returns"]
g = g.dropna()
lines = {figures.NAMES["L1"]: g["S7_net"], "v1 as committed": g["S0_net"], figures.NAMES["L0"]: g["spy_proxy"],
         figures.NAMES["L0-line"]: g["line"]}
figures.save_headline(lines, g["bill_new"], OUT, "headline_growth_and_drawdown", tier="in-sample",
                      title="v1 legacy vs v1 as committed vs SPY, 2005–2025",
                      subtitle="2005–19: v1 chose its parameters here; 2020–25: test seen by owner in v1 (disclosed)",
                      footer=figures.FOOTER + " v1 as committed = S0 (Yahoo prices + Cboe VIX, same-close, free leverage);"
                      " v1 legacy = S7 (= L1); the SPY+T-bills line is matched to v1 legacy (ex ante, 63 days).")

# 4. exposure over time (L1) ----------------------------------------------------------------------------------------------
w = books[["S7_w_SPY", "S7_w_TLT"]].dropna().resample("ME").mean()
cash = (1 - w.sum(axis=1)).clip(lower=0)
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.stackplot(w.index, w["S7_w_SPY"], w["S7_w_TLT"], cash, colors=[BLUE, ORANGE, BASE],
             labels=["SPY proxy", "TLT proxy", "cash (H.15 bills)"], edgecolor=SURF, linewidth=0.5)
ax.axhline(1.0, color=INK2, lw=0.8, ls="--")
ax.text(w.index[-1], 1.0, " gross 1.0\n (above = financed\n at bill + 25 bp)", color=INK2, fontsize=7, va="center",
        ha="left")
ax.set_ylabel("weight (monthly mean)")
ax.legend(loc="upper left", ncol=3, fontsize=8)
share_tlt = float((books["S7_w_TLT"].dropna() > 0).mean())
ax.set_title(f"L1 exposure: v1 holds the TLT proxy on {share_tlt:.0%} of days; average gross "
             f"{books['S7_gross_exp'].mean():.2f}")
fig.text(0.01, -0.03, TLT_LABEL, color=INK2, fontsize=7)
save(fig, "exposure_l1")

# 5. rolling 5-year excess Sharpe --------------------------------------------------------------------------------------------
roll = {}
for col, bill in [("S0_net", "bill_v1"), ("S7_net", "bill_new"), ("spy_proxy", "bill_new")]:
    roll[col] = site_local.rolling_sharpe(books[col], books[bill])
fig, ax = plt.subplots(figsize=(10, 3.6))
for col, c, lab in [("S0_net", BLUE, "v1 as committed"), ("S7_net", ORANGE, "L1"), ("spy_proxy", NEUTRAL, "SPY proxy")]:
    ax.plot(roll[col].index, roll[col], color=c, lw=2 if col != "spy_proxy" else 1.4, label=lab)
    last = roll[col].dropna()
    ax.annotate(f"{last.iloc[-1]:.2f}", (last.index[-1], last.iloc[-1]), xytext=(4, 0), textcoords="offset points",
                fontsize=8, va="center")
ax.axhline(0, color=BASE, lw=0.8)
ax.legend(loc="upper left", fontsize=8)
ax.set_ylabel("excess Sharpe, trailing 5y")
ax.set_title("Rolling 5-year excess Sharpe (over H.15 bills)")
fig.text(0.01, -0.03, "L1 holds the " + TLT_LABEL + ".", color=INK2, fontsize=7)
save(fig, "rolling_5y_excess_sharpe")

# 6. crisis small multiples (pre-registered windows inside 2005-2025) --------------------------------------------------
cw = {k: v for k, v in paths.prereg()["crisis_windows"].items() if str(v["start"]) >= "2005"}
fig, axes = plt.subplots(1, len(cw), figsize=(2.2 * len(cw), 2.6), sharey=False)
for ax, (k, v) in zip(axes, cw.items(), strict=True):
    a = pd.Period(str(v["start"]), "M").start_time
    z = pd.Period(str(v["end"]), "M").end_time
    seg = site_local.rebased(books.loc[a:z, ["S7_net", "spy_proxy"]].dropna())
    ax.plot(seg.index, seg["S7_net"], color=ORANGE, lw=1.8)
    ax.plot(seg.index, seg["spy_proxy"], color=NEUTRAL, lw=1.2)
    ax.set_title(k, fontsize=8)
    ax.text(0.02, 0.04, f"L1 {seg['S7_net'].iloc[-1] - 1:+.0%}\nSPY {seg['spy_proxy'].iloc[-1] - 1:+.0%}",
            transform=ax.transAxes, fontsize=7, color=INK)
    ax.tick_params(labelbottom=False, labelsize=7)
fig.suptitle("Pre-registered crisis windows: L1 (orange) vs SPY proxy (gray), growth of $1", fontsize=10,
             fontweight="bold", color=INK, y=1.06)
fig.subplots_adjust(wspace=0.35)
fig.text(0.01, -0.06, "L1 holds the " + TLT_LABEL + ".", color=INK2, fontsize=7)
save(fig, "crisis_small_multiples")

print("local figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")))
