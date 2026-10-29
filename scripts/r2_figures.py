"""R2 statistics figures -> reports/figures/R2/<name>.png|svg (committed). Owner O1.1: only charts of committed statistics
(reports/r2/*.csv) are drawn here; curves built from KF-derived series go to the gitignored reports/figures_local/R2/
(scripts/r2_figures_local.py, make report-site-local). Development 1990–2019 only: in-sample, not evidence."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import figures as fg  # noqa: E402
from rspy import paths  # noqa: E402

plt.rcParams.update(fg.RC)
OUT = paths.REPORTS / "figures" / "R2"
R2 = paths.REPORTS / "r2"
N = {**fg.NAMES, "L4b": "ERC (= inverse-vol)", "L5-lev": "Inverse-vol + vol target, 1.5x", "L2-u": "Vol-targeted SPY, 10%"}
CORE = ["L1", "L2", "L3", "L4", "L5"]
m = pd.read_csv(R2 / "metrics.csv")
m1 = m[m.book == "1x"].set_index("rung")
ln = pd.read_csv(R2 / "lines.csv").set_index("rung")
abl = pd.read_csv(R2 / "ablation.csv")
tl = pd.read_csv(R2 / "timing_luck.csv")
NOTE = "Development 1990–2019 (in-sample, not evidence). SPY = SPY proxy (KF Hi 20); TLT = " + paths.rules()["bonds"]["label"] + "."

# 1. ladder chart: ΔSharpe vs the SPY + T-bills line at matched vol, LW 95% interval ---------------------------------------
rows = ["L1", "L2", "L2-u", "L3", "L4", "L5", "L5-lev"]
fig, ax = plt.subplots(figsize=(8, 3.8))
y = np.arange(len(rows))[::-1]
for yi, r in zip(y, rows, strict=True):
    v = ln.loc[r]
    c = fg.BLUE if r in CORE else fg.NEUTRAL
    ax.plot([v.lo, v.hi], [yi, yi], color=c, lw=2, alpha=0.6)
    ax.plot(v.dsharpe_vs_line, yi, "o", color=c, ms=7)
    ax.text(v.hi + 0.01, yi, f"{v.dsharpe_vs_line:+.2f} (p {v.p_one_sided:.3f})", va="center", fontsize=8, color=fg.INK)
ax.axvline(0, color=fg.INK2, lw=0.8)
ax.set_yticks(y, [N[r] for r in rows])
ax.set_xlabel("excess Sharpe minus that of SPY + T-bills at the rung's vol (ex ante, 63 days)")
ax.set_title("Each rung vs SPY + T-bills at matched vol: point and 95% LW interval")
fig.text(0.01, -0.04, NOTE + " Gray = descriptive rows (not in the walk).", fontsize=7, color=fg.INK2)
fg.save(fig, OUT, "ladder_vs_line")

# 2. ablation: what each layer added (matched-vol ΔSharpe and CDaR change) ------------------------------------------------
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
yy = np.arange(len(abl))[::-1]
a1.barh(yy, abl.dsharpe_matched, color=[fg.BLUE if v >= 0 else fg.RED for v in abl.dsharpe_matched])
a2.barh(yy, abl.cdar_change, color=[fg.AQUA if v <= 0 else fg.RED for v in abl.cdar_change])
for a, col, fmt in ((a1, "dsharpe_matched", "{:+.2f}"), (a2, "cdar_change", "{:+.0%}")):
    for yi, v in zip(yy, abl[col], strict=True):
        a.text(v, yi, " " + fmt.format(v), va="center", ha="left" if v >= 0 else "right", fontsize=8)
    a.axvline(0, color=fg.INK2, lw=0.8)
a1.axvline(0.05, color=fg.MUTED, lw=0.8, ls="--")
a2.axvline(-0.15, color=fg.MUTED, lw=0.8, ls="--")
a1.set_yticks(yy, abl.layer)
a1.set_title("ΔSharpe vs the parent at matched vol")
a2.set_title("CDaR-95 change vs the parent at matched vol")
fig.text(0.01, -0.04, NOTE + " Dashed: the promotion rule's minimum effect (+0.05 Sharpe or −15% CDaR).", fontsize=7,
         color=fg.INK2)
fg.save(fig, OUT, "ablation")

# 3. cost waterfall: mean return per year, gross → costs → financing → net -----------------------------------------------
fig, ax = plt.subplots(figsize=(9, 3.6))
x0 = 0
for r in CORE:
    v = m1.loc[r]
    gross = v.net_pa + v.cost_pa + v.financing_pa
    steps = [("gross", gross, fg.BLUE), ("costs", -v.cost_pa, fg.RED), ("financing", -v.financing_pa, fg.YELLOW)]
    level = 0.0
    for k, (_lab, d, col) in enumerate(steps):
        ax.bar(x0 + k, d, bottom=level if k else 0, color=col, width=0.8)
        level = d if k == 0 else level + d
    ax.bar(x0 + 3, v.net_pa, color=fg.AQUA, width=0.8)
    ax.text(x0 + 3, v.net_pa, f"{v.net_pa:.1%}", ha="center", va="bottom", fontsize=7)
    ax.text(x0 + 1.5, -0.012, N[r], ha="center", va="top", fontsize=8, color=fg.INK)
    x0 += 5
ax.set_xticks([])
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
ax.set_ylim(bottom=-0.03)
ax.set_title("Mean return per year: gross (blue) − trading costs (red) − financing (yellow) = net (green)")
fig.text(0.01, -0.04, NOTE + " Costs on true traded turnover; financing at bill + 25 bp on borrowed notional.",
         fontsize=7, color=fg.INK2)
fg.save(fig, OUT, "cost_waterfall")

# 4. return vs CDaR, rungs and their matched lines --------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7, 4.6))
for r in ["L0", *CORE, "L5-lev", "L2-u"]:
    c = fg.BLUE if r in CORE else fg.NEUTRAL
    ax.plot(m1.loc[r, "cdar95"], m1.loc[r, "cagr"], "o", color=c, ms=7)
    ax.annotate(N[r], (m1.loc[r, "cdar95"], m1.loc[r, "cagr"]), xytext=(5, 3), textcoords="offset points", fontsize=8)
    if r != "L0":
        ax.plot(ln.loc[r, "line_cdar95"], ln.loc[r, "line_cagr"], "x", color=fg.ORANGE, ms=6)
        ax.plot([m1.loc[r, "cdar95"], ln.loc[r, "line_cdar95"]], [m1.loc[r, "cagr"], ln.loc[r, "line_cagr"]],
                color=fg.ORANGE, lw=0.6, alpha=0.6)
ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
ax.set_xlabel("CDaR-95 (average of the worst 5% drawdowns)")
ax.set_ylabel("CAGR")
ax.set_title("Return vs drawdown risk; orange x = SPY + T-bills at the rung's vol")
fig.text(0.01, -0.03, NOTE, fontsize=7, color=fg.INK2)
fg.save(fig, OUT, "return_vs_cdar")

# 5. timing luck: annual return of each of the 21 rebalance-day books ----------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 3.2))
for k, r in enumerate(["L3", "L4", "L5"]):
    t = tl[(tl.rung == r) & (tl.offset != "tranched")]
    o = t.offset.astype(int)
    ax.plot(o, t["ann_return"], "o-", color=[fg.BLUE, fg.ORANGE, fg.AQUA][k], ms=3, lw=1.2,
            label=f"{N[r]} (RTL {tl[(tl.rung == r) & (tl.offset == 'tranched')].rtl.iloc[0]:.2%}/yr)")
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
ax.set_xlabel("rebalance trading day of the month (0 = record book)")
ax.set_ylabel("annual return (net of 3/2 bp costs, cash at 0)")
ax.legend(fontsize=8)
ax.set_title("Timing luck: the same rule rebalanced on each of 21 trading days")
fig.text(0.01, -0.05, NOTE + " quantkit timing_luck (cash at 0, costs 3/2 bp); never used to pick a day.", fontsize=7,
         color=fg.INK2)
fg.save(fig, OUT, "timing_luck")
# 6. the two walks side by side (O2.3): pre-registered L1 → L5 (record) and the post-hoc parent chains ----------------
import json  # noqa: E402
import textwrap  # noqa: E402

pre = json.loads((R2 / "ladder.json").read_text())
ch = json.loads((R2 / "ladder_chains.json").read_text())["chains"]
walks = [("pre-registered (record)", ["L1", "L2", "L3", "L4", "L5"], pre)]
walks += [(f"post-hoc chain {k}", v["chain"], v) for k, v in ch.items()]
rows_ = []
for title, order, w in walks:
    done = {s_["rung"]: s_ for s_ in w["steps"]}
    for cand, inc in zip(order[1:], order[:-1], strict=True):
        rows_.append((title, cand, inc, done.get(cand)))
fig, ax = plt.subplots(figsize=(9, 0.42 * len(rows_) + 1.2))
yy = np.arange(len(rows_))[::-1]
for yi, (*_, st_) in zip(yy, rows_, strict=True):
    if st_ is None:
        ax.text(0.06, yi, "not tested (walk stopped)", va="center", fontsize=8, color=fg.MUTED)
        continue
    q = st_["quantkit"]
    ax.barh(yi, q["effect"], color=fg.AQUA if st_["promoted"] else fg.RED, height=0.6)
    failed = [k for k, v in q["parts"].items() if not v]
    ax.text(max(q["effect"], 0) + 0.005, yi, f"{q['effect']:+.3f}, LW p {q['p']:.3f}"
            + (f"; fails: {', '.join(failed)}" if failed else "; promoted"), va="center", fontsize=8, color=fg.INK)
ax.axvline(0, color=fg.INK2, lw=0.8)
ax.axvline(0.05, color=fg.MUTED, lw=0.8, ls="--")
ax.set_yticks(yy, [f"{t}: {N[c]} vs {N[i]}" for t, c, i, _ in rows_], fontsize=8)
ax.set_xlim(-0.05, 0.55)
ax.set_ylim(-0.7, len(rows_) - 0.3)
ax.set_xlabel("ΔSharpe vs the incumbent (quantkit effect; dashed = +0.05 minimum)")
ax.set_title("Promotion walks: pre-registered order vs post-hoc parent chains (owner O2.3)")
fig.text(0.01, -0.04, "\n".join(textwrap.wrap(NOTE + " Post-hoc: charter amended after R2 results; counted in the DSR "
         "trial count. robust = no Sharpe loss inside any development crisis window.", 170)), fontsize=7, color=fg.INK2)
fg.save(fig, OUT, "promotion_walks")
print("R2 figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")))
