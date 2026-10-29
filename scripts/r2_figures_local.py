"""R2 LOCAL curve figures (owner O1.1) -> reports/figures_local/R2/<name>.png|svg, gitignored, never committed: the
headline (owner O2.1, `quantkit.viz.headline`: growth of $1 + drawdown, crisis shading, table), stacked exposure with
the stock-bond correlation regime shaded, rolling 5-year excess Sharpe, crisis small multiples. Source: the local daily
books data/r2/books.parquet (KF-derived) written by `make ladder`. Development 1990–2019 only (in-sample)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import figures as fg  # noqa: E402
from rspy import paths, site_local  # noqa: E402

plt.rcParams.update(fg.RC)
OUT = paths.REPORTS / "figures_local" / "R2"
N = fg.NAMES
b = pd.read_parquet(paths.data_dir() / "r2" / "books.parquet").loc["1990-01-01":"2019-12-31"]
TLT = paths.rules()["bonds"]["label"]

# 1. headline (owner's names; the first line is emphasised) --------------------------------------------------------------
lines = {N["L5"]: b["L5_net"], N["L4"]: b["L4_net"], N["L3"]: b["L3_net"], N["L2"]: b["L2_net"], N["L1"]: b["L1_net"],
         N["L0"]: b["L0_net"], N["L0-line"]: b["L5_line"]}
tab = fg.save_headline(lines, b["bill"], OUT, "headline_growth_and_drawdown", tier="in-sample",
                       title="The core mix vs vol-targeted SPY, v1 and SPY, 1990–2019",
                       subtitle="Development window: every R2 choice was made here (in-sample, not evidence); "
                                "SPY+T-bills line matched to the inverse-vol + vol target book")

# 2. exposure over time (L5 and L4) with the trailing 63-day SPY–TLT correlation > 0 shaded ------------------------------
corr = b["spy_proxy"].rolling(63).corr(b["tlt_proxy"])
pos = (corr > 0).resample("ME").mean() > 0.5
fig, axes = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True)
for ax, r in zip(axes, ["L5", "L4"], strict=True):
    w = b[[f"{r}_w_spy", f"{r}_w_tlt"]].resample("ME").mean()
    cash = (1 - w.sum(axis=1)).clip(lower=0)
    for m in pos.index[pos.to_numpy()]:
        ax.axvspan(m - pd.offsets.MonthBegin(1), m, color=fg.GRID, alpha=0.8, lw=0)
    ax.stackplot(w.index, w.iloc[:, 0], w.iloc[:, 1], cash, colors=[fg.BLUE, fg.ORANGE, fg.BASE],
                 labels=["SPY proxy", "TLT proxy", "cash (H.15 bills)"], edgecolor=fg.SURF, linewidth=0.4)
    ax.set_ylabel("weight (monthly mean)")
    ax.set_title(f"{N[r]}: exposure; gray months = trailing 63-day SPY–TLT correlation > 0 (most of the month)")
axes[0].legend(loc="upper left", ncol=3, fontsize=8)
fig.text(0.01, -0.02, "Correlation regime shown descriptively (the regime rule is R3's L6). TLT = " + TLT, fontsize=7,
         color=fg.INK2)
fg.save(fig, OUT, "exposure_and_correlation_regime")

# 3. rolling 5-year excess Sharpe ---------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 3.6))
for r, c in [("L5", fg.BLUE), ("L4", fg.ORANGE), ("L3", fg.AQUA), ("L2", fg.YELLOW), ("L1", fg.RED), ("L0", fg.NEUTRAL)]:
    s = site_local.rolling_sharpe(b[f"{r}_net"], b["bill"])
    ax.plot(s.index, s, color=c, lw=1.8 if r == "L5" else 1.2, label=N[r])
    ax.annotate(f"{s.iloc[-1]:.2f}", (s.index[-1], s.iloc[-1]), xytext=(4, 0), textcoords="offset points", fontsize=7)
ax.axhline(0, color=fg.BASE, lw=0.8)
ax.legend(loc="upper left", ncol=3, fontsize=8)
ax.set_ylabel("excess Sharpe, trailing 5y")
ax.set_title("Rolling 5-year excess Sharpe (over H.15 bills), development 1990–2019")
fg.save(fig, OUT, "rolling_5y_excess_sharpe")

# 4. crisis small multiples (pre-registered development windows) ---------------------------------------------------------
cw = {k: v for k, v in paths.prereg()["crisis_windows"].items() if str(v["end"]) <= "2019-12"}
fig, axes = plt.subplots(1, len(cw), figsize=(2.3 * len(cw), 2.8))
for ax, (k, v) in zip(axes, cw.items(), strict=True):
    a, z = pd.Period(str(v["start"]), "M").start_time, pd.Period(str(v["end"]), "M").end_time
    seg = site_local.rebased(b.loc[a:z, ["L5_net", "L3_net", "L0_net"]])
    for col, c in [("L5_net", fg.BLUE), ("L3_net", fg.AQUA), ("L0_net", fg.NEUTRAL)]:
        ax.plot(seg.index, seg[col], color=c, lw=1.6 if col == "L5_net" else 1.1)
    ax.set_title(fg.CRISIS_LABELS[k], fontsize=8)
    ax.text(0.02, 0.04, "\n".join(f"{lab} {seg[col].iloc[-1] - 1:+.0%}" for col, lab in
                                  [("L5_net", "L5"), ("L3_net", "60/40"), ("L0_net", "SPY")]),
            transform=ax.transAxes, fontsize=7, color=fg.INK)
    ax.tick_params(labelbottom=False, labelsize=7)
fig.suptitle(f"Crisis windows: {N['L5']} (blue), 60/40 (green), SPY (gray), growth of $1", fontsize=10,
             fontweight="bold", color=fg.INK, y=1.06)
fig.subplots_adjust(wspace=0.35)
fg.save(fig, OUT, "crisis_small_multiples")
print("R2 local figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")), "| headline table:",
      {k: round(v["sharpe"], 3) for k, v in tab.items()})
