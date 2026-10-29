"""Build the daily panel data/panel.parquet from the raw files (make data). Content-hashed: the build key is the sha256
of every raw input + every rspy.data source file + spec/rules.yaml; a changed key rebuilds, an unchanged key is a no-op.
Adapted from naive-vs-optimal `src/nvo/data/build.py` @ b29bb37 (COPIED.md): `to_sessions` and `bill_returns` copied;
the bond legs now come from `quantkit.bonds.total_return` (D1.2); the money-market yield column added (D1.1).

Calendar: KF Hi 20 trading days are the session calendar for every daily leg.
Timing, one line per transform (value at t uses data ≤ t):
- hi20: KF return dated t (lag 0).
- tlt<M>: quantkit.bonds.total_return(curve, M, roll="daily", par_col=None, max_gap_days=7): the return earned on curve
  date d uses the curves at the previous fitted date and d; valid only if SVENY<M> is reported on both dates (D1.2);
  credited to the first session ≥ d (lag 0, never earlier); a session with no curve return earns 0 and the next curve
  return already spans it; returns spanning > 7 calendar days are dropped by quantkit (counted in build.json).
- bill: r_s = P^(−Δ/91) − 1, P = 1 − d·91/360, d = the last H.15 rate dated ≤ the PREVIOUS session (lag 1 session),
  Δ = calendar days between sessions (D1.1).
- mmy: y = (1/P − 1)·360/91 from the same lagged d (financing base, D1.1); dt = Δ/360.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from quantkit import bonds as qbonds

from rspy import paths
from rspy.data import readers
from rspy.data.fetch import RAW


def raw_files(root: Path | None = None) -> dict[str, Path]:
    root = root or paths.data_dir() / "raw"
    return {k: root / v for k, v in RAW.items()}


def build_key(root: Path | None = None) -> dict:
    src = Path(__file__).resolve().parent
    return {
        "raw": {k: paths.sha256(p) for k, p in raw_files(root).items()},
        "code": {f.name: paths.sha256(f) for f in sorted(src.glob("*.py"))},
        "rules": paths.sha256(paths.RULES),
    }


# ---- calendar transforms (copied from naive-vs-optimal build.py @ b29bb37) -------------------------------------------
def to_sessions(r: pd.Series, sessions: pd.DatetimeIndex) -> pd.Series:
    """Credit each curve-date return to the first session ≥ its date and compound per session. A NaN return makes its
    session NaN; sessions before the first curve return are NaN; returns after the last session are discarded."""
    r = r.sort_index()
    pos = sessions.searchsorted(r.index, side="left")
    ok = pos < len(sessions)
    v, p = r.to_numpy(float)[ok], pos[ok]
    out = np.zeros(len(sessions))
    np.add.at(out, p, np.log1p(np.nan_to_num(v)))
    out = np.expm1(out)
    bad = np.zeros(len(sessions), bool)
    bad[p[~np.isfinite(v)]] = True
    out[bad] = np.nan
    if len(p):
        out[: int(p.min())] = np.nan
    else:
        out[:] = np.nan
    return pd.Series(out, index=sessions, name=r.name)


def bill_returns(disc: pd.DataFrame, sessions: pd.DatetimeIndex, days: int = 91) -> pd.DataFrame:
    """D1.1 accrual on the session calendar. Output: date, disc_used (the previous session's rate), ret, mmy, dt."""
    d = disc.set_index("date")["disc"].sort_index()
    prev = sessions[:-1]
    pos = d.index.searchsorted(prev, side="right") - 1  # last rate dated ≤ previous session
    rate = np.where(pos >= 0, d.to_numpy()[np.clip(pos, 0, None)], np.nan)
    gap = np.diff(sessions.to_numpy()).astype("timedelta64[D]").astype(float)
    price = 1.0 - rate * days / 360.0
    ret = price ** (-gap / days) - 1.0
    mmy = (1.0 / price - 1.0) * 360.0 / days
    return pd.DataFrame({"date": sessions[1:], "disc_used": rate, "ret": ret, "mmy": mmy, "dt": gap / 360.0})


# ---- bonds (D1.2) ---------------------------------------------------------------------------------------------------
def bond_leg(curve: pd.DataFrame, maturity: int, *, max_gap_days: int, m: int) -> tuple[pd.Series, dict]:
    """Constant-maturity par TR on curve dates, NaN unless SVENY<M> is reported on both curve dates (D1.2)."""
    r = qbonds.total_return(curve, maturity, roll="daily", m=m, max_gap_days=max_gap_days, par_col=None,
                            check_start=False)  # 25y has no quantkit start; the reported mask below is the guard
    idx = qbonds.fitted(curve).index
    rep = curve[f"SVENY{maturity:02d}"].reindex(idx).notna().cummax()
    prev_rep = pd.Series(rep.to_numpy()[:-1], index=idx[1:])
    ok = (rep.reindex(r.index) & prev_rep.reindex(r.index)).fillna(False).astype(bool)
    gaps = int((np.diff(idx.to_numpy()).astype("timedelta64[D]").astype(float) > max_gap_days).sum())
    return r.where(ok).rename(f"tlt{maturity}"), {"curve_rows": len(idx), "gap_rows_dropped": gaps,
                                                    "first_valid": str(r.where(ok).first_valid_index().date())}


def build(root: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """The daily panel (index = KF sessions) and the build log."""
    spec = paths.rules()
    f = raw_files(root)
    eq = readers.read_kf(f["kf_size_daily"], column=spec["equity"]["column"])
    sessions = pd.DatetimeIndex(eq["date"], name="date")
    panel = pd.DataFrame({"hi20": eq["ret"].to_numpy()}, index=sessions)
    curve = readers.read_gsw(f["gsw_nominal"])
    bc = spec["bonds"]
    log: dict = {"sessions": len(sessions), "first_session": str(sessions[0].date()), "last_session": str(sessions[-1].date())}
    for mat in [bc["maturity_years"], *bc["sensitivity_maturities"]]:
        r, info = bond_leg(curve, mat, max_gap_days=bc["max_gap_days"], m=bc["coupons_per_year"])
        s = to_sessions(r.dropna(), sessions)  # leading NaN until the first valid return
        info["sessions_without_curve_return"] = int(((~sessions.isin(r.dropna().index)) & s.notna()).sum())
        panel[f"tlt{mat}"] = s
        log[f"tlt{mat}"] = info
    h15 = readers.read_h15(f["h15"], series=spec["bills"]["series"])
    b = bill_returns(h15, sessions, spec["bills"]["days"]).set_index("date")
    panel["bill"], panel["mmy"], panel["dt"], panel["disc_used"] = b["ret"], b["mmy"], b["dt"], b["disc_used"]
    log["bill_first_valid"] = str(panel["bill"].first_valid_index().date())
    return panel, log


def write(panel: pd.DataFrame, log: dict, key: dict, dest: Path | None = None) -> Path:
    dest = dest or paths.data_dir()
    dest.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(dest / "panel.parquet")
    (dest / "build.json").write_text(json.dumps({"key": key, "log": log}, indent=1, sort_keys=True))
    return dest


def is_current(root: Path | None = None, dest: Path | None = None) -> bool:
    dest = dest or paths.data_dir()
    p = dest / "build.json"
    return p.exists() and (dest / "panel.parquet").exists() and json.loads(p.read_text())["key"] == build_key(root)


def load(dest: Path | None = None) -> pd.DataFrame:
    """The panel, refusing a stale build (raw, code or rules changed since)."""
    if not is_current(dest=dest):
        raise RuntimeError("data/panel.parquet is missing or stale: run `make data`")
    return pd.read_parquet((dest or paths.data_dir()) / "panel.parquet")
