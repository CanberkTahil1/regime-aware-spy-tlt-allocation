"""R5 LOCAL curve figures (owner O1.1) -> reports/figures_local/R5/<name>.png|svg, gitignored, never committed: the
test-window headline (`quantkit.viz.headline`, tier "disclosed-reuse": seen by owner in v1); the owner's post-hoc
10-year row against the official 25-year books; stacked exposure (SPY / TLT / cash) of L5–L8; the correlation regime
(126-day SPY–TLT correlation, the L6 gate shaded); crisis small multiples (growth of $1 in COVID and 2022, each rung vs
its ex-ante SPY+bills line); rolling 5-year excess Sharpe 1990 → 2026 (development and test marked). Source:
data/r5/books.parquet (KF-derived) written by `make test-run` / `make r5-replay`. `--local` / `--src` / `--out` let the
dry run's synthetic output be drawn into a temporary directory (code check)."""

import argparse
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import figures as fg  # noqa: E402
from rspy import paths, site_local  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--local", default=str(paths.data_dir() / "r5" / "books.parquet"))
ap.add_argument("--src", default=str(paths.REPORTS / "r5"))
ap.add_argument("--out", default=str(paths.REPORTS / "figures_local" / "R5"))
a = ap.parse_args()
OUT = pathlib.Path(a.out)
plt.rcParams.update(fg.RC)
b = pd.read_parquet(a.local)
facts = json.loads((pathlib.Path(a.src) / "facts.json").read_text())
t0, t1 = pd.Timestamp(facts["test_first"]), pd.Timestamp(facts["test_last"])
bt = b.loc[t0:t1]
N = {**fg.NAMES, **fg.NAMES_R3}
SUB = f"Test {t0.date()} → {t1.date()}, frozen rules run once (seen by owner in v1, disclosed)"

# 1. headline: the ladder on the test window -------------------------------------------------------------------------------
lines = {N["L5"]: bt["L5_net"], N["L6"]: bt["L6_net"], N["L7"]: bt["L7_net"], N["L8"]: bt["L8_net"],
         N["L3"]: bt["L3_net"], N["L1"]: bt["L1_net"], N["L0"]: bt["L0_net"], N["L0-line"]: bt["L5_line"]}
t1_ = fg.save_headline(lines, bt["bill"], OUT, "headline_test_window", tier="disclosed-reuse",
                       title=f"The frozen ladder on the test window, {t0.year}–{t1.year}",
                       subtitle=SUB + "; SPY+bills matched ex ante to InvVol+VT")

# 2. headline: the owner's post-hoc 10-year row vs the official 25-year books ----------------------------------------------
TEN = {"L5": "InvVol+VT 10y", "L6": "+CorrReg 10y", "L7": "+Trend 10y"}
lines = {**{TEN[r]: bt[f"{r}@10y_net"] for r in TEN}, **{N[r]: bt[f"{r}_net"] for r in TEN}, N["L0"]: bt["L0_net"]}
t2_ = fg.save_headline(lines, bt["bill"], OUT, "headline_test_10y_bond_leg", tier="disclosed-reuse",
                       title="POST-HOC (owner): a 10-year bond leg vs the official 25-year books, test window",
                       subtitle=SUB + "; 10y leg not QA'd vs an ETF")

# 3. exposure over time (SPY / TLT / cash stacked) ---------------------------------------------------------------------------
fig, axes = plt.subplots(4, 1, figsize=(10, 7.5), sharex=True)
for ax, r in zip(axes, ["L5", "L6", "L7", "L8"], strict=True):
    w = bt[[f"{r}_w_spy", f"{r}_w_tlt"]].resample("W").last()
    cash = (1 - w.sum(axis=1)).clip(lower=0)
    ax.stackplot(w.index, w.iloc[:, 0], w.iloc[:, 1], cash, colors=[fg.BLUE, fg.ORANGE, fg.GRID], lw=0)
    ax.set_ylim(0, 1)
    ax.set_ylabel(fg.SHORT_R3.get(r, r), rotation=0, ha="right", va="center")
axes[0].legend(["SPY", "TLT", "cash"], fontsize=8, ncol=3, loc="upper right")
fig.suptitle("Exposure over the test window (held weights, weekly)", fontsize=10, fontweight="bold", color=fg.INK)
fg.save(fig, OUT, "exposure_l5_to_l8_test")

# 4. the correlation regime ---------------------------------------------------------------------------------------------------
c = b.loc[t0 - pd.DateOffset(years=2):t1]
fig, axes = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
axes[0].plot(c.index, c["corr126"], color=fg.INK2, lw=1)
axes[0].axhline(0, color=fg.RED, lw=0.8, ls=":")
gate = c["corr126_gate"] == 0
axes[0].fill_between(c.index, -1, 1, where=gate, color=fg.ORANGE, alpha=0.15, lw=0, label="L6 gate: TLT to cash")
axes[0].set_ylim(-1, 1)
axes[0].set_ylabel("126-day SPY–TLT corr")
axes[0].axvline(t0, color=fg.MUTED, lw=0.8)
axes[0].legend(fontsize=8)
axes[1].plot(c.index, c["L6_w_tlt"], color=fg.ORANGE, lw=1.2, label="L6 TLT weight")
axes[1].plot(c.index, c["L5_w_tlt"], color=fg.NEUTRAL, lw=1, label="L5 TLT weight")
axes[1].legend(fontsize=8)
axes[1].axvline(t0, color=fg.MUTED, lw=0.8)
fig.suptitle("Stock–bond correlation regime (the vertical line marks the start of the test window)", fontsize=10,
             fontweight="bold", color=fg.INK)
fg.save(fig, OUT, "correlation_regime_test")

# 5. crisis small multiples: growth of $1, each rung vs its ex-ante line -------------------------------------------------------
cr = [k for k in ("covid", "infl_2022")]
rs = ["L3", "L5", "L6", "L7", "L8"]
fig, axes = plt.subplots(len(cr), len(rs), figsize=(13, 5), sharey="row")
for i, k in enumerate(cr):
    v = paths.prereg()["crisis_windows"][k]
    w = b.loc[pd.Period(str(v["start"]), "M").start_time:pd.Period(str(v["end"]), "M").end_time]
    for j, r in enumerate(rs):
        ax = axes[i, j]
        ax.plot(w.index, site_local.rebased(w[f"{r}_net"]), color=fg.BLUE, lw=1.4, label=fg.SHORT_R3.get(r, r))
        ax.plot(w.index, site_local.rebased(w[f"{r}_line"]), color=fg.NEUTRAL, lw=1, label="SPY+bills (ex ante)")
        ax.plot(w.index, site_local.rebased(w["L0_net"]), color=fg.RED, lw=0.8, alpha=0.6, label="SPY")
        ax.tick_params(labelsize=6)
        if i == 0:
            ax.set_title(fg.SHORT_R3.get(r, r), fontsize=9)
        if j == 0:
            ax.set_ylabel(fg.CRISIS_LABELS[k], fontsize=8)
axes[0, 0].legend(fontsize=6)
fig.suptitle("Crisis small multiples, growth of $1 (each rung vs SPY + T-bills at its own vol, ex ante)", fontsize=10,
             fontweight="bold", color=fg.INK)
fg.save(fig, OUT, "crisis_small_multiples_test")

# 6. rolling 5-year excess Sharpe, 1990 → 2026 -----------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 3.8))
for r, col in [("L0", fg.RED), ("L3", fg.NEUTRAL), ("L5", fg.BLUE), ("L6", fg.ORANGE), ("L7", fg.AQUA)]:
    s = site_local.rolling_sharpe(b[f"{r}_net"].loc["1990-01-02":], b["bill"])
    ax.plot(s.index, s, color=col, lw=1.1, label=fg.SHORT_R3.get(r, r))
ax.axvspan(t0, t1, color=fg.YELLOW, alpha=0.12, lw=0, label="test (disclosed)")
ax.axhline(0, color=fg.BASE)
ax.set_ylabel("trailing 5y excess Sharpe")
ax.legend(fontsize=7, ncol=6)
ax.set_title("Rolling 5-year excess Sharpe, development (in-sample) and test (seen by owner in v1, disclosed)")
fg.save(fig, OUT, "rolling_5y_excess_sharpe_1990_2026")
print("R5 local figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")), "| headline:",
      {k: round(v["sharpe"], 3) for k, v in t1_.items()}, {k: round(v["sharpe"], 3) for k, v in t2_.items()})
