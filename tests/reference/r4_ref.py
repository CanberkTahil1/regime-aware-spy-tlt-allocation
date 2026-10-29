"""Plain references for rspy.robust (R4): v1's spread / Bollinger states and the GBM label by explicit loops, written
from the definitions in spec/prereg.yaml r4_zoo (not from v1's code)."""

import math

import numpy as np


def spread_keep_ref(r_spy, r_tlt, window, th):
    """keep_t: z_t = (s_t − mean(s_{t−w..t−1})) / sd(s_{t−w..t−1}, ddof 1); z > th ⇒ SPY 0; z < −th ⇒ TLT 0."""
    s = np.asarray(r_spy) - np.asarray(r_tlt)
    keep = np.ones((len(s), 2))
    for t in range(window, len(s)):
        h = s[t - window:t]
        if np.isnan(h).any() or np.isnan(s[t]):
            continue
        sd = h.std(ddof=1)
        if sd == 0:
            continue
        z = (s[t] - h.mean()) / sd
        if z > th:
            keep[t, 0] = 0.0
        elif z < -th:
            keep[t, 1] = 0.0
    return keep


def bollinger_keep_ref(p_spy, p_tlt, window, k):
    """keep_t from the ratio q_t = p_spy/p_tlt against mean ± k·sd of q_{t−w..t−1} (ddof 1)."""
    q = np.asarray(p_spy) / np.asarray(p_tlt)
    keep = np.ones((len(q), 2))
    for t in range(window, len(q)):
        h = q[t - window:t]
        m, sd = h.mean(), h.std(ddof=1)
        if q[t] > m + k * sd:
            keep[t, 0] = 0.0
        elif q[t] < m - k * sd:
            keep[t, 1] = 0.0
    return keep


def gbm_label_ref(r, h=21, lag=2):
    """y_t = log sqrt(252 · mean(r_{t+lag} … r_{t+lag+h−1}²)); NaN where any is missing or past the end."""
    r = np.asarray(r, np.float64)
    out = np.full(len(r), np.nan)
    for t in range(len(r)):
        a, b = t + lag, t + lag + h
        if b <= len(r):
            w = r[a:b]
            if np.isfinite(w).all():
                out[t] = math.log(math.sqrt(252 * np.mean(w**2)))
    return out
