"""rspy.accounting (D1.3) and the bill conventions (D1.1): fast path = plain reference ≤ 1e-10 (E1.8); t+1 timing
property (hypothesis); no shorts; financing only above gross 1 (E1.3); y·91/360 = 91-day bill return and no look-ahead
in the H.15 carry-forward (E1.9)."""

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rspy import accounting
from rspy.data.build import bill_returns
from tests.reference.accounting_ref import run_ref

RATES = np.array([3e-4, 2e-4])


def _inputs(seed, T=300, gross_hi=1.6, decide_every=1):
    rng = np.random.default_rng(seed)
    R = rng.normal(3e-4, 0.01, (T, 2))
    bill = np.full(T, 1e-4) + rng.uniform(0, 5e-5, T)
    mmy = bill * 360 + 0.001
    dt = rng.choice([1, 1, 1, 3], T) / 360.0
    target = rng.uniform(0, gross_hi / 2, (T, 2))
    mask = np.arange(T) % decide_every != 0
    target[mask] = np.nan
    return target, R, bill, mmy, dt


@pytest.mark.parametrize("seed,every", [(0, 1), (1, 21), (2, 5)])
def test_fast_equals_reference(seed, every):
    target, R, bill, mmy, dt = _inputs(seed, decide_every=every)
    kw = dict(cost_rates=RATES, spread=0.0025, stress_spread=0.0075, cost_mult=2.0)
    b = accounting.run(target, R, bill, mmy, dt, **kw)
    ref = run_ref(target, R, bill, mmy, dt, **kw)
    assert np.abs(b.held - ref["held"]).max() <= 1e-10
    for k in ("gross", "cash", "financing", "cost", "net", "turnover"):
        assert np.abs(getattr(b, k) - ref[k]).max() <= 1e-10, k


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 10_000), t=st.integers(5, 200))
def test_t_plus_one_timing(seed, t):
    """A target decided at close t trades at close t+1: returns of rows ≥ t+2 cannot change anything up to row t+1,
    and the target first earns in row t+2."""
    target, R, bill, mmy, dt = _inputs(seed)
    a = accounting.run(target, R, bill, mmy, dt, cost_rates=RATES, spread=0.0025)
    R2 = R.copy()
    R2[t + 2:] += 0.05
    b = accounting.run(target, R2, bill, mmy, dt, cost_rates=RATES, spread=0.0025)
    assert np.array_equal(a.net[: t + 2], b.net[: t + 2])
    assert np.array_equal(a.held[: t + 3], b.held[: t + 3])  # held into row t+2 = decision of close t
    np.testing.assert_array_equal(a.held[t + 2], target[t])


def test_shift_by_one_day_changes_the_book():
    """Planting the same target one row earlier (a look-ahead) must change the result: the timing test can fail."""
    target, R, bill, mmy, dt = _inputs(3)
    a = accounting.run(target, R, bill, mmy, dt, cost_rates=RATES, spread=0.0025)
    early = np.vstack([target[1:], target[-1:]])
    b = accounting.run(early, R, bill, mmy, dt, cost_rates=RATES, spread=0.0025)
    assert not np.allclose(a.net, b.net)


def test_no_shorts():
    target, R, bill, mmy, dt = _inputs(4)
    target[10, 0] = -0.1
    with pytest.raises(ValueError, match="shorts"):
        accounting.run(target, R, bill, mmy, dt, cost_rates=RATES, spread=0.0025)
    accounting.run(target, R, bill, mmy, dt, cost_rates=RATES, spread=0.0025, allow_shorts=True)


def test_financing_only_above_gross_one_and_cash_only_below():
    """E1.3 by construction: financing ≥ 0, > 0 exactly on rows held above gross 1; cash interest ≥ 0, 0 above 1."""
    target, R, bill, mmy, dt = _inputs(5, gross_hi=2.0)
    b = accounting.run(target, R, bill, mmy, dt, cost_rates=RATES, spread=0.0025)
    inv = b.held.sum(axis=1)
    assert (b.financing >= 0).all() and (b.cash >= 0).all()
    assert (b.financing[inv > 1 + 1e-12] > 0).all() and (b.financing[inv <= 1] == 0).all()
    assert (b.cash[inv >= 1] == 0).all()


def test_unlevered_book_at_cash_earns_the_bill():
    T = 50
    R, bill = np.zeros((T, 2)), np.full(T, 2e-4)
    b = accounting.run(np.full((T, 2), 0.0), R, bill, bill * 360, np.ones(T) / 360, cost_rates=RATES, spread=0.0025)
    np.testing.assert_allclose(b.net, bill, rtol=0, atol=1e-18)


def test_sortino_standard_downside():
    e = np.array([0.01, -0.02, 0.005, -0.01])
    want = np.sqrt(252) * e.mean() / np.sqrt(np.mean(np.minimum(e, 0) ** 2))
    assert accounting.sortino(e) == pytest.approx(want, abs=1e-15)


# ---- D1.1 bills -----------------------------------------------------------------------------------------------------
def test_mmy_times_91_over_360_equals_91_day_bill_return():
    sessions = pd.DatetimeIndex(["2000-01-03", "2000-04-03"])  # 91 calendar days
    disc = pd.DataFrame({"date": pd.to_datetime(["2000-01-03"]), "disc": [0.05]})
    b = bill_returns(disc, sessions)
    assert b["mmy"].iloc[0] * 91 / 360 == pytest.approx(b["ret"].iloc[0], abs=1e-15)
    assert b["mmy"].iloc[0] > 0.05  # y > d: financing never cheaper than the discount quote


def test_bill_rate_carries_forward_and_never_looks_ahead():
    sessions = pd.DatetimeIndex(["2000-01-03", "2000-01-04", "2000-01-05", "2000-01-06"])
    disc = pd.DataFrame({"date": pd.to_datetime(["2000-01-03", "2000-01-05"]), "disc": [0.04, 0.09]})
    b = bill_returns(disc, sessions).set_index("date")
    # row 01-04 and 01-05 use the 01-03 rate (no print on 01-04; 01-05's print is not yet known for row 01-05)
    assert b.loc["2000-01-04", "disc_used"] == 0.04 and b.loc["2000-01-05", "disc_used"] == 0.04
    assert b.loc["2000-01-06", "disc_used"] == 0.09
