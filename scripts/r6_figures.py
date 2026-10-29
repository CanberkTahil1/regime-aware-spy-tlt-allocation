"""R6 statistics figures -> reports/figures/R6/<name>.png|svg (committed). Owner O1.1: only committed statistics
(reports/r6/*.csv, facts.json) and the public-domain BLS CPI gate state are drawn here; curves from KF-derived series go to
the gitignored reports/figures_local/R6/ (scripts/r6_figures_local.py). Development 1990–2019 is "in-sample"; the test
2020-01 → 2026-09 is "disclosed reuse: ideas inspired by this window". Descriptive: an R6 verdict promotes nothing."""

import argparse
import json
import pathlib
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from r6lib import cpi  # noqa: E402
from rspy import figures as fg  # noqa: E402
from rspy import paths  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--src", default=str(paths.REPORTS / "r6"))
ap.add_argument("--out", default=str(paths.REPORTS / "figures" / "R6"))
a = ap.parse_args()
R, OUT = pathlib.Path(a.src), pathlib.Path(a.out)
plt.rcParams.update(fg.RC)
v = pd.read_csv(R / "verdict.csv")
cmp_ = pd.read_csv(R / "compare.csv")
m = pd.read_csv(R / "metrics.csv")
cz = pd.read_csv(R / "crisis.csv")
costs = pd.read_csv(R / "costs.csv")
dsr = pd.read_csv(R / "dsr.csv")
facts = json.loads((R / "facts.json").read_text())

LAB = {"R6a_L2_trend": "VT SPY + trend", "R6b_L3@5y": "60/40 @5y", "R6b_L4@5y": "InvVol @5y",
       "R6b_L5@5y": "InvVol+VT @5y", "R6b_L7@5y": "+Trend @5y", "R6b_L3@10y": "60/40 @10y", "R6b_L4@10y": "InvVol @10y",
       "R6b_L5@10y": "InvVol+VT @10y", "R6b_L7@10y": "+Trend @10y", "R6c_L6-63": "CorrReg 63d",
       "R6c_infl": "Inflation-vol gate", "R6d_L5_bondtrend": "Bond-only trend", "R6e_weekly": "Asym VT weekly",
       "R6e_ewma5": "Asym VT EWMA5", "R6f_blend": "1/3 blend", "L0": "SPY", "L1": "v1", "L2": "VT SPY", "L3": "60/40",
       "L4": "InvVol", "L5": "InvVol+VT", "L6": "+CorrReg", "L7": "+Trend", "line": "SPY+bills"}
W = facts["windows"]
NOTE = (f"Development {W['development']['first']} → {W['development']['last']}: in-sample. Test {W['test']['first']} → "
        f"{W['test']['last']}: disclosed reuse — ideas inspired by this window. Matched: the reference is rescaled once "
        "with T-bills to the candidate's excess vol within the window; 'SPY+bills' = SPY rescaled the same way. Own "
        "parent = the rung the idea changes (spec/prereg_r6.yaml). Verdict: better/worse = ΔSharpe ≥ +0.05 / ≤ −0.05, or "
        "CDaR-95 ≤ 0.85× / ≥ 1/0.85× without the opposite Sharpe move (D6.4). Descriptive: promotes nothing. SPY = SPY "
        "proxy (KF Hi 20); TLT = " + paths.rules()["bonds"]["label"] + "; 5y/10y legs: GSW constant maturity, not QA'd "
        "vs an ETF.")
COL = {"better in both periods": fg.BLUE, "better only in the period that inspired it": fg.ORANGE,
       "better in development only": fg.AQUA, "better in development, worse in the test": fg.YELLOW,
       "no real difference": fg.NEUTRAL, "worse": fg.RED, "worse in both periods": fg.RED}


def note(fig, extra="", y=-0.03):
    fig.text(0.01, y, "\n".join(textwrap.wrap(NOTE + (" " + extra if extra else ""), 175)), fontsize=7, color=fg.INK2,
             va="top")


cands = v.candidate.tolist()

# 1. own-parent ΔSharpe, development vs test, with LW 95% intervals and the verdict ---------------------------------------
fig, ax = plt.subplots(figsize=(10, 7))
yy = np.arange(len(v))[::-1]
for yi, r in zip(yy, v.itertuples(index=False), strict=True):
    ax.plot([r.development_lo, r.development_hi], [yi + 0.15, yi + 0.15], color=fg.AQUA, lw=2, alpha=0.45)
    ax.plot(r.development_dsharpe, yi + 0.15, "o", color=fg.AQUA, ms=5)
    ax.plot([r.test_lo, r.test_hi], [yi - 0.15, yi - 0.15], color=fg.ORANGE, lw=2, alpha=0.45)
    ax.plot(r.test_dsharpe, yi - 0.15, "o", color=fg.ORANGE, ms=5)
    ax.text(1.02, yi, r.verdict, transform=ax.get_yaxis_transform(), fontsize=7, va="center", color=COL[r.verdict])
for xv, ls in ((0, "-"), (0.05, ":"), (-0.05, ":")):
    ax.axvline(xv, color=fg.BASE if xv == 0 else fg.MUTED, lw=1 if xv == 0 else 0.8, ls=ls)
ax.set_yticks(yy, [f"{LAB[r.candidate]} vs {LAB[r.own_parent]}" for r in v.itertuples(index=False)], fontsize=8)
ax.set_xlabel("ΔSharpe vs own parent at matched risk (annualised excess Sharpe), LW 95%")
ax.set_title("R6: each post-test idea vs the rung it changes, development and test")
ax.plot([], [], "o", color=fg.AQUA, label="development 1990–2019 (in-sample)")
ax.plot([], [], "o", color=fg.ORANGE, label="test 2020–2026 (inspired the idea)")
ax.legend(fontsize=7, loc="lower left")
note(fig)
fg.save(fig, OUT, "r6_dsharpe_own_parent_dev_vs_test")

# 2. development vs test scatter: the 'inspired it' quadrant -----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 6))
for r in v.itertuples(index=False):
    ax.plot(r.development_dsharpe, r.test_dsharpe, "o", color=COL[r.verdict], ms=7)
    ax.annotate(LAB[r.candidate], (r.development_dsharpe, r.test_dsharpe), fontsize=7, xytext=(4, 3),
                textcoords="offset points")
for f in (ax.axvline, ax.axhline):
    f(0, color=fg.BASE, lw=1)
    f(0.05, color=fg.MUTED, lw=0.6, ls=":")
    f(-0.05, color=fg.MUTED, lw=0.6, ls=":")
for k, c in COL.items():
    if k in set(v.verdict):
        ax.plot([], [], "o", color=c, label=k)
ax.set_xlabel("development ΔSharpe vs own parent (in-sample)")
ax.set_ylabel("test ΔSharpe vs own parent (inspired the idea)")
ax.set_title("Does the gain show up outside the period that suggested it?")
ax.legend(fontsize=7, loc="upper left")
note(fig, "Points use the Sharpe leg; a drawdown-leg verdict (VT SPY + trend in development, CDaR 0.59×) can sit inside "
     "the ±0.05 band.", y=-0.05)
fg.save(fig, OUT, "r6_dev_vs_test_scatter")

# 3. ΔSharpe vs VT SPY, 60/40 and SPY+bills, both windows ---------------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(13, 6), sharey=True)
yy = np.arange(len(cands))[::-1]
for ax, ref in zip(axes, ["L2", "L3", "line"], strict=True):
    for w, off, col in (("development", 0.15, fg.AQUA), ("test", -0.15, fg.ORANGE)):
        d = cmp_[(cmp_.reference == ref) & (cmp_.window == w) & (cmp_.kind != "own")].set_index("candidate").loc[cands]
        ax.errorbar(d.dsharpe, yy + off, xerr=[d.dsharpe - d.lo, d.hi - d.dsharpe], fmt="o", color=col, ms=4,
                    elinewidth=1.5, alpha=0.8, label=w)
    ax.axvline(0, color=fg.BASE)
    ax.set_title(f"vs {LAB[ref]}")
axes[0].set_yticks(yy, [LAB[c] for c in cands], fontsize=8)
axes[0].legend(fontsize=7)
axes[1].set_xlabel("ΔSharpe at matched risk, LW 95%")
note(fig, y=-0.04)
fg.save(fig, OUT, "r6_dsharpe_vs_vt_spy_6040_line")

# 4. COVID and 2022 at matched risk vs own parent ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
for ax, k in zip(axes, ["covid", "infl_2022"], strict=True):
    d = cz[(cz.crisis == k) & cz.own_parent].set_index("candidate").loc[cands]
    xx = np.arange(len(cands))
    ax.bar(xx - 0.2, d.child_return, 0.4, color=fg.BLUE, label="candidate")
    ax.bar(xx + 0.2, d.parent_matched_return, 0.4, color=fg.ORANGE, label="own parent at matched vol")
    ax.axhline(0, color=fg.BASE)
    ax.set_xticks(xx, [LAB[c] for c in cands], fontsize=7, rotation=60, ha="right")
    ax.set_title(fg.CRISIS_LABELS[k])
axes[0].set_ylabel("cumulative return in window")
axes[0].legend(fontsize=7)
note(fig, "Matched on the whole test window (crises included; in-crisis vols are not matched).", y=-0.2)
fg.save(fig, OUT, "r6_crisis_covid_2022_matched")

# 5. R6e: turnover vs Sharpe -----------------------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
for ax, w in zip(axes, ["development", "test"], strict=True):
    for r, c in (("L2", fg.NEUTRAL), ("R6e_weekly", fg.BLUE), ("R6e_ewma5", fg.AQUA)):
        q = m[(m.row == r) & (m.window == w)].iloc[0]
        ax.plot(q.turnover_pa, q.sharpe_excess, "o", color=c, ms=8, label=LAB[r])
        ax.annotate(f"{q.turnover_pa:.1f}×, cost {q.cost_pa * 1e4:.0f} bp", (q.turnover_pa, q.sharpe_excess), fontsize=7,
                    xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("traded turnover per year (one-way)")
    ax.set_title(w)
axes[0].set_ylabel("excess Sharpe")
axes[0].legend(fontsize=7)
note(fig, "Asymmetric vol targeting: cuts the same day; step-ups weekly (Friday anchor, disclosed) or by EWMA span 5. "
     "Unmatched Sharpe here; the matched ΔSharpe is in figure 1.", y=-0.06)
fg.save(fig, OUT, "r6e_turnover_vs_sharpe")

# 6. return vs CDaR, both windows ---------------------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for ax, w in zip(axes, ["development", "test"], strict=True):
    d = m[m.window == w].set_index("row")
    for r in cands + ["L0", "L2", "L3", "L5", "L7"]:
        is_ref = not r.startswith("R6")
        ax.plot(d.loc[r, "cdar95"], d.loc[r, "cagr"], "s" if is_ref else "o", color=fg.NEUTRAL if is_ref else fg.BLUE)
        ax.annotate(LAB[r], (d.loc[r, "cdar95"], d.loc[r, "cagr"]), fontsize=6, xytext=(3, 2), textcoords="offset points")
    for r in cands:
        ax.plot(d.loc[f"{r}-line", "cdar95"], d.loc[f"{r}-line", "cagr"], "x", color=fg.MUTED, ms=4)
    ax.set_xlabel("CDaR-95")
    ax.set_title(w)
axes[0].set_ylabel("CAGR")
axes[0].plot([], [], "x", color=fg.MUTED, label="SPY+bills at each candidate's vol (ex ante)")
axes[0].plot([], [], "s", color=fg.NEUTRAL, label="R5 reference rung")
axes[0].legend(fontsize=7)
note(fig, y=-0.05)
fg.save(fig, OUT, "r6_return_vs_cdar")

# 7. DSR, both windows ----------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 3.6))
xx = np.arange(len(cands))
for i, (w, c) in enumerate((("development", fg.AQUA), ("test", fg.ORANGE))):
    d = dsr[(dsr.window == w) & dsr.pool.str.startswith("headline")].set_index("candidate").loc[cands]
    ax.bar(xx + (i - 0.5) * 0.4, d.dsr, 0.4, color=c, label=f"{w}, N = {int(d.n_used.iloc[0])}")
ax.axhline(0.95, color=fg.RED, lw=0.8, ls=":")
ax.set_xticks(xx, [LAB[c] for c in cands], fontsize=7, rotation=45, ha="right")
ax.set_ylabel("deflated Sharpe ratio")
ax.set_title("Deflated Sharpe ratio with every R6 row counted")
ax.legend(fontsize=7)
note(fig, "N: development R4 n_used 4 + 15 R6 rows; test R5 N 5 + 15; trial variance max(V_dev, 1/(T−1)).", y=-0.18)
fg.save(fig, OUT, "r6_dsr")

# 8. costs and financing ------------------------------------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
for ax, w in zip(axes, ["development", "test"], strict=True):
    for i, (k, c) in enumerate([("1x", fg.BLUE), ("2x", fg.YELLOW), ("3x", fg.RED), ("f75", fg.AQUA)]):
        d = costs[(costs.window == w) & (costs.book == k)].set_index("candidate").loc[cands]
        ax.bar(xx + (i - 1.5) * 0.2, d.dsharpe_vs_own_parent, 0.2, color=c,
               label={"f75": "+75 bp financing"}.get(k, f"{k} costs"))
    ax.axhline(0, color=fg.BASE)
    ax.set_ylabel(f"ΔSharpe vs own parent\n({w})")
axes[1].set_xticks(xx, [LAB[c] for c in cands], fontsize=7, rotation=45, ha="right")
axes[0].legend(fontsize=7, ncol=4)
axes[0].set_title("Costs and financing stress: candidate and parent stressed alike")
note(fig, y=-0.1)
fg.save(fig, OUT, "r6_costs_dsharpe_vs_own_parent")

# 9. the inflation gate (public-domain BLS CPI): v vs its 10-year median ---------------------------------------------------
st = pd.read_parquet(cpi.data_dir() / "cpi_state.parquet") if (cpi.data_dir() / "cpi_state.parquet").exists() else None
if st is not None:
    st = st.assign(t=pd.PeriodIndex(st.month, freq="M").to_timestamp()).set_index("t").loc["1986":]
    fig, ax = plt.subplots(figsize=(11, 3.4))
    ax.plot(st.index, st.v * 100, color=fg.BLUE, lw=1.2, label="12-month std of monthly CPI-U NSA inflation (v)")
    ax.plot(st.index, st.med * 100, color=fg.ORANGE, lw=1.2, label="its 120-month median")
    hi = st.high.fillna(0).astype(bool)
    ax.fill_between(st.index, 0, 1, where=hi, transform=ax.get_xaxis_transform(), color=fg.RED, alpha=0.08, lw=0,
                    label="high: TLT to cash at the next month-end decision")
    ax.axvline(pd.Timestamp("2020-01-01"), color=fg.MUTED, lw=0.8, ls=":")
    ax.set_ylabel("% per month")
    ax.set_title("R6c inflation-volatility gate (BLS CPI-U NSA, CUUR0000SA0; month m used at the end of m+1)")
    ax.legend(fontsize=7, loc="upper left")
    note(fig, f"Share of month-end decisions with TLT gated: development {facts['infl_gate']['share_dev_decisions_high']:.0%},"
         f" test {facts['infl_gate']['share_test_decisions_high']:.0%}. 2025-10 not published (2025 lapse in "
         "appropriations); the gate stays defined (≥ 10 of 12 months). Source: U.S. Bureau of Labor Statistics.", y=-0.08)
    fg.save(fig, OUT, "r6c_inflation_vol_gate")
print("R6 figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")))
