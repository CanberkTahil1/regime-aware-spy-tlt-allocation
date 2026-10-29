"""R4 (D4.1–D4.7, E4.4): v1 overlay states equal plain loops and are decided from rows ≤ t; the GBM label/feature
design is causal and equals a loop; every walk-forward split passes quantkit's purge check and a leaky one raises;
GBM predictions are bit-identical with 1 vs 2 workers; the haircut blend; the waterfall identity and cost split; v1's
grid path reproduces L1 at v1's selected parameters; maturity legs and the quarterly calendar."""

import numpy as np
import pandas as pd
import pytest
from quantkit.cv import LeakageError, Split, check_split

from rspy import regime, robust, rungs
from tests.reference.r4_ref import bollinger_keep_ref, gbm_label_ref, spread_keep_ref
from tests.test_r2 import _inp


def _panel(seed=0, T=1600, start="1987-01-01"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=T)
    spy = rng.standard_t(4, T) * 0.008 + 4e-4
    tlt = rng.standard_t(4, T) * 0.007 + 2e-4
    bill = np.full(T, 1.2e-4)
    p = pd.DataFrame({"hi20": spy, "tlt25": tlt, "tlt10": tlt * 0.5, "tlt20": tlt * 0.8, "tlt30": tlt * 1.1,
                      "bill": bill, "mmy": bill * 360, "dt": np.full(T, 1 / 360)}, index=idx)
    return p


def _inp_of(p, start):
    return rungs.Inputs.from_panel(p, start, str(p.index[-1].date()))


@pytest.mark.parametrize("kind", ["spread", "bollinger"])
def test_overlay_keep_equals_the_plain_state_loop(kind):
    p = _panel(1)
    inp = _inp_of(p, "1987-03-02")
    k = robust.overlay_keep(p, inp, kind)
    c = robust.spec()["overlays"][kind]
    lvl = (1 + p[["hi20", "tlt25"]]).cumprod()  # base-free for the ratio test
    if kind == "spread":
        r = p[["hi20", "tlt25"]].copy()
        start = p.loc[:inp.index[0] - pd.Timedelta(days=7)].index[-1]
        r = r.loc[start:]
        r.iloc[0] = np.nan  # new_data_inputs: the base session has no return
        ref = spread_keep_ref(r["hi20"].to_numpy(), r["tlt25"].to_numpy(), c["window"], c["threshold"])
        ref = pd.DataFrame(ref, index=r.index).reindex(inp.index).to_numpy()
    else:
        start = p.loc[:inp.index[0] - pd.Timedelta(days=7)].index[-1]
        lv = lvl.loc[start:]
        ref = bollinger_keep_ref(lv["hi20"].to_numpy(), lv["tlt25"].to_numpy(), c["window"], c["num_std"])
        ref = pd.DataFrame(ref, index=lv.index).reindex(inp.index).to_numpy()
    assert np.array_equal(k, ref)
    assert (k[:, 0] == 0).any() and (k[:, 1] == 0).any()  # both states occur on this sample
    assert not ((k[:, 0] == 0) & (k[:, 1] == 0)).any()     # never both sleeves on one day


@pytest.mark.parametrize("kind", ["spread", "bollinger"])
def test_overlay_targets_and_holdings_use_no_future_returns(kind):
    p = _panel(2)
    inp = _inp_of(p, "1987-03-02")
    l5 = np.tile([0.5, 0.45], (len(inp.index), 1))
    tg = regime.gate(l5, robust.overlay_keep(p, inp, kind))
    held = rungs.book(tg, inp, band=0.05).held
    for t in (200, 451, 900, 1300):
        p2 = p.copy()
        p2.loc[p2.index > inp.index[t], ["hi20", "tlt25"]] = 0.05
        inp2 = _inp_of(p2, "1987-03-02")
        tg2 = regime.gate(l5, robust.overlay_keep(p2, inp2, kind))
        assert np.array_equal(tg[:t + 1], tg2[:t + 1]), t
        assert np.array_equal(held[:t + 2], rungs.book(tg2, inp2, band=0.05).held[:t + 2]), t


def _core(seed=3, T=1600):
    """A synthetic Core on 1987-… (so the registered refit years 1989–1991 have test years); s5 = EWMA variance."""
    p = _panel(seed, T)
    inp = _inp_of(p, "1987-01-02")
    rows = rungs.decision_rows(inp.index, 0)
    dev = np.asarray(inp.index >= pd.Timestamp("1990-01-01"))
    L4 = rungs.l4_target(inp, rows)
    r4 = rungs.log_book_returns(rungs.book(L4, inp, band=0.05))
    s5 = (r4**2).ewm(halflife=60, adjust=False).mean()
    return robust.Core(p, inp, rows, dev, 0.05, {"L4": L4}, s5, r4, {})


def test_gbm_design_is_causal_and_the_label_equals_a_loop():
    core = _core()
    D = robust.gbm_design(core)
    r = core.r4.reindex(core.inp.index).to_numpy()
    assert np.allclose(D["y"].to_numpy(), gbm_label_ref(r), atol=1e-10, equal_nan=True)
    assert np.array_equal(D["label_end"], np.arange(len(r)) + 22)
    X = D["X"].to_numpy()
    for t in (400, 800):  # features at t do not move when returns after t change
        R2 = core.inp.R.copy()
        R2[t + 1:] = 0.03
        inp2 = rungs.Inputs(core.inp.index, R2, core.inp.bill, core.inp.mmy, core.inp.dt)
        r4b = rungs.log_book_returns(rungs.book(core.T["L4"], inp2, band=0.05))
        c2 = robust.Core(core.panel, inp2, core.rows, core.dev, 0.05, core.T, core.s5, r4b, {})
        X2 = robust.gbm_design(c2)["X"].to_numpy()
        assert np.array_equal(X[:t + 1], X2[:t + 1], equal_nan=True), t


def test_gbm_splits_pass_the_purge_check_and_a_leaky_split_raises():
    core = _core()
    D = robust.gbm_design(core)
    ok = np.isfinite(D["X"].to_numpy()).all(axis=1) & np.isfinite(D["y"].to_numpy())
    pos = np.flatnonzero(ok)
    cv, le = robust.gbm_splits(core.inp.index, pos, D["label_end"], range(1989, 1992))
    assert len(cv) >= 2
    for sp in cv:
        check_split(sp, 22, 0, le)
        a = sp.bounds[sp.test_groups[0]][0]
        assert le[sp.train].max() < a  # no training label reaches the test year
    sp = cv[0]
    a = sp.bounds[sp.test_groups[0]][0]
    leaky = sp.train.copy()
    leaky[a - 5] = True  # a row whose label window crosses into the test year
    with pytest.raises(LeakageError):
        check_split(Split(leaky, sp.test, sp.test_groups, sp.bounds, 22, 0, le), 22, 0, le)


def test_gbm_predictions_bit_identical_with_1_and_2_workers():
    pytest.importorskip("lightgbm")
    core = _core()
    a = robust.gbm_predict(core, n_jobs=1)
    b = robust.gbm_predict(core, n_jobs=2)
    assert np.array_equal(a["log_sigma_gbm"], b["log_sigma_gbm"], equal_nan=True)
    pr = a["log_sigma_gbm"]
    assert np.isfinite(pr[core.inp.index.year == 1990]).all()
    assert np.isnan(pr[core.inp.index.year <= 1989]).all()  # warm-up rows are never predicted


def test_gbm_haircut_blend():
    core = _core()
    lz = 0.5 * np.log(252 * core.s5.reindex(core.inp.index).to_numpy())
    lg = lz + 0.4
    lg[:500] = np.nan
    s0, s5_, s1 = (robust.gbm_sigma(core, lg, h) for h in (0.0, 0.5, 1.0))
    f = np.isfinite(lz)
    assert np.allclose(np.log(s0[f][500:]), lg[f][500:]) and np.allclose(np.log(s1[f]), lz[f])
    assert np.allclose(np.log(s5_[f][500:]), lz[f][500:] + 0.2)
    assert np.allclose(s5_[:500][f[:500]], np.exp(lz[:500][f[:500]]))  # no prediction ⇒ σ_zoo


def test_waterfall_identity_and_cost_split():
    inp = _inp(7, T=600)
    rows = rungs.decision_rows(inp.index, 0)
    tg = rungs.vol_target(rungs.l4_target(inp, rows), pd.Series(np.full(600, 1e-5), index=inp.index), inp.index,
                          0.10, 1.5)
    bk = rungs.book(tg, inp, band=0.05, cost_mult=2.0, stress_bp=75)
    kw = rungs.acc_kw()
    from rspy import accounting

    bs = accounting.run(tg, inp.R, inp.bill, inp.mmy, inp.dt, cost_rates=kw["cost_rates"] * np.array([1.0, 0.0]),
                        spread=kw["spread"], stress_spread=75e-4, cost_mult=2.0, band=0.05, index=inp.index)
    w = robust.waterfall(bk, bs, inp.bill)
    assert w["max_resid"] <= 1e-10
    assert w["gross_pa"] + w["cash_pa"] - w["cost_spy_pa"] - w["cost_tlt_pa"] - w["financing_pa"] == pytest.approx(
        w["net_pa"], abs=1e-12)
    assert w["cost_spy_pa"] > 0 and w["cost_tlt_pa"] > 0 and w["financing_pa"] > 0


def test_v1_grid_path_reproduces_l1_at_v1_params():
    p = _panel(4, T=900)
    inp = _inp_of(p, "1987-02-02")
    lb = rungs._legacy()
    assert np.array_equal(robust.v1_target_for(p, inp, lb.v1_params()), rungs.l1_target(p, inp), equal_nan=True)
    g = robust.v1_grid()
    assert len(g) == 648 and (g[0].index == ["z", "th", "sw", "sth", "ddw", "ddt", "cw"]).all()
    sel = lb.v1_params()
    assert sum(all(np.isclose(x[k], sel[k]) for k in sel.index) for x in g) == 1  # v1's pick is one grid point


def test_maturity_leg_replaces_tlt_and_refuses_a_gap():
    p = _panel(5, T=300, start="1986-01-02")
    q = robust.leg_panel(p, 10)
    assert np.array_equal(q["tlt25"].to_numpy(), p["tlt10"].to_numpy())
    assert robust.leg_panel(p, 25) is p
    p.iloc[40, p.columns.get_loc("tlt30")] = np.nan
    with pytest.raises(ValueError, match="tlt30"):
        robust.leg_panel(p, 30)


def test_quarterly_rows_are_the_quarter_end_month_end_rows():
    inp = _inp(8, T=800)
    m = robust.decision_rows(inp.index)
    q = robust.decision_rows(inp.index, quarterly=True)
    assert np.array_equal(m, rungs.decision_rows(inp.index, 0)) and not (q & ~m).any()
    assert (inp.index[q].month % 3 == 0).all() and np.array_equal(q, m & (inp.index.month % 3 == 0))


def test_v1_grid_net_bit_identical_with_1_and_2_workers(tmp_path):
    p = _panel(6, T=1100, start="1985-11-01")  # from before 1986 (v1 base session) into 1990 (scored rows exist)
    f = tmp_path / "panel.parquet"
    p.to_parquet(f)
    g = robust.v1_grid()[:4]
    a = robust.v1_grid_net(f, workers=1, grid=g)
    b = robust.v1_grid_net(f, workers=2, grid=g)  # loky children, chunks of 2
    assert a.shape == (int((p.index >= "1990-01-01").sum()), 4) and np.isfinite(a).all()
    assert np.array_equal(a, b)


def test_waterfall_vol_drag_is_nonnegative_for_a_low_vol_book():
    inp = _inp(9, T=800)
    tg = np.full(inp.R.shape, np.nan)
    tg[0] = (0.2, 0.2)  # a low-vol book: mean·252 − CAGR < 0 here, the compounded-mean drag is still ≥ 0
    bk = rungs.book(tg, inp)
    w = robust.waterfall(bk, bk, inp.bill)
    assert w["vol_drag_pa"] >= 0 and w["compounded_mean_pa"] >= w["cagr"]


def test_gbm_predictions_up_to_t_ignore_returns_after_t():
    pytest.importorskip("lightgbm")
    core = _core()
    a = robust.gbm_predict(core)["log_sigma_gbm"]
    for t in (int(np.flatnonzero(core.inp.index.year == 1990)[100]), int(np.flatnonzero(core.inp.index.year == 1991)[30])):
        R2 = core.inp.R.copy()
        R2[t + 1:] *= 4.0  # a vol shock after t
        inp2 = rungs.Inputs(core.inp.index, R2, core.inp.bill, core.inp.mmy, core.inp.dt)
        r4b = rungs.log_book_returns(rungs.book(core.T["L4"], inp2, band=0.05))
        s5b = (r4b**2).ewm(halflife=60, adjust=False).mean()
        c2 = robust.Core(core.panel, inp2, core.rows, core.dev, 0.05, core.T, s5b, r4b, {})
        b = robust.gbm_predict(c2)["log_sigma_gbm"]
        assert np.array_equal(a[:t + 1], b[:t + 1], equal_nan=True), t
        assert not np.array_equal(a[t + 1:], b[t + 1:], equal_nan=True)  # the shock is seen after t
