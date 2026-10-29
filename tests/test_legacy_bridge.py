"""R1 reconciliation bridge (D1.4): the mirror of v1's scaling is v1 exactly (E1.1), the t+1 step is one row later,
rspy.accounting places v1's decision on the same rows as the shifted v1 book (timing frameworks agree), S4 = S3 returns
exactly (E1.5), S5-S7 hold no short (E1.6). Uses v1's cached data (marker legacy: fails if missing, D0.3)."""

import contextlib
import importlib
import io

import numpy as np
import pandas as pd
import pytest

from tests.legacy_support import V1_TABLES, check_v1_data

pytestmark = pytest.mark.legacy


@pytest.fixture
def v1(no_yahoo, monkeypatch):
    try:
        path = check_v1_data()
    except (FileNotFoundError, ValueError) as e:
        pytest.fail(str(e))
    data = importlib.import_module("legacy.data")
    monkeypatch.setattr(data, "DATA_PATH", path)
    with contextlib.redirect_stdout(io.StringIO()):
        prices, returns = data.prepare_data()
    from rspy import legacy_bridge as lb

    return lb, prices, returns


def _bills(index):
    n = len(index)
    return pd.DataFrame({"bill": np.full(n, 1e-4), "mmy": np.full(n, 0.0365), "dt": np.full(n, 1 / 360)}, index=index)


def test_mirror_is_v1_and_s0_reproduces_committed_test_metrics(v1):
    lb, prices, returns = v1
    bt = importlib.import_module("legacy.backtest")
    sig = lb.v1_signals(prices, returns)
    s0 = lb.v1_book(lb.v1_scaled(sig, returns), returns)["net"]
    want = bt.compute_strategy_returns(sig, returns)
    assert np.abs(s0 - want).max() <= 1e-15
    m = lb.v1_metrics(s0, ("2020-01-01", "2025-12-31"))
    t = pd.read_csv(V1_TABLES / "test_metrics.csv").set_index("Metric")["Strategy"]
    for k, key in [("cagr", "Annual Return"), ("vol", "Volatility"), ("sharpe", "Sharpe"), ("sortino", "Sortino"),
                   ("max_dd", "Max Drawdown")]:
        assert abs(m[k] - t[key]) <= 1e-12, k


def test_t_plus_one_and_accounting_timing_agree(v1):
    lb, prices, returns = v1
    scaled = lb.v1_scaled(lb.v1_signals(prices, returns), returns)
    held1 = scaled.shift(1).fillna(0.0)
    bills = _bills(returns.index)
    s3 = lb.run_accounting(scaled, returns, bills, rates=np.array([3e-4, 2e-4]), spread=0.0025, allow_shorts=True)
    # rspy.accounting holds v1's decision (scaled[t], decided at close t−1) over row t+1 = the S1 book
    np.testing.assert_array_equal(s3[["w_SPY", "w_TLT"]].to_numpy()[2:], held1.to_numpy()[2:])
    s5 = lb.run_accounting(scaled, returns, bills, rates=np.array([3e-4, 2e-4]), spread=0.0025, allow_shorts=False,
                           floor_zero=True)
    assert (s5[["w_SPY", "w_TLT"]].to_numpy() >= 0).all()
    with pytest.raises(ValueError, match="shorts"):
        lb.run_accounting(scaled, returns, bills, rates=np.array([3e-4, 2e-4]), spread=0.0025, allow_shorts=False)


def test_rv_proxy_uses_returns_up_to_t_only():
    from rspy.legacy_bridge import rv_proxy

    r = pd.Series(np.random.default_rng(0).normal(0, 0.01, 60), index=pd.bdate_range("2010-01-01", periods=60))
    a = rv_proxy(r, r.index, 20)
    r2 = r.copy()
    r2.iloc[40:] *= 5
    b = rv_proxy(r2, r.index, 20)
    assert a.iloc[:40].equals(b.iloc[:40]) and a.iloc[:19].isna().all() and np.isfinite(a.iloc[19])
