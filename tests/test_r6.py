"""R6 (spec/prereg_r6.yaml; O6.1, O6.2, D6.1-D6.5): the asymmetric vol-target recursion and the blend against plain
references, the CPI parse / gate timing (release lag, the 2025-10 gap, no look-ahead), the verdict table, 1 vs N
workers, and that R6 leaves R5's lock untouched."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from r6lib import books, cpi, report, spec
from rspy import freeze, paths, rungs
from tests.reference.r6_ref import asym_ref, blend_ref, iso_week_end, to_dates


def _index(n, seed=0):
    idx = pd.bdate_range("2019-01-01", periods=n + 10)
    rng = np.random.default_rng(seed)
    return pd.DatetimeIndex(np.sort(rng.choice(idx, n, replace=False)))  # gaps = holidays / short weeks


# ---- D6.1 ------------------------------------------------------------------------------------------------------------
@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 10_000), n=st.integers(2, 120), mode=st.sampled_from(["weekly", "ewma5"]))
def test_asym_equals_reference(seed, n, mode):
    rng = np.random.default_rng(seed)
    idx = _index(n, seed)
    raw = rng.uniform(0, 2, n)
    raw[rng.random(n) < 0.1] = np.nan
    out = books.asym(raw, idx, mode)
    ref = asym_ref(raw, to_dates(idx), mode)
    assert np.array_equal(np.isnan(out), np.isnan(ref))
    np.testing.assert_allclose(out, ref, rtol=0, atol=1e-12)


@settings(max_examples=30, deadline=None)
@given(seed=st.integers(0, 10_000), n=st.integers(3, 120), mode=st.sampled_from(["weekly", "ewma5"]))
def test_asym_properties(seed, n, mode):
    rng = np.random.default_rng(seed)
    idx = _index(n, seed)
    raw = rng.uniform(0, 2, n)
    out = books.asym(raw, idx, mode)
    prev = np.r_[np.nan, out[:-1]]
    cut = raw < prev
    assert np.array_equal(out[cut], raw[cut])                 # a cut applies on its own row
    assert (out[~cut & np.isfinite(prev)] >= prev[~cut & np.isfinite(prev)] - 1e-15).all()  # never cut otherwise
    if mode == "weekly":
        wk = books.week_end(idx)
        assert np.array_equal(out[wk], raw[wk])               # every week-end session resets to raw
    t = int(rng.integers(1, n))                               # no look-ahead: changing raw after t moves nothing <= t
    raw2 = raw.copy()
    raw2[t:] = rng.uniform(0, 2, n - t)
    np.testing.assert_array_equal(books.asym(raw2, idx, mode)[:t], out[:t])


def test_week_end_iso_and_short_weeks():
    idx = pd.DatetimeIndex(["2020-12-28", "2020-12-29", "2020-12-30", "2020-12-31",       # ISO week 53 of 2020
                            "2021-01-04", "2021-01-05", "2021-01-08", "2021-01-11"])
    assert books.week_end(idx).tolist() == [False, False, False, True, False, False, True, True]
    assert books.week_end(idx).tolist() == iso_week_end(to_dates(idx))


# ---- D6.3 ------------------------------------------------------------------------------------------------------------
def _fake_books(T, K, seed):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=T)
    out = []
    for _ in range(K):
        held = rng.uniform(0, 1.2, (T, 2))
        out.append(rungs.accounting.Book(idx, held, rng.normal(0, 0.01, T), np.zeros(T), rng.uniform(0, 1e-5, T),
                                         rng.uniform(0, 1e-4, T), rng.normal(3e-4, 0.01, T), rng.uniform(0, 0.3, T),
                                         np.ones(T, bool)))
    return idx, out


@settings(max_examples=30, deadline=None)
@given(seed=st.integers(0, 10_000), T=st.integers(3, 150))
def test_blend_equals_dollar_reference(seed, T):
    idx, bks = _fake_books(T, 3, seed)
    dec = np.r_[idx[1:].month != idx[:-1].month, False]          # last session of each month
    rates = np.array([3e-4, 2e-4])
    f = books.blend(bks, dec, cost_rates=rates, cost_mult=2.0)
    ref = blend_ref([b.net for b in bks], [b.held for b in bks], dec, rates, 2.0)
    np.testing.assert_allclose(f["net"], ref, rtol=0, atol=1e-12)
    np.testing.assert_allclose(f["shares"].sum(axis=1), 1.0, atol=1e-12)
    after = np.flatnonzero(np.r_[False, dec[:-1]]) + 1           # shares are exactly 1/3 the row after each reset
    after = after[after < T]
    np.testing.assert_allclose(f["shares"][after], 1 / 3, atol=1e-15)


def test_blend_of_identical_books_is_the_book():
    idx, (b,) = _fake_books(80, 1, 7)
    dec = np.r_[idx[1:].month != idx[:-1].month, False]
    f = books.blend([b, b, b], dec, cost_rates=np.array([3e-4, 2e-4]))
    np.testing.assert_allclose(f["net"], b.net, atol=1e-15)
    assert f["reset_turnover"].max() < 1e-15
    np.testing.assert_allclose(f["turnover"], b.turnover, atol=1e-15)


# ---- O6.2 / D6.2: CPI ------------------------------------------------------------------------------------------------
def _payload(rows):
    return {"Results": {"series": [{"data": [{"year": y, "period": p, "value": v} for y, p, v in rows]}]}}


def test_parse_drops_m13_and_reads_dash_as_missing():
    s = cpi.parse(_payload([("2025", "M13", "321.9"), ("2025", "M10", "-"), ("2025", "M09", "324.800")]))
    assert list(s.index.astype(str)) == ["2025-09", "2025-10"]
    assert s["2025-09"] == 324.8 and np.isnan(s["2025-10"])


def _cpi(months=400, seed=0, miss=()):
    rng = np.random.default_rng(seed)
    idx = pd.period_range("1980-01", periods=months, freq="M")
    s = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.003, 0.002, months))), index=idx)
    for m in miss:
        s[m] = np.nan
    return s


def test_state_windows_and_gap_rule():
    s = _cpi(400, miss=["2000-06"])
    stt = cpi.state(s)
    pi = np.log(s / s.shift(1))
    m = pd.Period("1999-12", "M")
    assert stt.v[m] == pytest.approx(pi.loc[m - 11:m].std(ddof=1), abs=1e-15)
    assert stt.med[m] == pytest.approx(stt.v.loc[m - 119:m].median(), abs=1e-15)
    assert np.isnan(stt.pi["2000-06"]) and np.isnan(stt.pi["2000-07"])
    assert stt.v.loc["2000-06":"2001-05"].notna().all()           # 10 or 11 of 12 pi defined: still defined
    assert stt.high.loc["1991-01":].notna().all()


def test_keep_reads_the_previous_month_only():
    s = _cpi(400)
    idx = pd.bdate_range("1995-01-02", "2010-12-31")
    rows = np.r_[idx[1:].month != idx[:-1].month, False]
    st0 = cpi.state(s)
    k0 = cpi.keep(idx, rows, st0)
    for t in np.flatnonzero(rows):                                # decision of month M reads high_{M-1}, exactly
        m = idx[t].to_period("M")
        assert k0[t, 1] == 1.0 - st0.high[m - 1]
    assert (st0.high[rows_m := idx[rows].to_period("M")] != st0.high[rows_m - 1].to_numpy()).any()  # lag matters here
    s2 = s.copy()
    s2["2005-06"] *= 1.05                                         # a shock in June 2005
    k1 = cpi.keep(idx, rows, cpi.state(s2))
    june_end = int(np.flatnonzero(rows & (idx.year == 2005) & (idx.month == 6))[0])
    np.testing.assert_array_equal(k0[: june_end + 1], k1[: june_end + 1])   # June's decision cannot see June's CPI
    assert not np.array_equal(k0[june_end + 1:], k1[june_end + 1:])        # July's can (lag one month)
    assert np.isnan(k0[~rows]).all() and np.isfinite(k0[rows]).all()
    assert (k0[rows, 0] == 1).all()


def test_real_cpi_files_if_present():
    if cpi.verify():
        pytest.skip("data/r6/raw not fetched (make r6-data)")
    s = cpi.read()
    assert [str(m) for m in s.index[s.isna()]] == ["2025-10"]
    assert str(s.index[0]) == "1975-01"


# ---- D6.4 ------------------------------------------------------------------------------------------------------------
def test_verdict_table_complete_and_words():
    w = spec()["verdict"]["words"]
    assert len(w) == 9 and {k.split(",")[0] for k in w} == {"better", "same", "worse"}
    assert report.verdict("same", "better") == "better only in the period that inspired it"
    assert report.word(0.06, 0.01, 0.1, 1.0, 0.9, 1.1) == ("better", "Sharpe", True)
    assert report.word(0.0, -0.1, 0.1, 0.80, 0.7, 0.95) == ("better", "drawdown", True)
    assert report.word(-0.04, -0.2, 0.1, 0.80, 0.6, 1.1) == ("better", "drawdown", False)
    assert report.word(-0.06, -0.2, 0.1, 0.5, 0.4, 0.6) == ("worse", "Sharpe", False)   # Sharpe wins outside the band
    assert report.word(0.04, -0.2, 0.2, 1.2, 1.05, 1.3) == ("worse", "drawdown", True)
    assert report.word(0.0, -0.1, 0.1, 1.0, 0.9, 1.1)[0] == "same"


def test_candidates_registered_and_counted():
    c = report.candidates()
    assert len(c) == spec()["dsr"]["n_r6"] == 15
    v = pd.read_csv(paths.REPORTS / "variants.csv")
    r6 = v[(v.phase == "R6") & (v.counted_in_dsr == "yes")]
    assert int(r6.n_configs.sum()) == 15
    assert spec()["dsr"]["test"]["n_raw"] == 751 + 15 and spec()["dsr"]["test"]["n_headline"] == 5 + 15


def test_one_vs_n_workers_identical():
    rng = np.random.default_rng(3)
    T = 400
    c = np.full(T, 1e-4)
    tasks = [(rng.normal(4e-4, 0.01, T), rng.normal(3e-4, 0.012, T), c, np.full(T, 0.02), np.full(T, 1 / 360))
             for _ in range(3)]
    a, b = report.run_pairs(tasks, 1), report.run_pairs(tasks, 2)
    assert json.dumps(a, default=float, sort_keys=True) == json.dumps(b, default=float, sort_keys=True)


# ---- O6.1: R5's lock untouched ------------------------------------------------------------------------------------------
def test_r6_leaves_the_r5_lock_untouched():
    if not (paths.data_dir() / "panel.parquet").exists():
        pytest.skip("no data/panel.parquet")
    assert freeze.verify(git=False, replay=True) == []        # only the Makefile is replay-exempt (D5.9)
    lock = freeze.read()
    assert not any(f.startswith(("r6lib/", "scripts/r6", "spec/prereg_r6")) for f in lock["files"])
