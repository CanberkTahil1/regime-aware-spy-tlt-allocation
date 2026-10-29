"""R1 LOCAL curve figures (owner O1.1) -> reports/figures_local/R1/<name>.png|svg, gitignored, never committed: growth +
drawdown, exposure, rolling 5-year excess Sharpe, crisis panels, all from the local daily books data/r1/books.parquet
(Yahoo/Cboe/KF-derived) written by `make reconcile`. Rolling Sharpe and crisis rebasing via rspy.site_local (tested).
Palette: the dataviz reference categorical slots 1-4 in fixed order (validated: all hard gates pass; slots 3-4 below
3:1 contrast, so every chart carries direct labels and reports/r1/reconciliation.md is the table view)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import paths, site_local  # noqa: E402

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
W = {k: [str(a), str(z)] for k, (a, z) in paths.rules()["legacy"]["windows"].items()}
wins = {k: (pd.Timestamp(a), pd.Timestamp(z)) for k, (a, z) in W.items()}

# 3. growth of $1 with drawdown underneath --------------------------------------------------------------------------------
g = books[["S0_net", "S7_net", "spy_proxy"]].dropna()
wealth = (1 + g).cumprod()
dd = wealth / wealth.cummax() - 1
fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={"height_ratios": [3, 1.3]})
for col, c, lab in [("S0_net", BLUE, "v1 as committed (S0, Yahoo/VIX, same-close, free leverage)"),
                    ("S7_net", ORANGE, "L1: v1 on permitted data + charter accounting (S7)"),
                    ("spy_proxy", NEUTRAL, "SPY proxy (KF Hi 20)")]:
    a1.plot(wealth.index, wealth[col], color=c, lw=2 if col != "spy_proxy" else 1.4, label=lab)
    if col != "spy_proxy":
        a2.plot(dd.index, dd[col], color=c, lw=1.4)
ends = wealth.iloc[-1].sort_values(ascending=False)
for k, (_col, v) in enumerate(ends.items()):  # end values, stacked so they never collide
    a1.annotate(f"${v:.1f}", (wealth.index[-1], v), xytext=(6, 10 - 11 * k), textcoords="offset points", fontsize=8,
                va="center", color=INK, arrowprops={"arrowstyle": "-", "color": BASE, "lw": 0.6})
a1.set_yscale("log")
a1.set_ylabel("growth of $1 (log)")
a2.set_ylabel("drawdown")
a2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
for k, (a, z) in wins.items():
    for ax in (a1, a2):
        ax.axvspan(a, z, color=GRID if k != "validation" else SURF, alpha=0.35, lw=0)
    a1.text(a, a1.get_ylim()[1], f" {k}", color=MUTED, fontsize=8, va="top")
a1.legend(loc="upper left", fontsize=8)
a1.set_title("Growth of $1, 2005–2025 (test 2020+ seen by owner in v1, disclosed)")
fig.text(0.01, -0.02, "L1 holds the " + TLT_LABEL + ".", color=INK2, fontsize=7)
save(fig, "growth_and_drawdown")

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
