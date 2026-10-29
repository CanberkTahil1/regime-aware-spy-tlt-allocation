"""R1 statistics figures -> reports/figures/R1/<name>.png|svg (committed). Owner O1.1: only charts of committed statistics
(reports/r1/reconciliation.csv, qa.csv) are drawn here; every curve built from Yahoo/Cboe/KF-derived series is drawn by
scripts/r1_figures_local.py into the gitignored reports/figures_local/R1/ (make report-site-local).
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
W = {k: [str(a), str(z)] for k, (a, z) in paths.rules()["legacy"]["windows"].items()}

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
fig.text(0.01, -0.06, "S7 = L1 holds the " + TLT_LABEL + "; SPY = SPY proxy (KF Hi 20).", color=INK2, fontsize=7)
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
fig.text(0.01, -0.04, "L1 holds the " + TLT_LABEL + ".", color=INK2, fontsize=7)
save(fig, "cagr_waterfall_test")

# 7. data QA ---------------------------------------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"wspace": 0.75})
for ax, (pair, lab) in zip(axes, [("hi20_vs_spy", "KF Hi 20 vs SPY"), ("gsw25_vs_tlt", "GSW 25y vs TLT")], strict=True):
    r = qa[(qa.pair == pair) & (qa["sample"] == "2005-2025")].iloc[0]
    rows = qa[qa.pair == pair].set_index("sample")
    n = len(rows)
    ax.barh(range(n), rows["te_pa"], color=[BLUE, AQUA, YELLOW, ORANGE][:n], height=0.5)
    for i, (s_, v) in enumerate(rows["te_pa"].items()):
        ax.text(v, i, f" {v:.2%} (corr {rows.loc[s_, 'corr']:.3f})", va="center", fontsize=8, color=INK)
    ax.axvline(r["te_max"], color=RED, lw=1, ls="--")
    ax.set_ylim(-0.5, n - 0.1)
    ax.text(r["te_max"], n - 0.38, f" pass band ≤ {r['te_max']:.1%}", color=RED, fontsize=7, ha="left", va="center")
    ax.set_yticks(range(n), [i.replace(" (descriptive; inside test, seen)", " (test, seen)") for i in rows.index], fontsize=8)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
    ax.set_xlim(0, max(rows["te_pa"].max(), r["te_max"]) * 1.7)
    ax.set_title(f"{lab}: monthly TE ({'pass' if r['pass'] == 1 else 'FAIL'})")
fig.text(0.01, -0.04, "Local Yahoo file used only as the comparison (never committed, never used by a rung). "
         + TLT_LABEL, color=INK2, fontsize=7)
save(fig, "data_qa")
print("figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")))
