"""R2 drift-aware no-trade band in rspy.accounting (D2.1, E2.5): fast = reference loop ≤ 1e-10; band 0 = unbanded bit
for bit; a sleeve inside ±b is untouched and one outside lands exactly on the edge; a planted quantkit-style band
(compared to the previous target, no drift) gives a different book."""

import numpy as np
import pytest

from rspy import accounting
from tests.reference.accounting_ref import run_ref
from tests.test_accounting import RATES, _inputs

KW = dict(cost_rates=RATES, spread=0.0025, stress_spread=0.0, cost_mult=1.0)


@pytest.mark.parametrize("seed,every,b", [(0, 1, 0.05), (1, 21, 0.05), (2, 5, 0.02), (3, 1, (0.01, 0.08))])
def test_banded_fast_equals_reference(seed, every, b):
    target, R, bill, mmy, dt = _inputs(seed, decide_every=every)
    bb = np.broadcast_to(np.asarray(b, float), (2,))
    fast = accounting.run(target, R, bill, mmy, dt, band=b, **KW)
    ref = run_ref(target, R, bill, mmy, dt, band=bb, **KW)
    assert np.abs(fast.held - ref["held"]).max() <= 1e-10
    for k in ("gross", "cash", "financing", "cost", "net", "turnover"):
        assert np.abs(getattr(fast, k) - ref[k]).max() <= 1e-10, k


def test_band_zero_is_unbanded_bit_for_bit():
    target, R, bill, mmy, dt = _inputs(4, decide_every=3)
    a = accounting.run(target, R, bill, mmy, dt, **KW)
    b = accounting.run(target, R, bill, mmy, dt, band=0.0, **KW)
    for k in ("held", "net", "turnover", "cost"):
        assert np.array_equal(getattr(a, k), getattr(b, k)), k


def test_band_inside_untouched_outside_to_edge():
    T = 60
    R = np.zeros((T, 2))
    R[10:20, 0] = 0.05  # SPY rallies: its drifted weight rises above 0.60 + 0.05
    bill, mmy, dt = np.zeros(T), np.zeros(T), np.full(T, 1 / 360)
    target = np.full((T, 2), np.nan)
    target[0] = target[25] = target[5] = (0.6, 0.4)
    bk = accounting.run(target, R, bill, mmy, dt, band=0.05, **KW)
    assert np.allclose(bk.held[2], (0.55, 0.35))  # first build from cash also stops at the edge (warm-up only)
    assert bk.turnover[6] == 0.0  # decision at 5 with no drift: inside the band, no trade
    pre = bk.held[25] * (1 + R[25]) / (1 + bk.held[25] @ R[25])
    assert pre[0] > 0.65 and pre[1] < 0.35  # both sleeves drifted out of their bands (0.60 ± 0.05, 0.40 ± 0.05)
    assert np.allclose(bk.held[27], (0.65, 0.35))  # traded at 26 to the nearest edges, not to the targets


def test_planted_band_on_last_target_differs():
    """quantkit's band compares to the previous TARGET (no drift); with a constant target it never trades again,
    while the drift-aware band does: the two books must differ."""
    target, R, bill, mmy, dt = _inputs(5, decide_every=21)
    target[~np.isnan(target[:, 0])] = (0.6, 0.4)
    bk = accounting.run(target, R * 3, bill, mmy, dt, band=0.02, **KW)
    traded_rows = np.flatnonzero(bk.turnover > 0)
    assert len(traded_rows) > 1  # a quantkit-style band would trade only the first build


def test_negative_band_raises():
    target, R, bill, mmy, dt = _inputs(6)
    with pytest.raises(ValueError, match="band"):
        accounting.run(target, R, bill, mmy, dt, band=-0.01, **KW)


def test_zero_target_exits_fully_and_reentry_stops_at_the_edge():
    """R3 D3.1 (spec/rules.yaml accounting.band_zero_target): a sleeve whose target is exactly 0 trades to 0 (a gate
    sends it to cash, no 5 pp stub); the band still applies otherwise, so re-entry from 0 stops at target − b."""
    T = 40
    R = np.zeros((T, 2))
    bill, mmy, dt = np.zeros(T), np.zeros(T), np.full(T, 1 / 360)
    target = np.full((T, 2), np.nan)
    target[0] = (0.6, 0.4)
    target[10] = (0.6, 0.0)  # gate on: TLT to cash
    target[20] = (0.6, 0.4)  # gate off: back in
    bk = accounting.run(target, R, bill, mmy, dt, band=0.05, **KW)
    assert bk.held[12, 1] == 0.0  # fully out, not 0.05
    assert np.isclose(bk.held[22, 1], 0.35)  # re-entry stops at the band edge (disclosed asymmetry)
    ref = run_ref(target, R, bill, mmy, dt, band=np.array([0.05, 0.05]), **KW)
    assert np.abs(bk.held - ref["held"]).max() <= 1e-12


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_banded_fast_equals_reference_with_zero_targets(seed):
    target, R, bill, mmy, dt = _inputs(seed, decide_every=5)
    rows = np.flatnonzero(~np.isnan(target[:, 0]))
    target[rows[::3], 1] = 0.0  # planted gate exits
    target[rows[1::4], 0] = 0.0
    fast = accounting.run(target, R, bill, mmy, dt, band=0.05, **KW)
    ref = run_ref(target, R, bill, mmy, dt, band=np.array([0.05, 0.05]), **KW)
    assert np.abs(fast.held - ref["held"]).max() <= 1e-10
    assert np.abs(fast.net - ref["net"]).max() <= 1e-10
