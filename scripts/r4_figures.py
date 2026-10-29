"""R4 statistics figures -> reports/figures/R4/<name>.png|svg (committed). Owner O1.1: only charts of committed statistics
(reports/r4/*.csv, *.json) are drawn here; curves built from KF-derived series go to the gitignored
reports/figures_local/R4/ (scripts/r4_figures_local.py, make report-site-local). Development 1990–2019 only: in-sample,
descriptive ("built rungs; none promoted")."""

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
OUT = paths.REPORTS / "figures" / "R4"
R = paths.REPORTS / "r4"
PE = paths.prereg()["r4_evaluation"]
PAR = PE["parents"]
costs = pd.read_csv(R / "costs.csv")
wf = pd.read_csv(R / "waterfall.csv")
loco = pd.read_csv(R / "loco.csv")
dec = pd.read_csv(R / "decades.csv")
roll = pd.read_csv(R / "rolling.csv")
pw = pd.read_csv(R / "power.csv")
sens = pd.read_csv(R / "sensitivity.csv")
dsr = pd.read_csv(R / "dsr.csv")
pbo = pd.read_csv(R / "pbo.csv")
zoo = pd.read_csv(R / "zoo.csv")
facts = json.loads((R / "facts.json").read_text())
LAB = {"L0": "SPY", "L1": "v1", "L2": "VT SPY", "L3": "60/40", "L4": "InvVol", "L5": "InvVol+VT", "L5-lev": "InvVol+VT 1.5x",
       "L6": "+CorrReg", "L7": "+Trend", "L8": "+Crash"}
LAYERS = [r for r in PE["rungs"] if r in PAR]
NOTE = (PE["label"] + ". Development 1990–2019 (in-sample, descriptive). Matched vol: the reference is rescaled once with "
        "T-bills to the rung's development excess vol. SPY = SPY proxy (KF Hi 20); TLT = " + paths.rules()["bonds"]["label"] + ".")


def note(fig, extra="", y=-0.04):
    fig.text(0.01, y, "\n".join(textwrap.wrap(NOTE + (" " + extra if extra else ""), 175)), fontsize=7, color=fg.INK2,
             va="top")


def lab(r):
    return f"{LAB.get(r, r)} ({r} vs {PAR[r]})" if r in PAR else LAB.get(r, r)


# 1. what each layer added, at 1x / 2x / 3x costs and +75 bp financing ------------------------------------------------------
par = costs[costs.apply(lambda x: PAR.get(x.rung) == x.reference, axis=1)]
fig, ax = plt.subplots(figsize=(9, 4.2))
yy = np.arange(len(LAYERS))[::-1]
mk = {"1x": ("o", fg.BLUE), "2x": ("s", fg.YELLOW), "3x": ("D", fg.RED), "f75": ("^", fg.AQUA)}
for yi, r in zip(yy, LAYERS, strict=True):
    one = par[(par.rung == r) & (par.book == "1x")].iloc[0]
    ax.plot([one.lo, one.hi], [yi, yi], color=fg.BLUE, lw=2, alpha=0.35)
    for k, (m_, col) in mk.items():
        v = par[(par.rung == r) & (par.book == k)].dsharpe.iloc[0]
        ax.plot(v, yi + {"1x": 0, "2x": 0.12, "3x": 0.24, "f75": -0.12}[k], m_, color=col, ms=6 if k == "1x" else 4,
                label=k if yi == yy[0] else None)
    ax.text(one.hi + 0.01, yi, f"{one.dsharpe:+.2f}", va="center", fontsize=8)
ax.axvline(0, color=fg.BASE, lw=1)
ax.set_yticks(yy, [lab(r) for r in LAYERS])
ax.set_xlabel("ΔSharpe vs the parent at matched vol (LW 95% interval at 1×)")
ax.legend(loc="lower right", ncol=4, fontsize=8, title="cost row", title_fontsize=8)
ax.set_title("What each layer added, and whether costs or financing change it")
note(fig, "2×/3× = cost multipliers on both books; f75 = +75 bp financing on borrowed notional (both books).")
fg.save(fig, OUT, "ablation_by_cost_row")

# 2. loss waterfall per rung (1x), with the 3x and +75 bp net -----------------------------------------------------------------
w1 = wf[wf.book == "1x"].set_index("rung").loc[PE["rungs"]]
w3 = wf[wf.book == "3x"].set_index("rung")
wf75 = wf[wf.book == "f75"].set_index("rung")
comp = [("gross_pa", "gross sleeve return", fg.BLUE, 1), ("cash_pa", "cash interest", fg.AQUA, 1),
        ("cost_spy_pa", "SPY costs", fg.YELLOW, -1), ("cost_tlt_pa", "TLT costs", fg.ORANGE, -1),
        ("financing_pa", "financing", fg.RED, -1)]
fig, ax = plt.subplots(figsize=(10, 4.4))
x = np.arange(len(w1))
for i, (r, row) in enumerate(w1.iterrows()):
    lvl = 0.0
    for k, name, col, sg in comp:
        v = sg * row[k]
        ax.bar(i, v, bottom=lvl, color=col, width=0.6, label=name if i == 0 else None, edgecolor=fg.SURF, lw=0.3)
        lvl += v
    ax.plot([i - 0.35, i + 0.35], [row.net_pa] * 2, color=fg.INK, lw=1.6, label="net (1×)" if i == 0 else None)
    ax.plot(i, w3.loc[r, "net_pa"], "D", color=fg.RED, ms=4, label="net at 3× costs" if i == 0 else None)
    ax.plot(i, wf75.loc[r, "net_pa"], "^", color=fg.NEUTRAL, ms=4, label="net at +75 bp" if i == 0 else None)
    ax.text(i, max(row.gross_pa + row.cash_pa, row.net_pa) + 0.002, f"{row.net_pa:.1%}\n−{row.cost_spy_pa + row.cost_tlt_pa + row.financing_pa:.2%}",
            ha="center", va="bottom", fontsize=7)
top = float((w1.gross_pa + w1.cash_pa).max())
ax.set_ylim(0, top * 1.18)
ax.set_xticks(x, [LAB[r] for r in w1.index], rotation=20, fontsize=8)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
ax.set_ylabel("annualised arithmetic return")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4, fontsize=7)
ax.set_title("Loss waterfall per rung: gross + cash − costs − financing = net (1×); label: net and total drag")
note(fig, "Arithmetic means (×252), additive per day (identity ≤ 1e-10); the vol drag ((1 + mean)^252 − 1 − CAGR) is in "
          "waterfall.csv.", y=-0.2)
fg.save(fig, OUT, "loss_waterfall")

# 3. leave-one-crisis-out: change in each layer's ΔSharpe vs the parent ---------------------------------------------------------
lp = loco[loco.apply(lambda x: PAR.get(x.rung) == x.reference, axis=1)]
cr = list(dict.fromkeys(lp.dropped))
fig, ax = plt.subplots(figsize=(9, 4))
for j, k in enumerate(cr):
    s = lp[lp.dropped == k].set_index("rung").loc[LAYERS]
    ax.scatter(s.change, yy + (j - 2.5) * 0.1, s=22, color=[fg.BLUE, fg.ORANGE, fg.AQUA, fg.YELLOW, fg.RED, fg.NEUTRAL][j],
               label=fg.CRISIS_LABELS[k])
ax.axvline(0, color=fg.BASE, lw=1)
ax.set_yticks(yy, [lab(r) for r in LAYERS])
ax.set_xlabel("ΔSharpe without the window − ΔSharpe on all development days")
ax.legend(fontsize=7, ncol=3, loc="lower right")
ax.set_title("Leave-one-crisis-out: which crisis each layer's result depends on")
note(fig, "A negative change = the layer looked better because of that window.")
fg.save(fig, OUT, "leave_one_crisis_out")

# 4. decades ------------------------------------------------------------------------------------------------------------------------
dp = dec[dec.apply(lambda x: PAR.get(x.rung) == x.reference, axis=1)]
fig, ax = plt.subplots(figsize=(9, 4))
for j, (d, col) in enumerate(zip(["1990s", "2000s", "2010s"], [fg.AQUA, fg.ORANGE, fg.BLUE], strict=True)):
    s = dp[dp.decade == d].set_index("rung").loc[LAYERS]
    ax.barh(yy + (j - 1) * 0.25, s.dsharpe, height=0.25, color=col, label=d)
ax.axvline(0, color=fg.BASE, lw=1)
ax.set_yticks(yy, [lab(r) for r in LAYERS])
ax.set_xlabel("ΔSharpe vs the parent within the decade (parent matched once on the full development sample)")
ax.legend(fontsize=8)
ax.set_title("Each layer by decade")
note(fig)
fg.save(fig, OUT, "decades")

# 5. rolling 5-year: share of windows where the layer beat its parent ------------------------------------------------------------------
rp = roll[(roll.stat == "dsharpe_matched_once")]
rp = rp[rp.apply(lambda x: PAR.get(x.rung) == x.reference, axis=1)].set_index("rung").loc[LAYERS]
fig, ax = plt.subplots(figsize=(9, 3.8))
ax.barh(yy, rp.share_pos, color=fg.BLUE, height=0.55)
for yi, r in zip(yy, rp.itertuples(), strict=True):
    ax.text(r.share_pos + 0.01, yi, f"{r.share_pos:.0%}  (median {r.median:+.2f}, range {r.min:+.2f} … {r.max:+.2f})",
            va="center", fontsize=7)
ax.axvline(0.5, color=fg.BASE, lw=1, ls="--")
ax.set_xlim(0, 1.25)
ax.set_yticks(yy, [lab(r) for r in LAYERS])
ax.set_xlabel("share of trailing 5-year (1,260-session) windows with ΔSharpe > 0 vs the parent")
ax.set_title("Rolling 5-year: how often each layer beat its parent")
note(fig)
fg.save(fig, OUT, "rolling_5y_share_beating_parent")

# 6. bond maturity, band width, calendar ------------------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), sharey=True)
order = ["L1", "L3", "L4", "L5", "L6", "L7", "L8"]
for ax, (fac, title) in zip(axes, [("maturity_years", "TLT leg maturity (25y registered)"),
                                   ("band_pp", "band width, pp (5 registered)"), ("calendar", "calendar (monthly registered)")],
                            strict=True):
    s = sens[sens.factor == fac]
    vals = list(dict.fromkeys(s.value))
    yof = dict(zip(order, np.arange(len(order))[::-1], strict=True))  # one row grid for all panels (shared y)
    reg = s.groupby("rung").registered_sharpe.first()
    ax.scatter(reg, [yof[r] for r in reg.index], marker="|", s=200, color=fg.INK, label="registered", zorder=3)
    for j, v in enumerate(vals):
        q = s[s.value == v].set_index("rung")
        ax.scatter(q.sharpe, [yof[r] for r in q.index], s=24, color=[fg.BLUE, fg.ORANGE, fg.AQUA][j % 3], label=str(v),
                   zorder=2)
    ax.set_yticks(list(yof.values()), [LAB[r] for r in yof])
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("development excess Sharpe")
    ax.legend(fontsize=7, loc="lower right")
fig.suptitle("Sensitivity, one factor at a time (descriptive; 10/20/30y legs: GSW constant-maturity proxies, not QA'd vs an ETF)",
             fontsize=10, fontweight="bold", color=fg.INK, y=1.02)
note(fig, y=-0.06)
fg.save(fig, OUT, "sensitivity_maturity_band_calendar")

# 7. return vs CDaR, rungs and sensitivity variants ---------------------------------------------------------------------------------
one = costs[(costs.book == "1x")].drop_duplicates("rung").set_index("rung")
fig, ax = plt.subplots(figsize=(8, 5))
ax.scatter(sens.cdar95, sens.cagr, s=14, color=fg.BASE, label="sensitivity variants")
for r, row in one.iterrows():
    ax.scatter(row.cdar95, row.cagr, s=40, color=fg.BLUE if r != "L0" else fg.INK)
    ax.annotate(LAB[r], (row.cdar95, row.cagr), xytext=(4, 2), textcoords="offset points", fontsize=7)
ax.set_xlabel("CDaR-95 (compounded, development)")
ax.set_ylabel("CAGR (development)")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1%}"))
ax.legend(fontsize=8)
ax.set_title("Return vs CDaR-95: built rungs (1× costs) and the 41 sensitivity books")
note(fig, "The SPY + T-bills line at each rung's vol is in costs.csv (ΔSharpe vs line).")
fg.save(fig, OUT, "return_vs_cdar")

# 8. DSR and PBO -------------------------------------------------------------------------------------------------------------------
h = dsr[dsr.pool.str.startswith("headline")].set_index("rung")
ng = dsr[dsr.pool == "without v1 grid"].set_index("rung")
rn = dsr[dsr.pool.str.startswith("raw N")].set_index("rung")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4), gridspec_kw={"width_ratios": [2, 1]})
yd = np.arange(len(h))[::-1]
a1.barh(yd, h.dsr, color=fg.BLUE, height=0.55, label=f"headline (n_eff + 1 = {int(h.n_used.iloc[0])})")
a1.scatter(ng.loc[h.index].dsr, yd, marker="|", s=150, color=fg.ORANGE, label=f"without v1's grid (n = {int(ng.n_used.iloc[0])})", zorder=3)
a1.scatter(rn.loc[h.index].dsr, yd, marker="x", s=30, color=fg.RED, label=f"raw N = {int(rn.n_used.iloc[0])}", zorder=3)
a1.axvline(0.95, color=fg.BASE, ls="--", lw=1)
a1.set_yticks(yd, [LAB.get(r, r) for r in h.index], fontsize=8)
a1.set_xlabel("deflated Sharpe ratio (P[true Sharpe > expected best of the null trials])")
a1.legend(fontsize=7, loc="lower left")
a1.set_title(f"DSR, effective trials (ρ* 0.5): {facts['dsr_pool']['n_raw_columns']} series → n_eff {facts['dsr_pool']['n_eff']}", fontsize=9)
p = pbo.copy()
short = {"primary (zoo)": "zoo", "secondary (rungs + sensitivity + zoo)": "all rungs", "primary, near-duplicates dropped (1e-12; descriptive)": "zoo ≈dedup"}
p["lab"] = p.pool.map(short) + " S=" + p.blocks.astype(str)
a2.barh(np.arange(len(p))[::-1], p.pbo, color=[fg.BLUE if r == "primary" else fg.BASE for r in p.role], height=0.55)
a2.set_yticks(np.arange(len(p))[::-1], p.lab, fontsize=8)
a2.axvline(0.5, color=fg.INK2, ls="--", lw=1)
a2.set_xlim(0, 1)
a2.set_xlabel("PBO (CSCV)")
a2.set_title("Probability of backtest overfitting (blue = registered primary)", fontsize=9)
note(fig, "DSR tests the Sharpe against zero after selection, not an edge over SPY.", y=-0.06)
fg.save(fig, OUT, "dsr_and_pbo")

# 9. power: years needed to confirm each layer's measured edge --------------------------------------------------------------------
pp = pw[pw.apply(lambda x: PAR.get(x.rung) == x.reference, axis=1)].set_index("rung").loc[LAYERS]
fig, ax = plt.subplots(figsize=(9, 3.8))
cap = 1000
v = pp.years_needed.replace(np.inf, np.nan)
ax.barh(yy, v.fillna(cap).clip(upper=cap), color=[fg.BLUE if np.isfinite(x) else fg.BASE for x in v], height=0.55)
for yi, (_r, row) in zip(yy, pp.iterrows(), strict=True):
    t = "∞ (measured edge ≤ 0)" if not np.isfinite(row.years_needed) else f"{row.years_needed:,.0f} y (ΔSharpe {row.dsharpe:+.3f}, ρ {row.rho:.2f})"
    ax.text(min(row.years_needed if np.isfinite(row.years_needed) else cap, cap) * 1.05, yi, t, va="center", fontsize=7)
ax.axvline(30, color=fg.RED, ls="--", lw=1)
ax.text(31, yy[0] + 0.4, "development sample = 30 y", fontsize=7, color=fg.RED)
ax.set_xscale("log")
ax.set_xlim(1, cap * 30)
ax.set_yticks(yy, [lab(r) for r in LAYERS])
ax.set_xlabel("years of daily data for 80% power (one-sided α 0.05), if the measured ΔSharpe were the truth")
ax.set_title("Power: how long it would take to confirm each layer's edge")
note(fig, "quantkit.stats.power: " + pp.header.iloc[0] + "; optimistic (point estimate taken as the true effect).")
fg.save(fig, OUT, "power_years_needed")

# 10. the three O3.1 zoo rows vs L5 --------------------------------------------------------------------------------------------------
zp = zoo[zoo.reference.str.startswith("L5")].reset_index(drop=True)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3), sharey=True)
yz = np.arange(len(zp))[::-1]
for yi, r in zip(yz, zp.itertuples(), strict=True):
    a1.plot([r.lo, r.hi], [yi, yi], color=fg.BLUE, lw=2, alpha=0.4)
    a1.plot(r.dsharpe, yi, "o", color=fg.BLUE)
    a1.text(r.hi + 0.005, yi, f"{r.dsharpe:+.3f}", va="center", fontsize=8)
    a2.plot([r.cdar_lo, r.cdar_hi], [yi, yi], color=fg.ORANGE, lw=2, alpha=0.4)
    a2.plot(r.cdar_ratio, yi, "o", color=fg.ORANGE)
a1.axvline(0, color=fg.BASE)
a2.axvline(1, color=fg.BASE)
a1.set_yticks(yz, [f"{r.row} (turnover {r.turnover_pa:.1f}×/yr)" for r in zp.itertuples()], fontsize=8)
a1.set_xlabel("ΔSharpe vs matched L5 (LW 95%)")
a2.set_xlabel("CDaR-95 ratio vs matched L5 (paired bootstrap 95%)")
fig.suptitle("The three O3.1 zoo rows (+ raw GBM) vs their parent L5 (zoo: never promoted)", fontsize=10, fontweight="bold",
             color=fg.INK, y=1.03)
note(fig, y=-0.12)
fg.save(fig, OUT, "zoo_rows_vs_L5")
print("R4 figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")))
