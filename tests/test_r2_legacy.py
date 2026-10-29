"""E2.6 (D2.3): L2 is v1's own scaling on an all-SPY signal: the mirror `legacy_bridge.v1_scaled` on that signal, booked
with v1's accounting, equals v1's `compute_strategy_returns` ≤ 1e-12 on v1's cached data (marker legacy, D0.3)."""

import importlib

import numpy as np
import pandas as pd
import pytest

from tests.test_legacy_bridge import v1  # noqa: F401  (fixture)

pytestmark = pytest.mark.legacy


def test_l2_mirror_is_v1_on_an_all_spy_signal(v1):  # noqa: F811
    lb, _prices, returns = v1
    bt = importlib.import_module("legacy.backtest")
    sig = pd.DataFrame({"SPY_pos": 1.0, "TLT_pos": 0.0}, index=returns.index)
    mine = lb.v1_book(lb.v1_scaled(sig, returns), returns)["net"]
    want = bt.compute_strategy_returns(sig, returns)
    assert np.abs(mine - want).max() <= 1e-12
    held = lb.v1_scaled(sig, returns)
    assert held["SPY_pos"].max() == 2.0 and (held["TLT_pos"] == 0).all()  # cap 2, never TLT
