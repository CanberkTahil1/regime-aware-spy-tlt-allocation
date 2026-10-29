"""Plain references for rspy.regime (R3): the trailing correlation by an explicit np.corrcoef loop."""

import numpy as np


def corr_ref(R, window):
    out = np.full(len(R), np.nan)
    for t in range(window - 1, len(R)):
        out[t] = np.corrcoef(R[t - window + 1:t + 1].T)[0, 1]
    return out
