"""make r6 (spec/prereg_r6.yaml; owner O6.1/O6.2, advisor D6.1–D6.5): the R6 candidates and R5's reference rungs on
development 1990-01-02 → 2019-12-31 ("in-sample") and test 2020-01-02 → 2026-09-30 ("disclosed reuse: ideas inspired by
this window"). Reads the R5-locked panel and the BLS CPI files; never writes reports/r5 or anything R5 locked.

Committed (statistics only): reports/r6/{metrics, compare, verdict, crisis, costs, dsr, placebo}.csv, facts.json, run.json
(hashes only; timing goes to logs/r6_timing.json).
Local only (gitignored, KF-derived daily series): data/r6/books.parquet. Refuses if the CPI files fail their manifest,
if prereg_r6's sha256 differs from the one in reports/ledger.md, or if an identity check misses its tolerance.
"""

import argparse
import json
import os
import time

import pandas as pd

from r6lib import SPEC, books, cpi, data_dir, report, spec
from rspy import paths
from rspy.data import build as dbuild

TABLES = ("metrics", "compare", "verdict", "crisis", "costs", "dsr", "placebo")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=int(os.environ.get("RSPY_R6_WORKERS", "2")))  # threads: 4 → 1.45 GB, 2 → 1.03 GB; processes 2.9 GB (perf.md)
    ap.add_argument("--out", default=str(paths.REPORTS / "r6"))
    a = ap.parse_args()
    t = {}
    t0 = time.perf_counter()
    h = paths.sha256(SPEC)
    if h not in (paths.REPORTS / "ledger.md").read_text():
        raise SystemExit(f"prereg_r6 sha256 {h[:12]} is not recorded in reports/ledger.md (register before computing)")
    probs = cpi.verify()
    if probs:
        raise SystemExit("CPI raw files:\n  " + "\n  ".join(probs))
    panel = dbuild.load()
    st = cpi.state(cpi.read())
    B = books.build(panel, st)
    t["build"] = time.perf_counter() - t0
    if B["infl_carried_scored"] != spec()["checks"]["carry_count"]:
        raise SystemExit(f"inflation gate: {B['infl_carried_scored']} carried scored decisions (registered 0)")
    t1 = time.perf_counter()
    E = report.evaluate(B, workers=a.workers)
    t["evaluate"] = time.perf_counter() - t1
    ident = report.identity(E, B, paths.REPORTS, paths.data_dir())
    bad = {k: v for k, v in ident.items() if not v[0] <= v[1]}
    if bad:
        raise SystemExit(f"identity checks failed: {bad}")

    idx = B["inp"].index
    W = report.windows(idx)
    rows, dev, ts = B["rows"], W["development"], W["test"]
    ki = B["keep"]["infl"]
    hi = ki[:, 1] == 0
    dec22 = [str(d.date()) for d in idx[rows] if d.year == 2022 and d.month <= 6]
    v = E["verdict"]
    f = books_facts(B, W)
    facts = {
        "windows": {w: {"first": str(idx[m][0].date()), "last": str(idx[m][-1].date()), "sessions": int(m.sum()),
                        "label": report.label(w)} for w, m in W.items()},
        "identity": {k: {"value": v, "tolerance": t} for k, (v, t) in ident.items()},
        "infl_gate": {
            "carried_scored_decisions": B["infl_carried_scored"],
            "share_dev_decisions_high": float(hi[rows & dev].mean()),
            "share_test_decisions_high": float(hi[rows & ts].mean()),
            "high_at_2022_01_06_decisions": {d: bool(hi[idx.get_loc(pd.Timestamp(d))]) for d in dec22},
            "first_test_decision_high": next((str(d.date()) for d in idx[rows & ts & hi]), None),
            "cpi_missing_months": [str(m) for m in st.index[st.cpi.isna()]]},
        **f,
        "verdict_counts": v.verdict.value_counts().to_dict(),
        "verdict_counts_flagged": (v.verdict + " [" + v["flags"].str.replace(r"; test power.*", "", regex=True) + "]")
        .value_counts().to_dict(),
        "test_words_clearly": int(v.test_clearly.sum()), "development_words_clearly": int(v.development_clearly.sum()),
        "test_power_range": [float(v.power_at_test_length.min()), float(v.power_at_test_length.max())],
        "prereg_r6_sha256": h, "panel_sha256": paths.sha256(paths.data_dir() / "panel.parquet"),
        "gold": "R6g not run (owner O6.2): no monthly-frequency engine",
        "workers": a.workers,
    }
    t["total"] = time.perf_counter() - t0
    out = paths.ROOT / a.out if not os.path.isabs(a.out) else __import__("pathlib").Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for k in TABLES:
        E[k].to_csv(out / f"{k}.csv", index=False, float_format="%.10g")
    (out / "facts.json").write_text(json.dumps(facts, indent=1, sort_keys=True, default=float) + "\n")
    outputs = {f"{k}.csv": paths.sha256(out / f"{k}.csv") for k in TABLES} | {"facts.json": paths.sha256(out / "facts.json")}
    (out / "run.json").write_text(json.dumps({"prereg_r6_sha256": h, "outputs_sha256": outputs,
                                              "cpi_manifest_sha256": paths.sha256(cpi.raw_dir() / "manifest.jsonl")},
                                             indent=1, sort_keys=True) + "\n")
    paths.LOGS.mkdir(exist_ok=True)   # timing is not committed (it changes every run; `make all` must leave the tree clean)
    (paths.LOGS / "r6_timing.json").write_text(json.dumps({k: round(x, 1) for k, x in t.items()}) + "\n")
    loc = {"bill": B["inp"].bill, "spy_proxy": B["inp"].R[:, 0], "infl_keep_tlt": books.rungs.carry(ki)[:, 1],
           "trend_spy": books.rungs.carry(B["keep"]["trend"])[:, 0], "trend_tlt": books.rungs.carry(B["keep"]["trend"])[:, 1]}
    for name, bk in B["books"].items():
        b = bk["1x"]
        loc[f"{name}_net"] = b.net
        loc[f"{name}_w_spy"], loc[f"{name}_w_tlt"] = b.held[:, 0], b.held[:, 1]
    for name, ln in E["line_local"].items():
        loc[f"{name}_line"] = ln
    data_dir().mkdir(parents=True, exist_ok=True)
    pd.DataFrame(loc, index=idx).to_parquet(data_dir() / "books.parquet")
    st.assign(month=st.index.astype(str)).to_parquet(data_dir() / "cpi_state.parquet", index=False)
    print(v[["candidate", "development_word", "development_dsharpe", "test_word", "test_dsharpe", "verdict"]]
          .to_string(index=False, float_format=lambda x: f"{x:+.3f}"))
    print(f"identity: {len(ident)} checks within tolerance; carried {B['infl_carried_scored']}; timing {facts and t}")


def books_facts(B: dict, W: dict) -> dict:
    out = {}
    fund = B["books"]["R6f_blend"]["1x"]
    for w, m in W.items():
        out[f"R6f_gross_{w}"] = {"mean": float(fund.gross_exposure[m].mean()), "max": float(fund.gross_exposure[m].max()),
                                 "reset_turnover_pa": float(fund.reset_turnover[m].mean() * 252)}
        out[f"trend_share_{w}_days"] = {
            "spy_out": float((books.rungs.carry(B["keep"]["trend"])[m, 0] == 0).mean()),
            "tlt_out": float((books.rungs.carry(B["keep"]["trend"])[m, 1] == 0).mean())}
        out[f"infl_share_{w}_days_tlt_out"] = float((books.rungs.carry(B["keep"]["infl"])[m, 1] == 0).mean())
    return out


if __name__ == "__main__":
    main()
