"""Raw-file readers, one per source. Adapted from naive-vs-optimal `src/nvo/data/readers.py` @ b29bb37 (COPIED.md):
the seal cuts are removed (this charter has no sealed window); parsing is unchanged.

Timing, one line per source (value at t uses data ≤ t):
- KF Hi 20 daily: the return dated t is known at t's close (lag 0).
- GSW nominal curve: the curve dated t is known at t's close for return marking (lag 0; returns only — a future SIGNAL
  use would need the Fed's weekly posting lag).
- H.15 3-month bill: the discount rate dated t is known at t's close; returns accrue at the previous session's rate (D1.1).
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pandas as pd


def read_kf(path: Path, *, column: str = "Hi 20") -> pd.DataFrame:
    """Value-weighted daily section of Portfolios_Formed_on_ME_daily. Output: date, ret (decimal)."""
    with zipfile.ZipFile(path) as z:
        text = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    i = next(k for k, ln in enumerate(text) if "Value Weighted Returns -- Daily" in ln)
    head = text[i + 1].split(",")
    rows = []
    for ln in text[i + 2:]:
        s = ln.strip()
        if not re.match(r"^\d{8},", s):
            break  # end of the value-weighted section
        rows.append(s)
    df = pd.read_csv(io.StringIO("\n".join([",".join(head)] + rows)), header=0)
    df.columns = ["date"] + [c.strip() for c in df.columns[1:]]
    v = df[column].astype(float)
    if v.isin([-99.99, -999.0]).any():
        raise ValueError(f"KF {column}: missing-value codes inside the series")
    return pd.DataFrame({"date": pd.to_datetime(df["date"].astype(str), format="%Y%m%d"), "ret": v / 100.0})


def read_gsw(path: Path) -> pd.DataFrame:
    """GSW curve file (feds200628): all columns, DatetimeIndex 'date', sorted."""
    lines = Path(path).read_text().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("Date,"))
    keep = [lines[i]] + [ln for ln in lines[i + 1:] if ln[:10]]
    df = pd.read_csv(io.StringIO("\n".join(keep)), na_values=["NA", ""])
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("Date")), name="date")
    return df.sort_index()


def read_h15(path: Path, *, series: str = "RIFSGFSM03_N.B") -> pd.DataFrame:
    """One H.15 series from the DDP SDMX zip. Only OBS_STATUS="A" rows (ND rows carry −9999). Output: date, disc."""
    with zipfile.ZipFile(path) as z:
        x = z.read("H15_data.xml").decode()
    i = x.find(f'SERIES_NAME="{series}"')
    if i < 0:
        raise KeyError(series)
    blk = x[i:x.find("</kf:Series>", i)]
    obs = re.findall(r'OBS_STATUS="A" OBS_VALUE="([^"]+)" TIME_PERIOD="(\d{4}-\d\d-\d\d)"', blk)
    out = pd.DataFrame({"date": pd.to_datetime([d for _, d in obs]), "disc": [float(v) / 100.0 for v, _ in obs]})
    return out.sort_values("date", ignore_index=True)
