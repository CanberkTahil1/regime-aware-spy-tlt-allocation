"""The R1 page computes nothing (charter "Charts only draw numbers already in the ledger/reports"): every summary and
loss value in the bundle equals a field of the committed reports/r1/reconciliation.csv; no daily series is in it; the
bundle validates (tiers on every row; train/validation in-sample, test disclosed-reuse)."""

import pandas as pd
from quantkit import results as qr

from rspy import paths, site


def test_every_bundle_number_traces_to_the_committed_csv():
    tab = pd.read_csv(paths.REPORTS / "r1" / "reconciliation.csv")
    b = qr.validate(site.bundle())
    assert "series" not in b.tables and "rolling" not in b.tables  # returns never leave the machine (D1.4)
    m = pd.read_csv(paths.REPORTS / "r2" / "metrics.csv")
    m1 = m[m.book == "1x"].set_index("rung")
    ln = pd.read_csv(paths.REPORTS / "r2" / "lines.csv").set_index("rung")
    v1 = pd.read_csv(paths.REPORTS / "r2" / "vs_l1.csv").set_index("rung")
    r2 = set(site.R2_NAMES)
    for r in b.tables["summary"].itertuples(index=False):
        metric, window = r.metric.rsplit(" (", 1)
        if r.strategy in r2:  # R2: development window, in-sample, copied from reports/r2/*.csv
            want = (ln.loc[r.strategy, metric] if metric == "dsharpe_vs_line"
                    else v1.loc[r.strategy, metric] if metric == "dsharpe_vs_L1" else m1.loc[r.strategy, metric])
            assert r.value == want and r.tier == "in-sample", (r.strategy, r.metric)
            continue
        want = tab[(tab.step == r.strategy) & (tab.window == window.rstrip(")"))].iloc[0][metric]
        assert r.value == want, (r.strategy, r.metric)
        assert r.tier == ("disclosed-reuse" if window.startswith("test") else "in-sample")
    for r in b.tables["loss"].itertuples(index=False):
        if r.strategy in r2:
            v = m1.loc[r.strategy]
            want = {"gross": v.net_pa + v.cost_pa + v.financing_pa, "cost": v.cost_pa, "financing": v.financing_pa,
                    "net": v.net_pa}[r.part]
            assert abs(abs(r.value) - abs(want)) <= 1e-15 and r.tier == "in-sample"
            continue
        row = tab[(tab.step == r.strategy) & (tab.window == "test")].iloc[0]
        col = {"gross": "gross_pa", "cost": "cost_pa", "financing": "financing_pa", "net": "net_pa"}[r.part]
        assert abs(r.value) == abs(row[col])
