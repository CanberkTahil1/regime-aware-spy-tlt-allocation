"""R3 LOCAL curve figures (owner O1.1) -> reports/figures_local/R3/<name>.png|svg, gitignored, never committed: the
headline (`quantkit.viz.headline`, owner labels SPY, v1, 60/40, InvVol+VT, +CorrReg, +Trend, +Crash, SPY+bills), stacked
exposure of L5/L6/L7 with the correlation regime shaded, the owner's crisis windows (1994, GFC, Q4 2018) as growth of $1,
rolling 5-year excess Sharpe. Source: data/r3/books.parquet (KF-derived) written by `make ladder`. Development 1990–2019
only (in-sample, descriptive)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import figures as fg  # noqa: E402
from rspy import paths, site_local  # noqa: E402

plt.rcParams.update(fg.RC)
OUT = paths.REPORTS / "figures_local" / "R3"
N = {**fg.NAMES, **fg.NAMES_R3}
b = pd.read_parquet(paths.data_dir() / "r3" / "books.parquet").loc["1990-01-01":"2019-12-31"]
TLT = paths.rules()["bonds"]["label"]

# 1. headline: the regime layers first (emphasised: +Crash = the full ladder) -------------------------------------------
lines = {N["L8"]: b["L8_net"], N["L7"]: b["L7_net"], N["L6"]: b["L6_net"], N["L5"]: b["L5_net"], N["L3"]: b["L3_net"],
         N["L1"]: b["L1_net"], N["L0"]: b["L0_net"], N["L0-line"]: b["L8_line"]}
tab = fg.save_headline(lines, b["bill"], OUT, "headline_growth_and_drawdown", tier="in-sample",
                       title="The regime layers vs the core mix, 60/40, v1 and SPY, 1990–2019",
                       subtitle="Development window (in-sample, descriptive; no promotion walk). SPY+T-bills line "
                                "matched ex ante to +Crash (the full ladder L8)")

# 2. exposure over time (L5, L6, L7) with the trailing 126-day correlation > 0 shaded --------------------------------------
pos = (b["corr126_gate"] == 0).resample("ME").mean() > 0.5  # the L6 gate as traded (review R3 MINOR: not raw corr)
fig, axes = plt.subplots(3, 1, figsize=(10, 7.6), sharex=True)
for ax, r in zip(axes, ["L5", "L6", "L7"], strict=True):
    w = b[[f"{r}_w_spy", f"{r}_w_tlt"]].resample("ME").mean()
    cash = (1 - w.sum(axis=1)).clip(lower=0)
    for m in pos.index[pos.to_numpy()]:
        ax.axvspan(m - pd.offsets.MonthBegin(1), m, color=fg.GRID, alpha=0.8, lw=0)
    ax.stackplot(w.index, w.iloc[:, 0], w.iloc[:, 1], cash, colors=[fg.BLUE, fg.ORANGE, fg.BASE],
                 labels=["SPY proxy", "TLT proxy", "cash (H.15 bills)"], edgecolor=fg.SURF, linewidth=0.4)
    ax.set_ylabel("weight (monthly mean)")
    ax.set_title(f"{fg.SHORT_R3[r]}: {N[r]}", fontsize=9)
axes[0].legend(loc="upper left", ncol=3, fontsize=8)
fig.suptitle("Exposure over time; gray months = L6 gate on (126-day SPY–TLT correlation > 0 at the previous month-end)",
             fontsize=10, fontweight="bold", color=fg.INK, y=0.995)
fig.text(0.01, -0.01, "Development 1990–2019. TLT = " + TLT, fontsize=7, color=fg.INK2)
fg.save(fig, OUT, "exposure_and_correlation_regime")

# 3. owner windows: growth of $1 inside 1994, GFC, Q4 2018 (raw books; the matched comparison is the committed chart) ----
W = {"bonds_1994": ("1994-02-01", "1994-11-30"), "gfc": ("2007-10-01", "2009-03-31"), "q4_2018": ("2018-09-01", "2018-12-31")}
COLS = [("L5_net", fg.NEUTRAL, "InvVol+VT"), ("L6_net", fg.ORANGE, "+CorrReg"), ("L7_net", fg.BLUE, "+Trend"),
        ("L3_net", fg.AQUA, "60/40"), ("L0_net", fg.INK2, "SPY")]
fig, axes = plt.subplots(1, 3, figsize=(12, 3.4))
for ax, (k, (a, z)) in zip(axes, W.items(), strict=True):
    seg = site_local.rebased(b.loc[a:z, [c for c, *_ in COLS]])
    for col, colr, _ in COLS:
        ax.plot(seg.index, seg[col], color=colr, lw=1.8 if col in ("L6_net", "L7_net") else 1.1)
    ax.set_title(fg.CRISIS_LABELS[k], fontsize=9)
    ax.text(0.02, 0.04, "\n".join(f"{lab} {seg[col].iloc[-1] - 1:+.1%}" for col, _, lab in COLS), transform=ax.transAxes,
            fontsize=7, color=fg.INK)
    ax.tick_params(labelsize=7)
    ax.tick_params(axis="x", labelrotation=30)
fig.suptitle("Owner windows, growth of $1 (raw, each book at its own risk; matched-risk differences: "
             "reports/figures/R3/crisis_matched_owner_windows)", fontsize=9, fontweight="bold", color=fg.INK, y=1.04)
fig.subplots_adjust(wspace=0.25)
fg.save(fig, OUT, "crisis_owner_windows")

# 4. rolling 5-year excess Sharpe ---------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 3.6))
for r, colr in [("L7", fg.BLUE), ("L6", fg.ORANGE), ("L5", fg.NEUTRAL), ("L3", fg.AQUA), ("L0", fg.INK2)]:
    s = site_local.rolling_sharpe(b[f"{r}_net"], b["bill"])
    ax.plot(s.index, s, color=colr, lw=1.8 if r in ("L6", "L7") else 1.1, label=fg.SHORT_R3[r])
    ax.annotate(f"{s.iloc[-1]:.2f}", (s.index[-1], s.iloc[-1]), xytext=(4, 0), textcoords="offset points", fontsize=7)
ax.axhline(0, color=fg.BASE, lw=0.8)
ax.legend(loc="upper left", ncol=5, fontsize=8)
ax.set_ylabel("excess Sharpe, trailing 5y")
ax.set_title("Rolling 5-year excess Sharpe (over H.15 bills), development 1990–2019")
fg.save(fig, OUT, "rolling_5y_excess_sharpe")
print("R3 local figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")), "| headline table:",
      {k: round(v["sharpe"], 3) for k, v in tab.items()})
