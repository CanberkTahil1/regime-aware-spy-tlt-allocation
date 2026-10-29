"""D1.2 / E1.10: the TLT proxy leg = quantkit.bonds.total_return(par_col=None, max_gap 7) masked to SVENY<M>-reported
dates equals naive-vs-optimal's validated `par_total_return` (tests/reference/bonds_par_ref.py) ≤ 1e-10, on a synthetic
GSW-shaped curve (no downloaded data needed); and the session mapping never credits a return early."""

import numpy as np
import pandas as pd

from rspy.data.build import bond_leg, to_sessions
from tests.reference import bonds_par_ref as ref


def _curve(seed=0, n=400, start="1985-10-01", reported_from="1985-11-25"):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, periods=n)
    days = days.delete([50, 51, 52, 53, 54])  # a one-week hole (≤ 7 calendar days kept, longer dropped)
    k = len(days)
    walk = lambda s, x0: x0 + np.cumsum(rng.normal(0, s, k))  # noqa: E731
    c = pd.DataFrame({"BETA0": walk(0.01, 6.0), "BETA1": walk(0.01, -2.0), "BETA2": walk(0.01, 1.0),
                      "BETA3": walk(0.01, 2.0), "TAU1": 1.5 + np.abs(walk(0.005, 0.0)),
                      "TAU2": 10 + np.abs(walk(0.01, 0.0))}, index=pd.DatetimeIndex(days, name="date"))
    c["SVENY25"] = np.where(c.index >= pd.Timestamp(reported_from), 7.0, np.nan)
    c.loc[c.index[200], "SVENY25"] = np.nan  # a one-day blank inside the reported range (2008-03-21 style)
    return c


def test_quantkit_leg_equals_validated_reference():
    c = _curve()
    got, info = bond_leg(c, 25, max_gap_days=7, m=2)
    want = ref.par_total_return(c, 25, m=2, max_gap_days=7, prefix="SVENY")
    both = got.dropna().index.intersection(want.dropna().index)
    assert len(both) > 300
    assert np.abs(got[both] - want[both]).max() <= 1e-10
    assert set(got.dropna().index) == set(want.dropna().index)  # same rows valid (mask + gap rule)


def test_mask_needs_both_curve_dates_reported():
    c = _curve()
    got, _ = bond_leg(c, 25, max_gap_days=7, m=2)
    first = c.index[c.index >= "1985-11-25"][0]
    assert got.loc[:first].isna().all()  # the first reported date cannot earn: its purchase day was unreported
    assert np.isfinite(got.loc[c.index[201]])  # a one-day blank inside the range is not a gap (cummax)


def test_to_sessions_never_credits_early_and_compounds():
    r = pd.Series([0.01, 0.02, 0.03], index=pd.to_datetime(["2000-01-03", "2000-01-04", "2000-01-08"]))
    sessions = pd.to_datetime(["2000-01-03", "2000-01-05", "2000-01-10"])
    s = to_sessions(r, pd.DatetimeIndex(sessions))
    assert s.iloc[0] == 0.01
    assert abs(s.iloc[1] - 0.02) < 1e-15  # 01-04 is credited to the first session ≥ it (01-05), never to 01-03
    assert abs(s.iloc[2] - 0.03) < 1e-15  # a Saturday curve date goes to Monday, never Friday
