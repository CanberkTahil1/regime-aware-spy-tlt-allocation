"""R2 rungs and evaluation (D2.2, D2.5–D2.8): decision rows, L4 σ vs quantkit's sample covariance (E2.7), ERC = inverse
vol for two assets (E2.7), the record book = quantkit tranche offset 0 (E2.8), the ex-ante line uses rows < t (E2.9),
the vol-zoo pick uses losses realised ≤ the year-end only (E2.10), the vol layer's cap, the promotion legs."""

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st
from quantkit.alloc.cov import sample_cov
from quantkit.alloc.risk import erc
from quantkit.trade import tranche as qtr

from rspy import evaluate as ev
from rspy import rungs, volzoo


def _inp(seed=0, T=700):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2001-01-01", periods=T)
    R = np.column_stack([rng.normal(4e-4, 0.011, T), rng.normal(2e-4, 0.009, T)])
    bill = np.full(T, 1e-4)
    return rungs.Inputs(idx, R, bill, bill * 360, np.full(T, 1 / 360))


def test_decision_rows_are_the_last_session_of_each_month():
    inp = _inp()
    rows = rungs.decision_rows(inp.index, 0)
    d = inp.index[rows]
    nxt = inp.index[np.flatnonzero(rows) + 1]
    assert (d.month != nxt.month).all()  # decided on the last session, traded on the first of the next month
    assert rows.sum() == len(np.unique(inp.index.to_period("M"))) - 1


def test_sigma63_matches_quantkit_sample_cov():
    inp = _inp(1)
    s = rungs.sigma63(inp)
    for t in (62, 63, 300, 699):
        ref = np.sqrt(np.diag(sample_cov(inp.R[t - 62:t + 1], ddof=1)))
        assert np.abs(s[t] - ref).max() <= 1e-10
    assert np.isnan(s[61]).all()  # all 63 returns required


@settings(max_examples=60, deadline=None)
@given(s1=st.floats(0.01, 0.5), s2=st.floats(0.01, 0.5), rho=st.floats(-0.99, 0.99))
def test_erc_equals_inverse_vol_for_two_assets(s1, s2, rho):
    C = np.array([[s1 * s1, rho * s1 * s2], [rho * s1 * s2, s2 * s2]])
    iv = np.array([1 / s1, 1 / s2])
    assert np.abs(erc(C) - iv / iv.sum()).max() <= 1e-8


def test_l4b_equals_l4_on_month_ends():
    inp = _inp(2)
    rows = rungs.decision_rows(inp.index, 0)
    a, b = rungs.l4_target(inp, rows), rungs.l4b_target(inp, rows)
    ok = np.isfinite(a[:, 0])
    assert ok.sum() > 20 and np.array_equal(ok, np.isfinite(b[:, 0]))
    assert np.abs(a[ok] - b[ok]).max() <= 1e-10


def test_record_book_is_tranche_offset_zero():
    inp = _inp(3)

    def rule(mask):
        tr = np.flatnonzero(mask)
        dec = np.zeros(len(inp.index), bool)
        dec[tr[tr >= 1] - 1] = True
        bk = rungs.book(rungs.l4_target(inp, dec), inp, band=0.05)
        return np.vstack([bk.held[1:], bk.held[-1:]])

    rec = rungs.book(rungs.l4_target(inp, rungs.decision_rows(inp.index, 0)), inp, band=0.05)
    tr = qtr.tranche(rule, inp.index, list(range(21)))
    assert np.array_equal(tr["books"][0], np.vstack([rec.held[1:], rec.held[-1:]]))
    assert len(tr["books"]) == 21


def test_vol_layer_cap_and_scale():
    w = np.tile([0.5, 0.5], (4, 1))
    f = np.array([(0.05 / np.sqrt(252)) ** 2, (0.20 / np.sqrt(252)) ** 2, np.nan, (0.10 / np.sqrt(252)) ** 2])
    T = rungs.vol_scaled(w, f, 0.10, 1.0)
    assert np.allclose(T[0], (0.5, 0.5))  # 0.10 / 0.05 = 2, capped at 1
    assert np.allclose(T[1], (0.25, 0.25))
    assert np.isnan(T[2]).all() and np.allclose(T[3], (0.5, 0.5))


def test_ex_ante_line_never_uses_row_t_or_later():
    inp = _inp(4)
    x = inp.R[:, 0] * 0.6 + inp.R[:, 1] * 0.3
    a = ev.line(x, inp.R[:, 0], inp.bill, inp.mmy, inp.dt)["weight"]
    for t in (100, 400):
        y = x.copy()
        y[t:] *= 5.0  # a planted future
        b = ev.line(y, inp.R[:, 0], inp.bill, inp.mmy, inp.dt)["weight"]
        assert np.array_equal(a[: t + 1], b[: t + 1], equal_nan=True)
        assert not np.array_equal(a, b, equal_nan=True)


def test_zoo_pick_ignores_losses_after_the_year_end():
    idx = pd.bdate_range("2000-01-03", "2003-12-31")
    rng = np.random.default_rng(5)
    r = pd.Series(rng.normal(0, 0.01, len(idx)), idx)
    F = pd.DataFrame({m: (r**2).ewm(halflife=h).mean() for m, h in
                      zip(volzoo.spec()["selection_order"], (60, 10, 30, 20, 5), strict=True)})
    a = volzoo.select(F, r, [2001])
    r2 = r.copy()
    r2.loc["2002-01-02":] *= 10  # planted: everything realised after 2001-12-31
    F2 = F.copy()
    F2.loc["2002-01-01":] *= 0.01
    b = volzoo.select(F2, r2, [2001])
    assert a == b


def test_promotion_legs_no_loss_rule():
    rng = np.random.default_rng(6)
    T = 2000
    c, rate, dt = np.full(T, 1e-4), np.full(T, 0.0365), np.full(T, 1 / 360)
    y = rng.normal(3e-4, 0.01, T)
    pos = {"a": np.arange(100, 200), "b": np.arange(900, 950)}
    same = ev.legs({"1x": y, "2x": y, "f75": y}, {"1x": y, "2x": y, "f75": y}, c, rate, dt, pos)
    assert abs(same["dsharpe_matched"]) <= 1e-12 and all(same["legs"]["sharpe"].values())  # ties do not lose
    assert not same["route_cdar"]
