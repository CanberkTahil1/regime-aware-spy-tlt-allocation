"""R1 figures -> reports/figures/R1/<name>.png|svg. Draws only saved outputs: reports/r1/reconciliation.csv, qa.csv and
the local daily books data/r1/books.parquet written by `make reconcile` (nothing is recomputed here except
cumulative products, drawdowns and rolling statistics of those saved series).
Palette: the dataviz reference categorical slots 1-4 in fixed order (validated: all hard gates pass; slots 3-4 below
3:1 contrast, so every chart carries direct labels and reports/r1/reconciliation.md is the table view)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import paths  # noqa: E402

BLUE, ORANGE, AQUA, YELLOW, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948"
INK, INK2, MUTED, GRID, BASE, SURF, NEUTRAL = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb", "#52514e"
OUT = paths.REPORTS / "figures" / "R1"
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


tab = pd.read_csv(paths.REPORTS / "r1" / "reconciliation.csv")
qa = pd.read_csv(paths.REPORTS / "r1" / "qa.csv")
books = pd.read_parquet(paths.data_dir() / "r1" / "books.parquet")
W = {k: [str(a), str(z)] for k, (a, z) in paths.rules()["legacy"]["windows"].items()}
wins = {k: (pd.Timestamp(a), pd.Timestamp(z)) for k, (a, z) in W.items()}

# 1. reconciliation: Sharpe and CAGR by step, one panel per window ------------------------------------------------------
fig, axes = plt.subplots(2, 3, figsize=(12, 6), sharex=True)
steps = list(STEP_NAMES)
for j, w in enumerate(["train", "validation", "test"]):
    t = tab[tab.window == w].set_index("step").loc[steps]
    for i, (col, fmt, lab) in enumerate([("sharpe", "{:.2f}", "Sharpe"), ("cagr", "{:.1%}", "CAGR")]):
        ax = axes[i, j]
        ax.plot(range(8), t[col], color=BLUE, marker="o", markersize=5)
        for k in (0, 7):
            ax.annotate(fmt.format(t[col].iloc[k]), (k, t[col].iloc[k]), textcoords="offset points",
                        xytext=(0, 7), ha="center", color=INK, fontsize=8)
        ax.axvline(3.5, color=MUTED, lw=0.8, ls="--")
        if i == 0:
            ax.set_title(f"{w} ({W[w][0][:4]}–{W[w][1][:4]}){' — seen in v1' if w == 'test' else ''}")
            ax.text(3.6, ax.get_ylim()[1], "metric → excess", color=MUTED, fontsize=7, va="top")
        if j == 0:
            ax.set_ylabel(lab)
        if col == "cagr":
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
for ax in axes[1]:
    ax.set_xticks(range(8), steps)
fig.suptitle("v1 → L1, one correction per step (S0–S3: v1's Sharpe without rf; S4+: excess Sharpe)", color=INK,
             fontsize=11, fontweight="bold")
fig.text(0.01, -0.02, "Steps: " + "; ".join(f"{k} {v}" for k, v in STEP_NAMES.items())
         + ". Order fixed before results (D1.4); attribution is order-dependent.", color=INK2, fontsize=7, wrap=True)
save(fig, "reconciliation_by_step")

# 2. test-window CAGR waterfall --------------------------------------------------------------------------------------------
t = tab[tab.window == "test"].set_index("step").loc[steps, "cagr"]
d = t.diff().iloc[1:]
fig, ax = plt.subplots(figsize=(9, 3.8))
x = np.arange(len(steps))
ax.bar(0, t.iloc[0], color=BLUE, width=0.6)
cum = t.iloc[0]
for i, v in enumerate(d.to_numpy(), start=1):
    ax.bar(i, v, bottom=cum, color=BLUE if v >= 0 else RED, width=0.6)
    ax.annotate(f"{v:+.1%}", (i, cum + max(v, 0)), textcoords="offset points", xytext=(0, 3), ha="center", fontsize=8,
                color=INK)
    cum += v
ax.bar(len(steps), t.iloc[-1], color=ORANGE, width=0.6)
ax.annotate(f"{t.iloc[0]:.1%}", (0, t.iloc[0]), textcoords="offset points", xytext=(0, 3), ha="center", fontsize=8)
ax.annotate(f"{t.iloc[-1]:.1%}", (len(steps), t.iloc[-1]), textcoords="offset points", xytext=(0, 3), ha="center",
            fontsize=8)
ax.set_xticks(list(x) + [len(steps)], ["S0\nv1"] + [f"{k}" for k in steps[1:]] + ["L1"])
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
ax.set_ylim(min(0.10, t.min() - 0.02), t.max() + 0.02)
ax.set_title("Test window 2020–2025 (seen by owner in v1, disclosed): CAGR change per correction")
save(fig, "cagr_waterfall_test")

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
    e = (books[col] - books[bill]).dropna()
    roll[col] = e.rolling(1260).mean() / e.rolling(1260).std() * np.sqrt(252)
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
save(fig, "rolling_5y_excess_sharpe")

# 6. crisis small multiples (pre-registered windows inside 2005-2025) --------------------------------------------------
cw = {k: v for k, v in paths.prereg()["crisis_windows"].items() if str(v["start"]) >= "2005"}
fig, axes = plt.subplots(1, len(cw), figsize=(2.2 * len(cw), 2.6), sharey=False)
for ax, (k, v) in zip(axes, cw.items(), strict=True):
    a = pd.Period(str(v["start"]), "M").start_time
    z = pd.Period(str(v["end"]), "M").end_time
    seg = (1 + books.loc[a:z, ["S7_net", "spy_proxy"]].dropna()).cumprod()
    ax.plot(seg.index, seg["S7_net"], color=ORANGE, lw=1.8)
    ax.plot(seg.index, seg["spy_proxy"], color=NEUTRAL, lw=1.2)
    ax.set_title(k, fontsize=8)
    ax.text(0.02, 0.04, f"L1 {seg['S7_net'].iloc[-1] - 1:+.0%}\nSPY {seg['spy_proxy'].iloc[-1] - 1:+.0%}",
            transform=ax.transAxes, fontsize=7, color=INK)
    ax.tick_params(labelbottom=False, labelsize=7)
fig.suptitle("Pre-registered crisis windows: L1 (orange) vs SPY proxy (gray), growth of $1", fontsize=10,
             fontweight="bold", color=INK, y=1.06)
fig.subplots_adjust(wspace=0.35)
save(fig, "crisis_small_multiples")

# 7. data QA ---------------------------------------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"wspace": 0.75})
for ax, (pair, lab) in zip(axes, [("hi20_vs_spy", "KF Hi 20 vs SPY"), ("gsw25_vs_tlt", "GSW 25y vs TLT")], strict=True):
    r = qa[(qa.pair == pair) & (qa["sample"] == "2005-2025")].iloc[0]
    rows = qa[qa.pair == pair].set_index("sample")
    ax.barh(range(3), rows["te_pa"], color=[BLUE, AQUA, YELLOW], height=0.5)
    for i, (s_, v) in enumerate(rows["te_pa"].items()):
        ax.text(v, i, f" {v:.2%} (corr {rows.loc[s_, 'corr']:.3f})", va="center", fontsize=8, color=INK)
    ax.axvline(r["te_max"], color=RED, lw=1, ls="--")
    ax.set_ylim(-0.5, 2.9)
    ax.text(r["te_max"], 2.62, f" pass band ≤ {r['te_max']:.1%}", color=RED, fontsize=7, ha="left", va="center")
    ax.set_yticks(range(3), list(rows.index), fontsize=8)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
    ax.set_xlim(0, max(rows["te_pa"].max(), r["te_max"]) * 1.7)
    ax.set_title(f"{lab}: monthly TE ({'pass' if r['pass'] == 1 else 'FAIL'})")
fig.text(0.01, -0.04, "Local Yahoo file used only as the comparison (never committed, never used by a rung). "
         + TLT_LABEL, color=INK2, fontsize=7)
save(fig, "data_qa")
print("figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")))
