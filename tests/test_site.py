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
    for r in b.tables["summary"].itertuples(index=False):
        metric, window = r.metric.rsplit(" (", 1)
        want = tab[(tab.step == r.strategy) & (tab.window == window.rstrip(")"))].iloc[0][metric]
        assert r.value == want, (r.strategy, r.metric)
        assert r.tier == ("disclosed-reuse" if window.startswith("test") else "in-sample")
    for r in b.tables["loss"].itertuples(index=False):
        row = tab[(tab.step == r.strategy) & (tab.window == "test")].iloc[0]
        col = {"gross": "gross_pa", "cost": "cost_pa", "financing": "financing_pa", "net": "net_pa"}[r.part]
        assert abs(r.value) == abs(row[col])
