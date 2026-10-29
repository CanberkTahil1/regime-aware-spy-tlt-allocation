"""R3 regime layer (D3.1–D3.6, E3.13): the correlation gate is decided from rows ≤ t and equals a plain np.corrcoef loop;
gates reach the daily target only through decisions made ≤ t and send a sleeve to exactly 0; faber's read-back equals
the month-end SMA rule at every decision row; the placebo is a block permutation of the monthly decision vector shared
by both sleeves; the L8 multiplier path is judge's candidate; max-div = L4 for two assets; ablation matching."""

import numpy as np
import pandas as pd
import pytest
from quantkit.alloc.risk import max_div
from quantkit.sizing import judge
from quantkit.stats import sharpe

from rspy import evaluate as ev
from rspy import regime, rungs
from tests.reference.regime_ref import corr_ref
from tests.test_r2 import _inp


def _rows(inp):
    return rungs.decision_rows(inp.index, 0)


def test_corr_equals_reference_and_uses_rows_up_to_t():
    inp = _inp(3, T=400)
    c = regime.corr(inp, 63)
    assert np.nanmax(np.abs(c - corr_ref(inp.R, 63))) <= 1e-10
    assert np.isnan(c[61]) and np.isfinite(c[62:]).all()
    R2 = inp.R.copy()
    R2[201:] *= -3.0  # perturb the future
    inp2 = rungs.Inputs(inp.index, R2, inp.bill, inp.mmy, inp.dt)
    assert np.array_equal(regime.corr(inp2, 63)[:201], c[:201], equal_nan=True)


def test_l6_keep_decides_on_decision_rows_only():
    inp = _inp(4, T=500)
    rows = _rows(inp)
    k = regime.l6_keep(inp, rows, 126, 0.0)
    c = regime.corr(inp, 126)
    on = rows & np.isfinite(c)
    assert np.isnan(k[~rows]).all()
    assert (k[on, 0] == 1.0).all()
    assert np.array_equal(k[on, 1], (c[on] <= 0.0).astype(float))


def test_gate_applies_decisions_made_up_to_t_and_exits_to_exact_zero():
    inp = _inp(5, T=300)
    rows = _rows(inp)
    parent = np.full(inp.R.shape, np.nan)
    parent[30:] = (0.5, 0.45)  # a daily target (vol layer)
    keep = np.full(inp.R.shape, np.nan)
    d = np.flatnonzero(rows)
    keep[d[0]] = (1.0, 1.0)
    keep[d[2]] = (1.0, 0.0)
    out = regime.gate(parent, keep)
    assert (out[d[2] - 1, 1] == 0.45) and (out[d[2], 1] == 0.0) and (out[d[2]:d[3], 1] == 0.0).all()
    assert np.array_equal(out[30:, 0], parent[30:, 0])  # the other sleeve untouched
    bk = rungs.book(out, inp, band=0.05)
    assert (bk.held[d[2] + 2:d[3], 1] == 0.0).all()  # traded at d+1, flat from d+2: no 5 pp stub


def test_faber_read_back_equals_the_month_end_sma_rule():
    inp = _inp(6, T=900)
    rows = _rows(inp)
    k = regime.trend_keep(inp, rows, 10)
    lvl = np.cumprod(1 + inp.R, axis=0)
    per = inp.index.to_period("M")
    ends = np.flatnonzero(np.r_[per[1:] != per[:-1], True])
    for e in np.flatnonzero(rows):
        j = np.searchsorted(ends, e)
        assert ends[j] == e  # offset-0 decision rows are month-ends
        if j < 9:
            assert np.isnan(k[e]).all()
            continue
        sma = lvl[ends[j - 9:j + 1]].mean(axis=0)
        assert np.array_equal(k[e], (lvl[e] > sma).astype(float))


def test_trend_read_back_fallback_matches_faber_near_the_end():
    inp = _inp(7, T=600)
    rows = _rows(inp)
    a = regime.trend_keep(inp, rows, 10)
    b = regime.trend_keep(inp, rows, 10, fallback_only=True)  # the SMA path on every row
    on = np.isfinite(a[:, 0])
    assert np.array_equal(a[on], b[on])


def test_placebo_is_a_block_permutation_shared_by_both_sleeves():
    inp = _inp(8, T=1500)
    rows = _rows(inp)
    keep = regime.trend_keep(inp, rows, 10)
    scored = inp.index >= inp.index[300]
    pl = regime.shuffle_decisions(keep, rows, scored, block=12, seed=0)
    r = np.flatnonzero(rows & scored)
    assert np.array_equal(pl[~(rows & scored)], keep[~(rows & scored)], equal_nan=True)
    pairs = lambda x: sorted(map(tuple, np.nan_to_num(x[r], nan=-1)))  # noqa: E731
    assert pairs(pl) == pairs(keep)  # same rows of (SPY, TLT) decisions: joint distribution kept
    perm = regime.block_perm(len(r), 12, 0)
    assert np.array_equal(pl[r], keep[r][perm], equal_nan=True)
    assert not np.array_equal(pl[r], keep[r], equal_nan=True)


def test_crash_multiplier_is_judges_candidate():
    rng = np.random.default_rng(1)
    x = rng.normal(2e-4, 0.008, 2000)
    x[500:700] -= 0.004  # a deep drawdown so the brake fires
    ov = regime.crash_overlay(x)
    assert (ov.mult < 1).any() and (ov.mult >= 0.25).all()
    j = judge(x, 0.10, "dd", sigma=np.full(len(x), 0.10), cap=1.0, block=21, seed=0, draws=200, mean_block=21)
    assert abs(j["sharpe"]["candidate"] - float(sharpe(ov.returns[1:], ann=252))) <= 1e-12
    assert abs(j["sharpe"]["vol"] - float(sharpe(x[1:], ann=252))) <= 1e-12  # vol targeting alone = the parent


def test_max_div_equals_l4_on_the_sample_covariance():
    inp = _inp(9, T=400)
    rows = _rows(inp)
    W4 = rungs.l4_target(inp, rows)
    for t in np.flatnonzero(rows & np.isfinite(W4[:, 0])):
        w = max_div(inp.R[t - 62:t + 1], cov=np.cov(inp.R[t - 62:t + 1].T, ddof=1))
        assert np.abs(w - W4[t]).max() <= 1e-10


def test_ablation_row_matches_the_rescaled_reference():
    rng = np.random.default_rng(2)
    T = 1500
    c = np.full(T, 1e-4)
    x = c + rng.normal(3e-4, 0.006, T)
    y = c + rng.normal(3e-4, 0.010, T)
    rate, dt = np.full(T, 0.03), np.full(T, 1 / 360)
    row = ev.ablation_row(x, y, c, rate, dt, draws=200)
    ds, cs, cb = ev.pair(x, y, c, rate, dt)
    assert abs(row["dsharpe"] - ds) <= 1e-10
    assert row["lo"] < row["dsharpe"] < row["hi"]
    assert abs(row["cdar_ratio"] - cs / cb) <= 1e-10
    assert row["cdar_lo"] <= row["cdar_median"] <= row["cdar_hi"] and row["maxdd_lo"] <= row["maxdd_hi"]


def test_no_r3_walk_chains_stay_cut_at_l5():
    ch = ev.chains({"L0", "L2", "L3", "L4", "L5"})
    assert ch["core"][-1] == "L5"


@pytest.mark.parametrize("w", [63, 126])
def test_l6_gate_never_nan_on_scored_decision_rows(w):
    inp = _inp(10, T=1200)
    rows = _rows(inp)
    k = regime.l6_keep(inp, rows, w, 0.0)
    scored = rows & (inp.index >= inp.index[300])
    assert np.isfinite(k[scored]).all()
    assert isinstance(pd.Series(k[:, 1]).dropna().iloc[0], float)


def test_cache_returns_the_uncached_value(tmp_path):
    x = np.random.default_rng(3).normal(size=300)
    fn = lambda r: np.cumsum(r)  # noqa: E731
    a = regime.cached("t", fn, x, key={"k": 1}, cache=tmp_path)
    b = regime.cached("t", fn, x, key={"k": 1}, cache=tmp_path)
    assert np.array_equal(a, fn(x)) and np.array_equal(b, a) and len(list(tmp_path.iterdir())) == 1
    W = regime.cached("w", lambda r: np.column_stack([r, -r]), x, key={}, cache=tmp_path)
    assert np.array_equal(regime.cached("w", None, x, key={}, cache=tmp_path), W)


def test_coverage_guard_refuses_a_missing_scored_decision():
    inp = _inp(11, T=900)
    rows = _rows(inp)
    scored = rows & (inp.index >= inp.index[300])
    k = regime.trend_keep(inp, rows, 10)
    regime.check_coverage("trend", k, scored)
    k[np.flatnonzero(scored)[5], 1] = np.nan
    with pytest.raises(RuntimeError, match="without a gate state"):
        regime.check_coverage("trend", k, scored)


def test_script_wiring_uses_no_future_returns():
    """Review R3 MATERIAL 1: the targets the script uses (regime.targets: L6, L7, L8 and the descriptive rows) at rows
    ≤ t, and the holdings through t + 1, do not move when returns after t change. t runs over the session before each
    decision row and the days of an active drawdown brake; the shock after t (+20% on both sleeves) moves the
    correlation, the trend and the brake, so a decision or multiplier read one row early is caught."""
    T_ = 1400
    inp = _inp(12, T=T_)
    R = inp.R.copy()
    R[700:820] = (-0.006, -0.004)  # a joint drawdown so the trend, correlation and drawdown brake all act
    inp = rungs.Inputs(inp.index, R, inp.bill, inp.mmy, inp.dt)
    rows = _rows(inp)
    dev = np.asarray(inp.index >= inp.index[300])
    l5 = np.tile([0.55, 0.45], (T_, 1))
    a = regime.targets(inp, rows, dev, l5, band=0.05)
    assert (a["g"][dev] < 1).any() and (a["keep"]["trend"][rows & dev] == 0).any()
    books_a = {k: rungs.book(v, inp, band=0.05).held for k, v in a["targets"].items()}
    d = np.flatnonzero(rows)
    ts = sorted({*(d[(d > 600) & (d < 1000)] - 1), *np.flatnonzero(a["g"] < 1)[::3]})
    for t in ts:
        R2 = R.copy()
        R2[t + 1:] = 0.2
        inp2 = rungs.Inputs(inp.index, R2, inp.bill, inp.mmy, inp.dt)
        b = regime.targets(inp2, rows, dev, l5, band=0.05)
        assert np.array_equal(a["g"][:t + 1], b["g"][:t + 1]), t
        for k, v in a["targets"].items():
            assert np.array_equal(v[:t + 1], b["targets"][k][:t + 1], equal_nan=True), (k, t)
            assert np.array_equal(books_a[k][:t + 2], rungs.book(b["targets"][k], inp2, band=0.05).held[:t + 2]), (k, t)
