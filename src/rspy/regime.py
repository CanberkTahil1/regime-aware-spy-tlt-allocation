"""R3 regime layer L6–L8 and the zoo gates (D3.1–D3.6): monthly gate decisions applied to a daily parent target, the
block-shuffled placebo, the crash multiplier.

A gate is a (T, N) "keep" array: 1 = hold the sleeve, 0 = that sleeve to cash, set on decision rows only (NaN elsewhere).
One line per transform (value at t uses data ≤ t):
- `corr(inp, w)`: Pearson correlation of the two sleeves' daily simple returns over the w rows ending at t (all
  required): `quantkit.value.rolling_corr` (review R3 MINOR: was a pandas re-implementation, equal to 2.3e-14 with no
  sign flip at a decision row); reference tests/reference/regime_ref.py::corr_ref;
- L6 (D3.1) `l6_keep`: at decision row t, keep = [1, corr_t ≤ threshold] (TLT to cash when corr > threshold);
- L7 (D3.2) `trend_keep`: `quantkit.signals.trend.faber(R, dates, months)` on each sleeve's total-return level; the
  decision of month-end e is faber's position from e + 2 (its next-close fill), read back to row e; where e + 2 is
  past the sample, the same SMA rule computed at e (`_sma_keep`, tested equal to faber on every other row);
- zoo gates (D3.6) `state_keep`: keep = [state_t is calm, 1] from a quantkit state stamped t (data ≤ t);
- `gate(parent, keep)`: parent (T, N) daily target × the latest decided keep (decided ≤ t, `rungs.carry`); a 0 keep
  gives a target of exactly 0, which the accounting exits fully (spec accounting.band_zero_target); NaN before the
  first decision (warm-up only, asserted on scored rows by the caller);
- placebo (D3.4) `shuffle_decisions`: the keep rows on the scored decision rows permuted by one
  `quantkit.vol.shuffle_blocks` order (blocks of `block` decisions, seeded), shared by both sleeves; other rows kept;
- L8 (D3.3) `crash_overlay`: `quantkit.sizing.overlay(x, 0.10, rule="dd", sigma=0.10 const, cap=1.0)` on the parent's
  development excess returns; its multiplier g_t is stamped t (returns ≤ t) and multiplies the parent's daily target
  at row t (traded t + 1 by the accounting).
- `targets(inp, rows, dev, l5)`: every R3 target built from L5's daily target in one place (the script's only path;
  tests/test_r3.py perturbs returns after row t and checks targets ≤ t and holdings ≤ t + 1 are unchanged);
- `cached(name, fn, X, **kw)`: fn(X, **kw) cached as Parquet keyed by X's bytes, kw, the quantkit version and this
  file (charter performance contract: shared inputs built once), for the zoo states and the min-CDaR weights.
Complexity: O(T·N) per gate; faber O(T·N); one book per placebo seed (numba walk); hmm_regime ≈ 20 s uncached.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import numpy as np
import pandas as pd
import quantkit
from quantkit import sizing
from quantkit.signals.trend import faber
from quantkit.value import rolling_corr
from quantkit.vol import shuffle_blocks

from rspy import paths, rungs


def spec() -> dict:
    return paths.rules()["r3"]


def corr(inp: rungs.Inputs, window: int) -> np.ndarray:
    return rolling_corr(inp.R[:, 0], inp.R[:, 1], window=window)


def l6_keep(inp: rungs.Inputs, rows: np.ndarray, window: int, threshold: float) -> np.ndarray:
    c = corr(inp, window)
    k = np.full(inp.R.shape, np.nan)
    on = rows & np.isfinite(c)
    k[on, 0] = 1.0
    k[on, 1] = (c[on] <= threshold).astype(float)
    return k


def _month_ends(index: pd.DatetimeIndex) -> np.ndarray:
    per = index.to_period("M")
    return np.flatnonzero(np.r_[per[1:] != per[:-1], True])


def _sma_keep(lvl: np.ndarray, ends: np.ndarray, j: int, months: int) -> np.ndarray:
    e = ends[j]
    return (lvl[e] > lvl[ends[j - months + 1:j + 1]].mean(axis=0)).astype(float)


def trend_keep(inp: rungs.Inputs, rows: np.ndarray, months: int = 10, *, fallback_only: bool = False) -> np.ndarray:
    """keep[e] for month-end decision rows e (D3.2). `fallback_only` computes every row on the SMA path (test hook)."""
    s = faber(inp.R, inp.index, months=months)
    lvl = np.cumprod(1.0 + inp.R, axis=0)
    ends = _month_ends(inp.index)
    T = len(inp.index)
    k = np.full(inp.R.shape, np.nan)
    for e in np.flatnonzero(rows):
        j = int(np.searchsorted(ends, e))
        if j >= len(ends) or ends[j] != e:
            raise ValueError("trend decisions are month-end rows (offset 0); other offsets need the D3.2 SMA path")
        if j < months - 1:
            continue
        if e + 2 < T and not fallback_only:
            k[e] = s[e + 2]
        else:
            k[e] = _sma_keep(lvl, ends, j, months)
    return k


def state_keep(state: np.ndarray, rows: np.ndarray, turbulent) -> np.ndarray:
    """keep = [calm, 1] at decision rows; `turbulent(x)` maps the state value to a bool (zoo gates, D3.6)."""
    st = np.asarray(state, np.float64)
    k = np.full((len(st), 2), np.nan)
    on = rows & np.isfinite(st)
    k[on, 0] = (~turbulent(st[on])).astype(float)
    k[on, 1] = 1.0
    return k


def check_coverage(name: str, keep: np.ndarray, scored_rows: np.ndarray) -> None:
    """D3.1/D3.2/D3.6 guard: a NaN decision on a scored row would silently mean 'not gated' (carry keeps the old one)."""
    bad = int((~np.isfinite(keep[scored_rows])).any(axis=1).sum())
    if bad:
        raise RuntimeError(f"{name}: {bad} scored decision rows without a gate state")


def gate(parent: np.ndarray, keep: np.ndarray) -> np.ndarray:
    return parent * rungs.carry(keep)


def block_perm(n: int, block: int, seed: int) -> np.ndarray:
    return shuffle_blocks(np.arange(n), block=block, seed=seed)


def shuffle_decisions(keep: np.ndarray, rows: np.ndarray, scored: np.ndarray, *, block: int, seed: int) -> np.ndarray:
    r = np.flatnonzero(rows & scored)
    out = keep.copy()
    out[r] = keep[r][block_perm(len(r), block, seed)]
    return out


def crash_overlay(x_excess) -> sizing.Overlay:
    c = spec()["L8"]
    x = np.asarray(x_excess, np.float64)
    return sizing.overlay(x, c["target"], rule=c["rule"], sigma=np.full(len(x), c["sigma"]), cap=c["cap"],
                          d1=c["d1"], d2=c["d2"], e_min=c["e_min"])


def crash_judge(x_excess) -> dict:
    c = spec()["L8"]
    x = np.asarray(x_excess, np.float64)
    j = c["judge"]
    return sizing.judge(x, c["target"], c["rule"], sigma=np.full(len(x), c["sigma"]), cap=c["cap"], d1=c["d1"],
                        d2=c["d2"], e_min=c["e_min"], block=j["block"], seed=j["seed"], draws=j["draws"],
                        mean_block=j["mean_block"])


def cached(name: str, fn, X, *, key: dict, cache: pathlib.Path | None = None) -> np.ndarray:
    """fn(X) cached; `key` (JSON) names everything else fn depends on (its parameters, the decision rows)."""
    X = np.ascontiguousarray(np.asarray(X, np.float64))
    h = hashlib.sha256(X.tobytes() + str(X.shape).encode() + json.dumps(key, sort_keys=True, default=str).encode()
                       + quantkit.__version__.encode() + pathlib.Path(__file__).read_bytes())
    f = (cache or paths.ROOT / ".cache" / "r3") / f"{name}_{h.hexdigest()[:20]}.parquet"
    if f.exists():
        out = pd.read_parquet(f).to_numpy()
        return out[:, 0] if out.shape[1] == 1 else out
    out = np.asarray(fn(X), np.float64)
    f.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(out.reshape(len(out), -1)).rename(columns=str).to_parquet(f)
    return out


def min_cdar_weights(R, rows, *, window: int, alpha: float, floor) -> np.ndarray:
    """quantkit `alloc.min_cdar` on the `window` rows ending at each decision row (NaN elsewhere / before the window)."""
    from quantkit.alloc import min_cdar

    rows = np.asarray(rows, bool)
    W = np.full(np.shape(R), np.nan)
    for t in np.flatnonzero(rows):
        if t + 1 >= window:
            W[t] = min_cdar(R[t - window + 1:t + 1], alpha=alpha, floor=floor)
    return W


def targets(inp: rungs.Inputs, rows: np.ndarray, dev: np.ndarray, l5: np.ndarray, *, band: float) -> dict:
    """L6 (+ 63-day and ±0.2 rows), L7 (+ trend on L5, trend on L6-63) and L8 from L5's daily target (spec r3). L8's
    multiplier g_t comes from the L7 book's development excess returns through row t (`crash_overlay`), 1 before the
    scored window. Returns {"targets", "keep", "g", "x7" (L7 development excess returns), "overlay"}."""
    c6 = spec()["L6"]
    keep = {}
    for w in (c6["windows"]["primary"], c6["windows"]["descriptive"]):
        keep[f"corr{w}"] = l6_keep(inp, rows, w, c6["threshold"])
    for th in c6["sensitivity"]:
        keep[f"corr126_th{th:+.1f}"] = l6_keep(inp, rows, c6["windows"]["primary"], th)
    keep["trend"] = trend_keep(inp, rows, spec()["L7"]["months"])
    T = {"L6": gate(l5, keep["corr126"]), "L6-63": gate(l5, keep["corr63"]),
         "L6-th-0.2": gate(l5, keep["corr126_th-0.2"]), "L6-th+0.2": gate(l5, keep["corr126_th+0.2"])}
    T["L7"] = gate(T["L6"], keep["trend"])
    T["L7-on-L5"] = gate(l5, keep["trend"])
    T["L7-63"] = gate(T["L6-63"], keep["trend"])
    x7 = rungs.book(T["L7"], inp, band=band).net[dev] - inp.bill[dev]
    ov = crash_overlay(x7)
    g = np.ones(len(inp.index))
    g[dev] = ov.mult
    T["L8"] = T["L7"] * g[:, None]
    return {"targets": T, "keep": keep, "g": g, "x7": x7, "overlay": ov}
