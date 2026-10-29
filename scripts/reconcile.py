"""make reconcile (R1): the legacy reconciliation table S0 → S7 (D1.4) and the data QA (D1.6).

Committed (derived statistics only, D1.4/D1.6): reports/r1/reconciliation.csv|md, reports/r1/qa.csv, reports/r1/facts.json.
Local only (gitignored, derived from Yahoo/Cboe/KF data): data/r1/books.parquet (daily books for the charts).
Reads v1's local cached data/prices.csv (hash-checked, yfinance stubbed: D0.2/D0.3) and data/panel.parquet.
"""

import contextlib
import io
import json
import os
import sys
import time

os.environ.setdefault("MPLBACKEND", "Agg")
from tests.legacy_support import check_v1_data, yfinance_stub  # noqa: E402

sys.modules["yfinance"] = yfinance_stub()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rspy import legacy_bridge as lb  # noqa: E402
from rspy import paths  # noqa: E402
from rspy.data import build, readers  # noqa: E402

t0 = time.perf_counter()
rules = paths.rules()
OUT = paths.REPORTS / "r1"
LOCAL = paths.data_dir() / "r1"
OUT.mkdir(parents=True, exist_ok=True)
LOCAL.mkdir(parents=True, exist_ok=True)

# ---- inputs ---------------------------------------------------------------------------------------------------------
v1data = __import__("legacy.data", fromlist=["x"])
v1data.DATA_PATH = check_v1_data()
with contextlib.redirect_stdout(io.StringIO()):
    v1_prices, v1_returns = v1data.prepare_data()
h15 = readers.read_h15(build.raw_files()["h15"], series=rules["bills"]["series"])
v1_bills = build.bill_returns(h15, pd.DatetimeIndex(v1_prices.index), rules["bills"]["days"]).set_index("date")
v1_bills = v1_bills.rename(columns={"ret": "bill"})
panel = build.load()
win = {k: [str(a), str(z)] for k, (a, z) in rules["legacy"]["windows"].items()}
start, end = v1_prices.index[0], pd.Timestamp(win["test"][1])
new_prices, new_returns, new_bills = lb.new_data_inputs(panel, start, end, rules["legacy"]["vix_proxy"]["window"])

books = lb.reconcile(v1_prices, v1_returns, v1_bills, new_prices, new_returns, new_bills, rules)

# ---- table ----------------------------------------------------------------------------------------------------------
WINDOWS = {k: (pd.Timestamp(a), pd.Timestamp(z)) for k, (a, z) in win.items()}
rows = []
for step in lb.STEPS:
    b = books[step]
    bill = (new_bills if step == "S7" else v1_bills)["bill"]
    for wname, (a, z) in WINDOWS.items():
        x = b.loc[a:z]
        v1m = lb.v1_metrics(b["net"], (a, z))
        cm = lb.charter_metrics(b["net"], bill, (a, z))
        head = v1m if step in ("S0", "S1", "S2", "S3") else cm  # S4 switches the metric definitions
        row = {"step": step, "window": wname, "start": str(x.index[0].date()), "end": str(x.index[-1].date()),
               "n": len(x), "cagr": head["cagr"], "vol": head["vol"], "sharpe": head["sharpe"],
               "sortino": head["sortino"], "max_dd": head["max_dd"], "sharpe_v1_def": v1m["sharpe"],
               "sharpe_excess": cm["sharpe"], "sortino_v1_def": v1m["sortino"], "sortino_standard": cm["sortino"],
               "turnover_pa": x["turnover"].mean() * 252, "cost_pa": x["cost"].mean() * 252,
               "gross_pa": (x["gross"] + x["cash"]).mean() * 252, "net_pa": x["net"].mean() * 252,
               "cash_pa": x["cash"].mean() * 252, "financing_pa": x["financing"].mean() * 252,
               "avg_gross": x["gross_exp"].mean(),
               "metric_def": "v1 (Sharpe w/o rf, v1 Sortino)" if step in ("S0", "S1", "S2", "S3") else "charter (excess)"}
        rows.append(row)
tab = pd.DataFrame(rows)
tab.to_csv(OUT / "reconciliation.csv", index=False, float_format="%.10g")

# ---- facts for the expectations -------------------------------------------------------------------------------------
facts: dict = {}
s0_signal_turnover = {}
run = __import__("legacy.run", fromlist=["x"])
sig0 = lb.v1_signals(v1_prices, v1_returns)
for wname, (a, z) in WINDOWS.items():
    bt = __import__("legacy.backtest", fromlist=["x"])
    s0_signal_turnover[wname] = bt.compute_turnover_on_window(sig0, a, z)
facts["v1_reported_turnover_signal_def"] = s0_signal_turnover
sc = books["_scaled_S0"].loc[:win["validation"][1]]
facts["v1_short_share_2005_2019"] = {"SPY": float((sc["SPY_pos"] < 0).mean()), "TLT": float((sc["TLT_pos"] < 0).mean())}
fin_rows = books["S2"]
held_inv = (books["S1"]["gross_exp"])  # S1 held = S2 held
facts["S2_financing_rows_negative"] = int((fin_rows["financing"] < 0).sum())
facts["S3_equals_S4_returns_exact"] = bool(books["S3"]["net"].equals(books["S4"]["net"]))
facts["S7_min_weight"] = float(books["S7"][["w_SPY", "w_TLT"]].min().min())
vs = books["_vix_score_corr_inputs"].loc[:win["validation"][1]]
score = lambda s: ((s / s.rolling(10, min_periods=10).mean()) - 1).clip(0, 2)  # noqa: E731 (v1's formula, descriptive)
facts["vix_score_corr_vix_vs_rv_2005_2019"] = float(score(vs["vix"]).corr(score(vs["rv"])))

# ---- data QA (D1.6): monthly, 2005-01 -> 2025-12, local Yahoo as comparison only ------------------------------------
qa_cfg = rules["qa"]
ya = v1_returns.loc["2005-01-04":"2025-12-31", ["SPY", "TLT"]]
kf = panel.loc["2005-01-04":"2025-12-31", ["hi20", "tlt25"]]
mon = lambda d: (1 + d).groupby(d.index.to_period("M")).prod() - 1  # noqa: E731
my, mk = mon(ya), mon(kf)
qa_rows = []
for name, proxy, etf, band in [("hi20_vs_spy", "hi20", "SPY", qa_cfg["bands"]["hi20_vs_spy"]),
                               ("gsw25_vs_tlt", "tlt25", "TLT", qa_cfg["bands"]["gsw25_vs_tlt"])]:
    for sub, (a, z) in {"2005-2025": ("2005-01", "2025-12"), "2005-2019": ("2005-01", "2019-12"),
                        "2020-2025 (test, seen)": ("2020-01", "2025-12")}.items():
        p_, e_ = mk[proxy].loc[a:z], my[etf].loc[a:z]
        d = p_ - e_
        dd = kf[proxy].loc[str(a):str(z) + "-31"] - ya[etf].reindex(kf.index).loc[str(a):str(z) + "-31"]
        qa_rows.append({"pair": name, "sample": sub, "months": len(d), "corr": p_.corr(e_),
                        "te_pa": d.std(ddof=1) * np.sqrt(12), "mean_diff_pa": d.mean() * 12,
                        "daily_corr": kf[proxy].loc[dd.index].corr(ya[etf].reindex(kf.index).loc[dd.index]),
                        "corr_min": band["corr_min"] if sub == "2005-2025" else np.nan,
                        "te_max": band["te_max"] if sub == "2005-2025" else np.nan,
                        "role": "scored (E1.7)" if sub == "2005-2025" else "descriptive"})
qa = pd.DataFrame(qa_rows)
qa["pass"] = np.where(qa["role"].str.startswith("scored"), (qa["corr"] >= qa["corr_min"]) & (qa["te_pa"] <= qa["te_max"]), np.nan)
qa.to_csv(OUT / "qa.csv", index=False, float_format="%.10g")
facts["runtime_s"] = round(time.perf_counter() - t0, 2)
(OUT / "facts.json").write_text(json.dumps(facts, indent=1, sort_keys=True, default=float))

# ---- local daily books for the charts (gitignored) ------------------------------------------------------------------
keep = {}
for step in lb.STEPS:
    b = books[step]
    keep[step] = b[["net", "gross_exp", "turnover", "cost", "cash", "financing"]].add_prefix(f"{step}_")
loc = pd.concat(keep.values(), axis=1)
loc = loc.join(books["S7"][["w_SPY", "w_TLT"]].add_prefix("S7_"), how="left")
loc = loc.join(books["S0"].rename(columns={"gross_exp": "x"})[[]], how="left")
loc["spy_proxy"] = panel["hi20"].reindex(loc.index)
loc["bill_new"] = new_bills["bill"].reindex(loc.index)
loc["bill_v1"] = v1_bills["bill"].reindex(loc.index)
loc["spy_v1"] = v1_returns["SPY"].reindex(loc.index)
loc.to_parquet(LOCAL / "books.parquet")

# ---- markdown table ---------------------------------------------------------------------------------------------------
pct = lambda v: f"{100 * v:.1f}%"  # noqa: E731
lines = ["| Step | Window | CAGR | Vol | Sharpe | Sortino | Max DD | Turnover/yr | Cost/yr | Cash/yr | Fin./yr | Gross |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in tab.itertuples():
    lines.append(f"| {r.step} | {r.window} | {pct(r.cagr)} | {pct(r.vol)} | {r.sharpe:.2f} | {r.sortino:.2f} | "
                 f"{pct(r.max_dd)} | {r.turnover_pa:.1f}× | {pct(r.cost_pa)} | {pct(r.cash_pa)} | {pct(r.financing_pa)} | "
                 f"{r.avg_gross:.2f} |")
caption = [
    "# R1 legacy reconciliation: v1 → L1, one correction per step",
    "",
    "Steps (cumulative, order fixed before any result, D1.4; attribution is order-dependent): "
    + "; ".join(f"**{k}** {v}" for k, v in rules["legacy"]["steps"].items()) + ".",
    "",
    "Metrics: S0–S3 use v1's own definitions (Sharpe without the risk-free rate, v1's Sortino); from S4 on, Sharpe is",
    "on returns over H.15 bills and Sortino uses the standard downside deviation vs 0. Turnover = annualised one-way",
    "traded Σ|Δw| (S0–S2 without drift, S3+ with drift; v1's own reported figure, signal changes only, was "
    + f"{s0_signal_turnover['test']:.2f}× in test). Cost, cash and financing are mean contributions per year.",
    "Windows: v1's train 2005–14 and validation 2015–19 (in-sample: v1 chose its parameters there); test 2020–25 =",
    "**seen by owner in v1, disclosed**. S0–S6 run on v1's local Yahoo/Cboe file (statistics only; the file is never",
    "committed); S7 runs on permitted data: SPY proxy (KF Hi 20), " + rules["bonds"]["label"] + ", H.15 bills.",
    "Produced by `make reconcile` (scripts/reconcile.py); figures in reports/figures/R1/.",
    "",
]
(OUT / "reconciliation.md").write_text("\n".join(caption + lines) + "\n")
print(tab[["step", "window", "cagr", "sharpe", "sharpe_excess", "max_dd", "turnover_pa", "avg_gross"]].round(4).to_string())
print(qa[["pair", "sample", "months", "corr", "te_pa", "mean_diff_pa", "pass"]].round(4).to_string())
print(json.dumps(facts, indent=1, default=float))
print(f"reconcile: {time.perf_counter() - t0:.1f} s")
