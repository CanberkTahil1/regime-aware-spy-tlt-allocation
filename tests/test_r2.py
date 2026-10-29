"""R2 rungs and evaluation (D2.2, D2.5–D2.8): decision rows, L4 σ vs quantkit's sample covariance (E2.7), ERC = inverse
vol for two assets (E2.7), the record book = quantkit tranche offset 0 (E2.8), the ex-ante line uses rows < t (E2.9),
the vol-zoo pick uses losses realised ≤ the year-end only (E2.10), the vol layer's cap, the promotion legs, the
post-hoc parent chains (O2.3, E2.14)."""

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from quantkit.alloc.cov import sample_cov
from quantkit.alloc.risk import erc
from quantkit.ladder import PreregistrationError
from quantkit.trade import tranche as qtr

from rspy import evaluate as ev
from rspy import paths, rungs, volzoo


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


def _panel(seed=7, T=900):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("1999-01-01", periods=T)
    return pd.DataFrame({"hi20": rng.normal(4e-4, 0.011, T), "tlt25": rng.normal(2e-4, 0.009, T),
                         "bill": np.full(T, 1e-4), "mmy": np.full(T, 0.0365), "dt": np.full(T, 1 / 360)}, index=idx)


def test_l1_l2_books_equal_legacy_bridge_run_accounting(no_yahoo):
    """Review R2 MATERIAL 2: rspy's L1/L2 decision → trade mapping is the R1 bridge's, end to end (a one-day shift in
    `v1_target` changes the book)."""
    from rspy import legacy_bridge as lb

    panel = _panel()
    inp = rungs.Inputs.from_panel(panel, panel.index[10], panel.index[-1])
    R = pd.DataFrame(inp.R, index=inp.index, columns=["SPY", "TLT"])
    bills = pd.DataFrame({"bill": inp.bill, "mmy": inp.mmy, "dt": inp.dt}, index=inp.index)
    kw = rungs.acc_kw()
    sig = pd.DataFrame({"SPY_pos": 1.0, "TLT_pos": 0.0}, index=inp.index)
    want = lb.run_accounting(lb.v1_scaled(sig, R), R, bills, rates=kw["cost_rates"], spread=kw["spread"],
                             allow_shorts=False, floor_zero=True)["net"].to_numpy()
    assert np.array_equal(rungs.book(rungs.l2_target(inp), inp).net, want)
    w = paths.rules()["legacy"]["vix_proxy"]["window"]
    start = inp.index[0] - pd.Timedelta(days=7)
    prices, rets, _ = lb.new_data_inputs(panel, panel.loc[:start].index[-1], inp.index[-1], w)
    sig1 = lb.v1_signals(prices, rets).reindex(inp.index).fillna(0.0)
    want1 = lb.run_accounting(lb.v1_scaled(sig1, R), R, bills, rates=kw["cost_rates"], spread=kw["spread"],
                              allow_shorts=False, floor_zero=True)["net"].to_numpy()
    assert np.array_equal(rungs.book(rungs.l1_target(panel, inp), inp).net, want1)


def test_vol_target_uses_the_forecast_stamped_t():
    """Review R2 MATERIAL 2: row t of the vol layer uses the forecast stamped t (not t+1): a strictly increasing
    forecast makes any misalignment visible."""
    inp = _inp(8)
    parent = np.full(inp.R.shape, np.nan)
    parent[0] = (0.5, 0.5)
    f = pd.Series(np.linspace(1e-5, 4e-4, len(inp.index)), inp.index)
    T = rungs.vol_target(parent, f, inp.index, 0.10, 10.0)
    want = 0.5 * 0.10 / np.sqrt(252 * f.to_numpy())
    assert np.allclose(T[:, 0], want, rtol=0, atol=1e-15)
    T2 = rungs.vol_target(parent, f.iloc[::2], inp.index, 0.10, 10.0)  # a stamp missing on day t → no decision at t
    assert np.isnan(T2[1]).all() and np.isfinite(T2[2]).all()


def test_chains_are_parent_only_and_cut_at_the_first_unbuilt_rung(monkeypatch):
    """O2.3 (post-hoc): L1 is a comparison row, never a parent; a chain stops at its first rung not built yet."""
    assert ev.chains({"L0", "L1", "L2", "L3", "L4", "L5"}) == {"vt_spy": ["L0", "L2"], "core": ["L0", "L3", "L4", "L5"]}
    assert ev.chains({"L0", "L2", "L4", "L5"})["core"] == ["L0"]  # L3 missing: L4 is never judged against L0
    pr = paths.prereg()
    bad = {**pr, "promotion_rule": {**pr["promotion_rule"], "walk_chains": {"x": ["L1", "L3"]}}}
    monkeypatch.setattr(paths, "prereg", lambda: bad)
    with pytest.raises(ValueError, match="comparison row"):
        ev.chains({"L1", "L3"})


def test_chain_walk_registers_beside_the_prereg_walk_and_never_uses_l1(tmp_path):
    """The chain ladders register next to r2_core without a rung-set clash; each step's incumbent is its parent."""
    pre, reg = tmp_path / "prereg.jsonl", tmp_path / "register.csv"
    ev.ladder("r2_core", paths.prereg()["promotion_rule"]["walk"]).preregister(pre)
    rng = np.random.default_rng(11)
    D = pd.bdate_range("1990-01-02", "2019-12-31")
    T = len(D)
    c, rate, dt = np.full(T, 1e-4), np.full(T, 0.0365), np.full(T, 1 / 360)
    books = {r: {k: rng.normal(3e-4 + 1e-5 * i, 0.01, T) for k in ("1x", "2x", "f75")}
             for i, r in enumerate(["L0", "L2", "L3", "L4", "L5"])}
    for k, ch in ev.chains(set(books)).items():
        ev.ladder(f"r2_chain_{k}", ch).preregister(pre)
        res = ev.walk({r: books[r] for r in ch}, c, rate, dt, D, prereg_path=pre, register_path=reg,
                      name=f"r2_chain_{k}")
        assert res["steps"] and res["winner"] in ch
        for s in res["steps"]:
            assert s["incumbent"] == ch[ch.index(s["rung"]) - 1] and "L1" not in (s["rung"], s["incumbent"])
    with pytest.raises(PreregistrationError):  # the same rung set under another name: order chosen after the fact
        ev.ladder("renamed", ["L0", "L2"]).preregister(pre)


def test_crisis_matched_parent_is_the_legs_rescale():
    """O2.4 descriptive row: the matched parent is `evaluate.rescale` to the child's excess vol, exactly."""
    rng = np.random.default_rng(3)
    T = 1500
    c, rate, dt = np.full(T, 1e-4), np.full(T, 0.0365), np.full(T, 1 / 360)
    x, y = rng.normal(3e-4, 0.006, T), rng.normal(3e-4, 0.012, T)
    pos = {"a": np.arange(100, 180), "b": np.arange(900, 960)}
    out = ev.crisis_matched(x, y, c, rate, dt, pos)
    ym = ev.rescale(y, c, float(np.std(x - c, ddof=1)) * np.sqrt(252), rate, dt, spread_bp=25.0)
    for r, p in zip(out, pos.values(), strict=True):
        assert r["parent_matched_return"] == float(np.prod(1 + ym[p]) - 1)
        assert r["child_return"] == float(np.prod(1 + x[p]) - 1) and r["loses_matched"] == (r["diff_matched"] < 0)


def test_committed_chain_walk_judges_every_step_against_its_parent():
    """Review (R2 amendment, MINOR): the script's wiring, on the committed result — every step's incumbent is its chain
    predecessor, no step involves L1, and the chain is the prereg chain cut at the first unbuilt rung."""
    import json

    j = json.loads((paths.REPORTS / "r2" / "ladder_chains.json").read_text())["chains"]
    assert {k: v["chain"] for k, v in j.items()} == ev.chains({"L0", "L2", "L3", "L4", "L5"})
    for v in j.values():
        ch = v["chain"]
        for s in v["steps"]:
            assert s["incumbent"] == ch[ch.index(s["rung"]) - 1] and "L1" not in (s["rung"], s["incumbent"])
