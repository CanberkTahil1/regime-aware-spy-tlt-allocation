"""Plain references for R6's fast or path-dependent code (spec/prereg_r6.yaml; D6.1, D6.3), written out from the
prereg text with no numba and a different formulation where one exists. Equivalence in tests/test_r6.py."""

import datetime as dt

import numpy as np


def asym_ref(raw, dates, mode):
    """D6.1: cuts the same row; step-ups at the last session of each ISO week (weekly) or by α = 1/3 (ewma5)."""
    out = [float("nan")] * len(raw)
    held = None
    for t, x in enumerate(raw):
        if x != x:  # NaN: pass through, state unchanged
            continue
        if held is None or x < held:
            held = x
        elif mode == "weekly":
            this = dates[t].isocalendar()[:2]
            nxt = dates[t + 1].isocalendar()[:2] if t + 1 < len(dates) else None
            if nxt != this:
                held = x
        else:
            held = held + (x - held) / 3.0
        out[t] = held
    return np.array(out)


def blend_ref(nets, helds, dec_rows, cost_rates, cost_mult=1.0):
    """D6.3 in dollars: NAV_i per sub-book compounds by its net return; after the close following a decision row the
    fund total is re-split equally; the reset trade per asset = Σ_i (total/K − NAV_i) · w_i,asset / total."""
    K = len(nets)
    T = len(nets[0])
    nav = [1.0 / K] * K
    out = np.zeros(T)
    for t in range(T):
        before = sum(nav)
        nav = [nav[i] * (1.0 + nets[i][t]) for i in range(K)]
        after = sum(nav)
        cost = 0.0
        if t >= 1 and dec_rows[t - 1] and t + 1 < T:
            N = len(helds[0][0])
            for a in range(N):
                dw = sum((after / K - nav[i]) * helds[i][t + 1][a] for i in range(K)) / after
                cost += cost_mult * cost_rates[a] * abs(dw)
            nav = [after / K] * K
        out[t] = after / before - 1.0 - cost
        # the cost is a fund-level charge (second order on NAV, as rspy.accounting): NAV not reduced
    return out


def iso_week_end(dates):
    return [t + 1 == len(dates) or dates[t + 1].isocalendar()[:2] != d.isocalendar()[:2] for t, d in enumerate(dates)]


def to_dates(index):
    return [dt.date(d.year, d.month, d.day) for d in index]
