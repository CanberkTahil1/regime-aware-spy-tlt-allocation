"""R5 statistics figures -> reports/figures/R5/<name>.png|svg (committed). Owner O1.1: only charts of committed
statistics (reports/r5/*.csv, *.json) are drawn here; curves from KF-derived series go to the gitignored
reports/figures_local/R5/ (scripts/r5_figures_local.py). Test window 2020-01 → 2026-09: frozen rules run once, "seen by
owner in v1, disclosed"; descriptive, cannot change any development verdict. `--src` / `--out` let the dry run's
synthetic output be drawn into a temporary directory (code check)."""

import argparse
import json
import pathlib
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import figures as fg  # noqa: E402
from rspy import paths  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--src", default=str(paths.REPORTS / "r5"))
ap.add_argument("--out", default=str(paths.REPORTS / "figures" / "R5"))
a = ap.parse_args()
R, OUT = pathlib.Path(a.src), pathlib.Path(a.out)
plt.rcParams.update(fg.RC)
fam = pd.read_csv(R / "family.csv")
m = pd.read_csv(R / "metrics.csv")
cz = pd.read_csv(R / "crisis.csv")
costs = pd.read_csv(R / "costs.csv")
dsr = pd.read_csv(R / "dsr.csv")
s10 = pd.read_csv(R / "sens10y.csv")
v12 = pd.read_csv(R / "v1_vs_v2.csv")
head = json.loads((R / "headline.json").read_text())
facts = json.loads((R / "facts.json").read_text())
LAB = {"L0": "SPY", "L1": "v1", "L2": "VT SPY", "L3": "60/40", "L4": "InvVol", "L5": "InvVol+VT", "L5-lev": "InvVol+VT 1.5x",
       "L6": "+CorrReg", "L7": "+Trend", "L8": "+Crash", "L2-u": "VT SPY 10%", "line": "SPY+bills"}
WIN = f"{facts['test_first']} → {facts['test_last']}"
NOTE = (f"Test window {WIN} ({facts['n_test_rows']} sessions): frozen rules run once; seen by owner in v1, disclosed; "
        "descriptive, cannot change any development verdict. Matched: the reference is rescaled once with T-bills to the "
        "rung's test-window excess vol (D5.2); the SPY+bills line is matched ex ante. SPY = SPY proxy (KF Hi 20); TLT = "
        + paths.rules()["bonds"]["label"] + ".")


def note(fig, extra="", y=-0.03):
    fig.text(0.01, y, "\n".join(textwrap.wrap(NOTE + (" " + extra if extra else ""), 175)), fontsize=7, color=fg.INK2,
             va="top")


# 1. the registered family: ΔSharpe at matched risk with LW 95% intervals, development point beside ------------------------
fig, ax = plt.subplots(figsize=(9, 8))
yy = np.arange(len(fam))[::-1]
for yi, r in zip(yy, fam.itertuples(index=False), strict=True):
    col = fg.BLUE if r.beat_holm else (fg.AQUA if r.beat_raw else fg.NEUTRAL)
    ax.plot([r.lo, r.hi], [yi, yi], color=col, lw=2, alpha=0.45)
    ax.plot(r.dsharpe, yi, "o", color=col, ms=6)
    ax.plot(r.dsharpe_dev, yi, "o", mfc="none", mec=fg.ORANGE, ms=6)
ax.axvline(0, color=fg.BASE, lw=1)
ax.axvline(0.05, color=fg.MUTED, lw=0.8, ls=":")
ax.set_yticks(yy, [f"{LAB[r.child]} vs {LAB.get(r.reference, r.reference)}" + (" (parent)" if r.kind == "parent" else "")
                   for r in fam.itertuples(index=False)], fontsize=8)
ax.set_xlabel("ΔSharpe at matched risk (annualised excess Sharpe)")
ax.set_title("Test window: each layer vs its parent, VT SPY, 60/40 and the SPY+bills line")
ax.plot([], [], "o", color=fg.NEUTRAL, label="test ΔSharpe, LW 95% (grey: no beat)")
ax.plot([], [], "o", color=fg.AQUA, label="beat at raw p < 0.05 and ≥ +0.05")
ax.plot([], [], "o", color=fg.BLUE, label="beat after Holm (24 rows)")
ax.plot([], [], "o", mfc="none", mec=fg.ORANGE, label="development 1990–2019 ΔSharpe (same pair)")
ax.legend(fontsize=7, loc="lower right")
note(fig, "Headline: " + "; ".join(f"{q}: {v['answer']}" for q, v in head.items()) + ".")
fg.save(fig, OUT, "family_dsharpe_test_vs_development")

# 2. what each layer added (ablation, parent rows) --------------------------------------------------------------------------
par = fam[fam.kind == "parent"]
fig, ax = plt.subplots(figsize=(9, 3.8))
x = np.arange(len(par))
ax.bar(x - 0.2, par.dsharpe, 0.4, color=fg.BLUE, label="test 2020–2026")
ax.errorbar(x - 0.2, par.dsharpe, yerr=[par.dsharpe - par.lo, par.hi - par.dsharpe], fmt="none", ecolor=fg.INK2, lw=1)
ax.bar(x + 0.2, par.dsharpe_dev, 0.4, color=fg.ORANGE, alpha=0.7, label="development 1990–2019")
ax.axhline(0, color=fg.BASE)
ax.set_xticks(x, [f"{LAB[c]}\nvs {LAB[p]}" for c, p in zip(par.child, par.reference, strict=True)], fontsize=8)
ax.set_ylabel("ΔSharpe vs parent (matched)")
ax.set_title("Ablation: what each layer added, test vs development")
ax.legend(fontsize=8)
note(fig)
fg.save(fig, OUT, "ablation_test_vs_development")

# 3. crisis panels: COVID and 2022 at matched risk --------------------------------------------------------------------------
rungs = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"]
fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax, k in zip(axes, ["covid", "infl_2022"], strict=True):
    d = cz[(cz.crisis == k) & cz.rung.isin(rungs)].set_index("rung").loc[rungs]
    xx = np.arange(len(rungs))
    ax.bar(xx - 0.27, d["return"], 0.27, color=fg.BLUE, label="rung")
    ax.bar(xx, d["line_return"], 0.27, color=fg.NEUTRAL, label="SPY+bills line at the rung's vol (ex ante)")
    ax.bar(xx + 0.27, d["parent_matched_return"].fillna(0), 0.27, color=fg.ORANGE, label="parent at matched vol")
    ax.axhline(0, color=fg.BASE)
    ax.set_xticks(xx, [LAB[r] for r in rungs], fontsize=7, rotation=30)
    ax.set_title(f"{fg.CRISIS_LABELS[k]} ({d['start'].iloc[0]} → {d['end'].iloc[0]})")
axes[0].set_ylabel("cumulative return in window")
axes[0].legend(fontsize=7)
note(fig, "k uses the whole test window's vol, crises included (in-crisis vols are not matched). SPY and v1 have no "
     "parent bar.", y=-0.06)
fg.save(fig, OUT, "crisis_covid_2022_matched")

# 4. v1 vs v2 side by side ------------------------------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
yy = np.arange(len(v12))[::-1]
for ax, (col, t) in zip(axes, [("cagr", "CAGR"), ("sharpe_excess", "excess Sharpe"), ("max_dd", "max drawdown")],
                        strict=True):
    ax.barh(yy, v12[col], color=[fg.RED if r == "S0" else (fg.ORANGE if r == "L1" else fg.BLUE) for r in v12.rung])
    ax.set_title(t)
    ax.axvline(0, color=fg.BASE)
axes[0].set_yticks(yy, [f"{r} [{w.split(' .. ')[1][:7]}]" for r, w in zip(v12.row, v12.window, strict=True)], fontsize=8)
note(fig, "v1 as committed (S0) is v1's own test 2020-01 → 2025-12 on Yahoo/Cboe with v1's accounting (seen; R1); every "
     "other row is the R5 test window with the charter accounting on permitted data.", y=-0.06)
fg.save(fig, OUT, "v1_vs_v2_side_by_side")

# 5. costs and financing on the test window ---------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 3.6))
lay = list(dict.fromkeys(costs.rung))
xx = np.arange(len(lay))
for i, (k, col) in enumerate([("1x", fg.BLUE), ("2x", fg.YELLOW), ("3x", fg.RED), ("f75", fg.AQUA)]):
    v = costs[costs.book == k].set_index("rung").loc[lay, "dsharpe_vs_parent"]
    ax.bar(xx + (i - 1.5) * 0.2, v, 0.2, color=col, label={"f75": "+75 bp financing"}.get(k, f"{k} costs"))
ax.axhline(0, color=fg.BASE)
ax.set_xticks(xx, [f"{LAB[r]}\nvs {LAB[p]}" for r, p in zip(lay, costs.drop_duplicates("rung").parent, strict=True)],
              fontsize=8)
ax.set_ylabel("ΔSharpe vs parent (matched)")
ax.set_title("Costs and financing: each layer vs its parent on the test window")
ax.legend(fontsize=7, ncol=4)
note(fig, "Frozen rules re-scored (robustness legs, not trials).")
fg.save(fig, OUT, "costs_dsharpe_vs_parent_test")

# 6. return vs CDaR with the lines -------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 5))
one = m[m.book == "1x"].set_index("rung")
for r in rungs:
    ax.plot(one.loc[r, "cdar95"], one.loc[r, "cagr"], "o", color=fg.BLUE)
    ax.annotate(LAB[r], (one.loc[r, "cdar95"], one.loc[r, "cagr"]), fontsize=7, xytext=(4, 3), textcoords="offset points")
    ax.plot(one.loc[f"{r}-line", "cdar95"], one.loc[f"{r}-line", "cagr"], "x", color=fg.NEUTRAL)
ax.plot([], [], "x", color=fg.NEUTRAL, label="SPY+bills line at each rung's vol (ex ante)")
ax.set_xlabel("CDaR-95 (test window)")
ax.set_ylabel("CAGR (test window)")
ax.set_title("Return vs drawdown risk, test window")
ax.legend(fontsize=7)
note(fig, y=-0.06)
fg.save(fig, OUT, "return_vs_cdar_test")

# 7. DSR: test (headline N 5, raw N 751) beside development --------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 3.4))
hd = dsr[dsr.pool.str.startswith("headline")].set_index("rung").loc[rungs]
rw = dsr[dsr.pool.str.startswith("raw")].set_index("rung").loc[rungs]
xx = np.arange(len(rungs))
ax.bar(xx - 0.27, hd.dsr, 0.27, color=fg.BLUE, label="test, N = 5")
ax.bar(xx, rw.dsr, 0.27, color=fg.NEUTRAL, label="test, raw N = 751")
if "dsr_development_headline" in hd:
    ax.bar(xx + 0.27, hd.dsr_development_headline, 0.27, color=fg.ORANGE, alpha=0.7, label="development (R4 headline)")
ax.axhline(0.95, color=fg.RED, lw=0.8, ls=":")
ax.set_xticks(xx, [LAB[r] for r in rungs], fontsize=8)
ax.set_ylabel("deflated Sharpe ratio")
ax.set_title("Deflated Sharpe ratio, test window vs development")
ax.legend(fontsize=7)
note(fig, "N from the development register (D5.4); trial variance max(V_dev, 1/(T−1)).")
fg.save(fig, OUT, "dsr_test_vs_development")

# 8. the owner's post-hoc 10-year row --------------------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
xx = np.arange(len(s10))
axes[0].bar(xx - 0.2, s10.sharpe_25y, 0.4, color=fg.BLUE, label="25-year leg (official)")
axes[0].bar(xx + 0.2, s10.sharpe_10y, 0.4, color=fg.AQUA, label="10-year leg (post-hoc)")
axes[0].set_xticks(xx, [LAB[r] for r in s10.rung])
axes[0].set_title("Excess Sharpe, test window")
axes[0].legend(fontsize=7)
axes[1].bar(xx - 0.2, s10.infl_2022_return_25y, 0.4, color=fg.BLUE)
axes[1].bar(xx + 0.2, s10.infl_2022_return_10y, 0.4, color=fg.AQUA)
axes[1].axhline(0, color=fg.BASE)
axes[1].set_xticks(xx, [LAB[r] for r in s10.rung])
axes[1].set_title("Return in 2022-01 → 2022-10")
note(fig, s10.label.iloc[0] + ".", y=-0.06)
fg.save(fig, OUT, "sensitivity_10y_bond_leg_test")
print("R5 figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")))
