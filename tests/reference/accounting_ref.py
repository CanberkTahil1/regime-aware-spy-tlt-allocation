"""Plain reference for rspy.accounting.run (D1.3): one Python loop, every formula written out from the charter, no
numba and no quantkit. Equivalence ≤ 1e-10 in tests/test_accounting.py."""

import numpy as np


def run_ref(target, R, bill, mmy, dt, *, cost_rates, spread, stress_spread=0.0, cost_mult=1.0):
    T, N = R.shape
    h = [0.0] * N
    out = {k: np.zeros(T) for k in ("gross", "cash", "financing", "cost", "net", "turnover")}
    held = np.zeros((T, N))
    for t in range(T):
        held[t] = h
        gross = sum(h[i] * R[t, i] for i in range(N))
        invested = sum(h)
        cash = max(1.0 - invested, 0.0) * bill[t]
        borrowed = max(sum(max(x, 0.0) for x in h) - 1.0, 0.0)
        fin = borrowed * (mmy[t] + spread + stress_spread) * dt[t]
        r_pre = gross + cash
        drifted = [h[i] * (1.0 + R[t, i]) / (1.0 + r_pre) for i in range(N)]
        cost = turn = 0.0
        if t >= 1 and not np.isnan(target[t - 1, 0]):  # decided at close t−1, traded at close t
            for i in range(N):
                d = target[t - 1, i] - drifted[i]
                turn += abs(d)
                cost += cost_mult * cost_rates[i] * abs(d)
            drifted = [float(target[t - 1, i]) for i in range(N)]
        out["gross"][t], out["cash"][t], out["financing"][t] = gross, cash, fin
        out["cost"][t], out["turnover"][t] = cost, turn
        out["net"][t] = gross + cash - fin - cost
        h = drifted
    out["held"] = held
    return out
