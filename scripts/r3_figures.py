"""R3 statistics figures -> reports/figures/R3/<name>.png|svg (committed). Owner O1.1: only charts of committed statistics
(reports/r3/*.csv, *.json) are drawn here; curves built from KF-derived series go to the gitignored
reports/figures_local/R3/ (scripts/r3_figures_local.py, make report-site-local). Development 1990–2019 only: in-sample,
descriptive (owner O2.4: no promotion walk for L6–L8)."""

import json
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import figures as fg  # noqa: E402
from rspy import paths  # noqa: E402

plt.rcParams.update(fg.RC)
OUT = paths.REPORTS / "figures" / "R3"
R3 = paths.REPORTS / "r3"
N = {**fg.NAMES, **fg.NAMES_R3}
abl = pd.read_csv(R3 / "ablation.csv")
ctx = pd.read_csv(R3 / "ablation_context.csv")
m = pd.read_csv(R3 / "metrics.csv").set_index("rung")
ln = pd.read_csv(R3 / "lines.csv").set_index("rung")
cr = pd.read_csv(R3 / "crisis.csv")
pl = pd.read_csv(R3 / "placebo.csv")
crash = json.loads((R3 / "crash.json").read_text())
NOTE = ("Development 1990–2019 (in-sample, descriptive; no promotion walk, owner O2.4). Matched vol: the reference is "
        "rescaled with T-bills to the child's excess vol. SPY = SPY proxy (KF Hi 20); TLT = "
        + paths.rules()["bonds"]["label"] + ".")


def note(fig, extra="", y=-0.04):
    fig.text(0.01, y, "\n".join(textwrap.wrap(NOTE + (" " + extra if extra else ""), 175)), fontsize=7, color=fg.INK2,
             va="top")


# 1. what each layer added: ΔSharpe vs the parent and CDaR ratio, 95% intervals (context: R2's layers) ------------------
rows = pd.concat([ctx, abl[(abl.reference == "parent") & (abl.role == "rung")]], ignore_index=True)
lab = [f"{r.layer} ({r.child} vs {r.reference_rung})" for r in rows.itertuples()]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.6), sharey=True)
yy = np.arange(len(rows))[::-1]
for yi, r in zip(yy, rows.itertuples(), strict=True):
    col = fg.NEUTRAL if r.role.startswith("context") else fg.BLUE
    a1.plot([r.lo, r.hi], [yi, yi], color=col, lw=2, alpha=0.5)
    a1.plot(r.dsharpe, yi, "o", color=col, ms=7)
    a1.text(r.hi + 0.01, yi, f"{r.dsharpe:+.2f}", va="center", fontsize=8)
    a2.plot([r.cdar_lo, r.cdar_hi], [yi, yi], color=col, lw=2, alpha=0.5)
    a2.plot(r.cdar_ratio, yi, "o", color=col, ms=7)
    a2.text(r.cdar_hi + 0.02, yi, f"{r.cdar_ratio:.2f}", va="center", fontsize=8)
a1.axvline(0, color=fg.INK2, lw=0.8)
a2.axvline(1, color=fg.INK2, lw=0.8)
a1.set_yticks(yy, lab, fontsize=8)
a1.set_title("ΔSharpe vs the parent at matched vol (LW 95%)")
a2.set_title("CDaR-95 ratio, child / matched parent (bootstrap 95%)")
note(fig, "Gray = R2 layers for context (seen). Drawdown intervals: paired stationary bootstrap, mean block 21 "
     "sessions (likely too narrow for multi-month drawdowns).")
fg.save(fig, OUT, "ablation_intervals")

# 2. each regime layer vs its parent, 60/40, v1 and the SPY + T-bills line ------------------------------------------------
REFS = ["parent", "60/40 (L3)", "v1 (L1)", "SPY+T-bills line"]
COL = dict(zip(REFS, [fg.BLUE, fg.AQUA, fg.RED, fg.ORANGE], strict=True))
main = abl[abl.role == "rung"]
fig, ax = plt.subplots(figsize=(9, 4.2))
kids = list(dict.fromkeys(main.child))
for i, ch in enumerate(kids):
    for j, ref in enumerate(REFS):
        r = main[(main.child == ch) & (main.reference == ref)].iloc[0]
        y = (len(kids) - i) * 5 - j
        ax.plot([r.lo, r.hi], [y, y], color=COL[ref], lw=2, alpha=0.5)
        ax.plot(r.dsharpe, y, "o", color=COL[ref], ms=6, label=ref if i == 0 else None)
        ax.text(r.hi + 0.01, y, f"{r.dsharpe:+.2f} (p {r.p_one_sided:.2f}, Holm {r.holm_p:.2f})", va="center",
                fontsize=7)
ax.set_yticks([(len(kids) - i) * 5 - 1.5 for i in range(len(kids))], [f"{N[k]} ({k})" for k in kids])
ax.axvline(0, color=fg.INK2, lw=0.8)
ax.legend(fontsize=8, loc="upper left", ncol=2)
ax.set_xlabel("ΔSharpe (excess over bills) vs the reference at matched vol; LW 95% interval")
ax.set_title("The regime layers vs their parent, 60/40, v1 and SPY + T-bills")
note(fig, f"Holm over the {int(abl.n_family.iloc[0])} ΔSharpe p-values in reports/r3/ablation.csv.")
fg.save(fig, OUT, "ablation_vs_references")

# 3. owner windows: 1994, GFC, Q4 2018 at matched risk ------------------------------------------------------------------
W = {"bonds_1994": "1994 bonds", "gfc": "GFC 2007-10→2009-03", "q4_2018": "Q4 2018"}
PAIRS = [("L6", "L5"), ("L7", "L6"), ("L7-on-L5", "L5"), ("L6", "L3"), ("L7", "L3"), ("L6", "L0"), ("L7", "L0")]
fig, axes = plt.subplots(1, 3, figsize=(15, 3.8), sharey=True)
for ax, (w, wl) in zip(axes, W.items(), strict=True):
    yy = np.arange(len(PAIRS))[::-1]
    for yi, (ch, ref) in zip(yy, PAIRS, strict=True):
        r = cr[(cr.child == ch) & (cr.reference == ref) & (cr.crisis == w)].iloc[0]
        ax.barh(yi, r.diff_matched, color=fg.AQUA if r.diff_matched >= 0 else fg.RED, height=0.6)
        ax.text(max(r.diff_matched, 0) + 0.005, yi,
                f"{r.diff_matched:+.1%} ({r.child_return:+.1%} vs {r.parent_matched_return:+.1%})", va="center",
                ha="left", fontsize=7)
    ax.axvline(0, color=fg.INK2, lw=0.8)
    ax.set_title(wl)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlim(-0.1, 0.5)
axes[0].set_yticks(yy, [f"{ch} vs {ref}" for ch, ref in PAIRS], fontsize=8)
fig.suptitle("In-crisis return of the child minus the reference at the child's vol (child vs matched reference)",
             fontsize=10, fontweight="bold", color=fg.INK, y=1.02)
note(fig, "L6 = +CorrReg (TLT to cash when 126-day corr > 0); L7 = +Trend (Faber 10m per sleeve); L7-on-L5 = trend "
     "without the correlation layer; L5 = inverse-vol + vol target; L3 = 60/40; L0 = SPY.")
fg.save(fig, OUT, "crisis_matched_owner_windows")

# 4. gates vs their block-shuffled placebos -------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 3.2))
yy = np.arange(len(pl))[::-1]
for yi, r in zip(yy, pl.itertuples(), strict=True):
    ax.plot([r.placebo_dsharpe_p05, r.placebo_dsharpe_p95], [yi, yi], color=fg.NEUTRAL, lw=6, alpha=0.35,
            solid_capstyle="butt")
    ax.plot(r.placebo_dsharpe_median, yi, "|", color=fg.NEUTRAL, ms=14)
    ax.plot(r.dsharpe_gate, yi, "o", color=fg.BLUE, ms=8)
    ax.text(max(r.dsharpe_gate, r.placebo_dsharpe_p95) + 0.01, yi,
            f"gate {r.dsharpe_gate:+.2f} (p {r.p_gate:.2f}); pctile {r.percentile_among_100_seeds:.0f}; "
            f"beats placebo: {'yes' if r.beats_placebo else 'no'}", va="center", fontsize=7)
ax.axvline(0, color=fg.INK2, lw=0.8)
ax.set_yticks(yy, [f"{N.get(g, g)} vs {r}" for g, r in zip(pl.gate, pl.parent, strict=True)], fontsize=8)
ax.set_xlim(right=0.45)
ax.set_xlabel("ΔSharpe vs the parent at matched vol")
ax.set_title("Each gate (blue) vs 100 placebos with its decisions shuffled in 12-month blocks (gray: 5–95%, median)")
note(fig, f"Crash rule (L8): sizing.judge on = {crash['on']}; candidate one-sided p {crash['candidate']['p_one_sided']:.2f}, "
     f"placebo p {crash['placebo']['p_one_sided']:.2f}; brake active on {crash['share_dev_days_g_below_1']:.1%} of days.")
fg.save(fig, OUT, "gate_placebos")

# 5. return vs CDaR with each rung's SPY + T-bills line ----------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 4.8))
for r in ["L0", "L1", "L3", "L5", "L6", "L7", "L8", "L7-on-L5", "hmm_gate", "jump_gate", "min_cdar"]:
    core = r in ("L5", "L6", "L7", "L8")
    ax.plot(m.loc[r, "cdar95"], m.loc[r, "cagr"], "o", color=fg.BLUE if core else fg.NEUTRAL, ms=7 if core else 5)
    ax.annotate(fg.SHORT_R3.get(r, r), (m.loc[r, "cdar95"], m.loc[r, "cagr"]), xytext=(5, 3),
                textcoords="offset points", fontsize=8)
    if r in ln.index:
        ax.plot(ln.loc[r, "line_cdar95"], ln.loc[r, "line_cagr"], "x", color=fg.ORANGE, ms=6)
        ax.plot([m.loc[r, "cdar95"], ln.loc[r, "line_cdar95"]], [m.loc[r, "cagr"], ln.loc[r, "line_cagr"]],
                color=fg.ORANGE, lw=0.6, alpha=0.6)
ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
ax.set_xlabel("CDaR-95 (average of the worst 5% drawdowns)")
ax.set_ylabel("CAGR")
ax.set_title("Return vs drawdown risk; orange x = SPY + T-bills at the rung's vol (ex ante)")
note(fig, "Gray = comparison and zoo rows.", y=-0.02)
fg.save(fig, OUT, "return_vs_cdar")

# 6. cost waterfall L5 → L8 (1x) and the 2x / 3x cost rows ----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 3.6))
x0 = 0
for r in ("L5", "L6", "L7", "L8"):
    v = m.loc[r]
    gross = v.net_pa + v.cost_pa + v.financing_pa
    ax.bar(x0, gross, color=fg.BLUE, width=0.8)
    ax.bar(x0 + 1, -v.cost_pa, bottom=gross, color=fg.RED, width=0.8)
    ax.bar(x0 + 2, v.net_pa, color=fg.AQUA, width=0.8)
    ax.text(x0 + 2, v.net_pa, f"{v.net_pa:.2%}\n(2x {m.loc[f'{r}@2x', 'net_pa']:.2%}, 3x {m.loc[f'{r}@3x', 'net_pa']:.2%})",
            ha="center", va="bottom", fontsize=7)
    ax.text(x0 + 1, -0.004, f"{fg.SHORT_R3[r]}\nturnover {v.turnover_pa:.1f}x/yr", ha="center", va="top", fontsize=8)
    x0 += 4
ax.set_xticks([])
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
ax.set_ylim(bottom=-0.02, top=0.12)
ax.set_title("Mean return per year: gross (blue) − trading costs (red) = net (green); no financing (gross ≤ 1)")
note(fig, "Costs 3/2 bp per side on true traded turnover (gate exits and vol scaling included).")
fg.save(fig, OUT, "cost_waterfall")
print("R3 figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")))
