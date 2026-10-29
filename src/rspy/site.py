"""The phase chart page (charter "Charts every phase"): committed R1 results (reports/r1/*.csv) → a `quantkit.results`
bundle → the `quantkit.viz` page reports/site/index.html. Adapted in form from naive-vs-optimal `src/nvo/site.py` @
b29bb37 (COPIED.md).

No new numbers: every value is a field of a committed CSV copied as stored (the loss parts are the CSV's annualised
gross, cost, financing and net). Absent by rule: daily return series (derived from Yahoo/Cboe/KF data, never committed,
D1.4), so quantkit's equity / drawdown / rolling-Sharpe charts are labelled placeholders; those curves are drawn in
reports/figures/R1/ from the local books. Evidence tier: v1's train and validation windows are "in-sample" (v1 chose
its parameters on them); the test window 2020+ is "disclosed-reuse" (seen by the owner in v1). Timing: none (ex post).
"""

from __future__ import annotations

import subprocess

import numpy as np
import pandas as pd
from quantkit import results as qr

from rspy import paths

TIER = {"train": "in-sample", "validation": "in-sample", "test": "disclosed-reuse"}
LICENCE = ("derived statistics only; S0-S6 and the QA from v1's local Yahoo/Cboe file (never committed); S7 from KF Hi 20 "
           "(terms unclear: gitignored, never redistributed), GSW and H.15 (public domain)")
METRICS = [("cagr", "per year"), ("vol", "annualised"), ("sharpe", "Sharpe (S0-S3 v1 def, S4+ excess)"),
           ("sharpe_excess", "excess Sharpe"), ("sortino", "Sortino (S0-S3 v1 def, S4+ standard)"),
           ("max_dd", "fraction"), ("turnover_pa", "× per year"), ("avg_gross", "gross exposure")]
STEP_NAMES = {"S0": "v1 as committed", "S1": "t+1", "S2": "+cash+financing", "S3": "+true-turnover costs",
              "S4": "excess metrics", "S5": "no shorts", "S6": "VIX to realised vol", "S7": "L1 (permitted data)"}


def tables(tab: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sm, loss = [], []
    for r in tab.itertuples(index=False):
        for m, unit in METRICS:
            sm.append((r.step, f"{m} ({r.window})", float(getattr(r, m)), unit, TIER[r.window], r.start, r.end))
        if r.window == "test":
            for part, v in (("gross", r.gross_pa), ("cost", -r.cost_pa), ("financing", -r.financing_pa),
                            ("net", r.net_pa)):
                loss.append((r.step, part, float(v), "mean return per year", TIER[r.window], r.start, r.end))
    summary = pd.DataFrame(sm, columns=["strategy", "metric", "value", "unit", "tier", "window_start", "window_end"])
    summary["lo"], summary["hi"] = np.nan, np.nan
    loss = pd.DataFrame(loss, columns=["strategy", "part", "value", "unit", "tier", "window_start", "window_end"])
    w = paths.rules()["legacy"]["windows"]
    windows = pd.DataFrame([(k, str(a), str(z), TIER[k], False, False,
                             "v1 chose its parameters here" if k != "test" else "seen by owner in v1, disclosed")
                            for k, (a, z) in w.items()],
                           columns=["name", "start", "end", "tier", "sealed", "opened", "note"])
    return {"summary": summary, "loss": loss, "windows": windows}


def manifest(tab: pd.DataFrame, qa: pd.DataFrame, sources: list[dict]) -> dict:
    head = git_head()
    t = tab[tab.window == "test"].set_index("step")
    q = qa[qa["sample"] == "2005-2025"].set_index("pair")
    verdicts = [
        {"id": "E1.1", "tier": "disclosed-reuse",
         "text": f"v1 reproduces exactly on its own data: test CAGR {t.loc['S0', 'cagr']:.1%}, Sharpe "
                 f"{t.loc['S0', 'sharpe']:.2f} (v1's definition)."},
        {"id": "D1.4", "tier": "disclosed-reuse",
         "text": f"After t+1 execution, cash and financing, true-turnover costs, excess Sharpe, no shorts, VIX → realised "
                 f"vol and permitted data, L1 (S7) earns test CAGR {t.loc['S7', 'cagr']:.1%} with excess Sharpe "
                 f"{t.loc['S7', 'sharpe']:.2f} (v1 as committed: {t.loc['S0', 'sharpe_excess']:.2f} on the excess "
                 f"definition)."},
        {"id": "E1.2", "tier": "in-sample",
         "text": "Pre-registered 't+1 ≤ 0' failed in train 2005–14 (t+1 raised Sharpe 0.54 → 0.64); held in "
                 "validation and test. One-day timing has no stable sign for this contrarian signal."},
        {"id": "E1.7", "tier": "in-sample",
         "text": f"Proxies pass QA 2005–2025 (monthly): Hi 20 vs SPY corr {q.loc['hi20_vs_spy', 'corr']:.3f}, TE "
                 f"{q.loc['hi20_vs_spy', 'te_pa']:.2%}; GSW 25y vs TLT corr {q.loc['gsw25_vs_tlt', 'corr']:.3f}, TE "
                 f"{q.loc['gsw25_vs_tlt', 'te_pa']:.2%}."},
    ]
    strategies = [{"id": k, "family": "legacy-v1", "variant": v, "frozen": True,
                   "cost_model": "v1 5 bp" if k in ("S0", "S1", "S2") else "3/2 bp per side, true turnover",
                   "gross_nav": False} for k, v in STEP_NAMES.items()]
    return {
        "schema_version": qr.SCHEMA_VERSION,
        "project": {"name": "regime-aware-spy-tlt-allocation", "repo": "regime-aware-spy-tlt-allocation",
                    "repo_commit": head, "quantkit_tag": "v0.19.1", "phase": "R1",
                    "thesis": "Regime-aware SPY/TLT/cash allocation; R1 swaps v1 onto permitted data and the charter's "
                              "accounting, one correction at a time.",
                    "data_cut": str(tab["end"].max()), "verdicts": verdicts},
        "strategies": strategies,
        "titles": {"loss_waterfall": "Test 2020–25 (seen in v1): mean return per year, gross → costs → financing → net"},
        "forward": {"rows_logged": 0, "last_row_date": None, "monitor_status": "not started", "refusals": 0,
                    "returns_hidden_until": None},
        "sources": sources,
    }


def git_head() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=paths.ROOT, capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def bundle() -> qr.Bundle:
    r1 = paths.REPORTS / "r1"
    tab, qa = pd.read_csv(r1 / "reconciliation.csv"), pd.read_csv(r1 / "qa.csv")
    sources = [{"path": str((r1 / f).relative_to(paths.ROOT)), "sha256": paths.sha256(r1 / f), "licence": LICENCE,
                "ledger_ref": "reports/ledger.md R1"} for f in ("reconciliation.csv", "qa.csv")]
    return qr.Bundle(manifest(tab, qa, sources), tables(tab))
