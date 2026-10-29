"""CPI-U NSA (BLS series CUUR0000SA0) and the R6c inflation-volatility gate (owner O6.2; advisor D6.2;
spec/prereg_r6.yaml data.cpi, candidates.R6c.inflation_gate).

Fetch: the BLS public API v1 (POST, 10-year chunks); bytes on disk under data/r6/raw/bls/ with one manifest line each
(UTC, URL, bytes, sha256), the rspy.data.fetch pattern. Not FRED (O6.2). Nothing here is cached from FRED.
One line per transform (value at month-end decision M uses data ≤ M − 1):
- `read`: periods M01–M12 (M13 annual averages dropped); "-" (footnote X: 2025-10, the 2025 lapse in appropriations) is
  missing; values as published (3 decimals), no rebasing;
- π_m = ln(CPI_m / CPI_{m−1}), undefined if either is missing (so 2025-10 and 2025-11 are undefined);
- v_m = sample std (ddof 1) of the π over the 12 months ending at m, defined iff ≥ 10 of them are;
- med_m = plain sample median of v over the 120 months ending at m (v_m included), defined iff ≥ 100 of them are;
- high_m = v_m > med_m; the decision at the month-end close of M reads high_{M−1} (BLS publishes month m during m + 1;
  checked against the BLS release archive 1994–2026, assumed before 1994, prereg_r6 lag_check);
- `keep(index, rows)`: (T, 2) keep = [1, 0 if high else 1] on the decision rows; an undefined decision is NaN (the
  caller carries the previous one and must find none on scored rows).
Complexity: O(months · 120) for the rolling median (≈ 620 months; trivial).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import urllib.request

import numpy as np
import pandas as pd

from r6lib import data_dir, spec

URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
UA = "regime-aware-spy-tlt-allocation research (private, non-commercial)"
CHUNKS = [(1975, 1984), (1985, 1994), (1995, 2004), (2005, 2014), (2015, 2024), (2025, 2026)]


def raw_dir() -> pathlib.Path:
    return data_dir() / "raw"


def chunk_path(y0: int, y1: int, root: pathlib.Path | None = None) -> pathlib.Path:
    return (root or raw_dir()) / "bls" / f"{spec()['data']['cpi']['series']}_{y0}_{y1}.json"


def fetch(root: pathlib.Path | None = None) -> list[dict]:
    """Download every chunk (BLS v1 allows 10 years per query); refuse a response that is not REQUEST_SUCCEEDED."""
    root = root or raw_dir()
    sid = spec()["data"]["cpi"]["series"]
    out = []
    for y0, y1 in CHUNKS:
        body = json.dumps({"seriesid": [sid], "startyear": str(y0), "endyear": str(y1)}).encode()
        req = urllib.request.Request(URL, data=body, headers={"User-Agent": UA, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
        if json.loads(b).get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS {y0}-{y1}: {json.loads(b).get('status')} {json.loads(b).get('message')}")
        p = chunk_path(y0, y1, root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
        line = {"utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "url": f"{URL} {body.decode()}",
                "path": str(p.relative_to(root)), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        with open(root / "manifest.jsonl", "a") as f:
            f.write(json.dumps(line, sort_keys=True) + "\n")
        out.append(line)
    return out


def verify(root: pathlib.Path | None = None) -> list[str]:
    """Problems with the raw CPI files: a missing chunk or a sha256 different from the latest manifest line."""
    root = root or raw_dir()
    man = root / "manifest.jsonl"
    if not man.exists():
        return [f"{man} missing (run `make r6-data`)"]
    last = {}
    for ln in man.read_text().splitlines():
        d = json.loads(ln)
        last[d["path"]] = d["sha256"]
    probs = []
    for y0, y1 in CHUNKS:
        p = chunk_path(y0, y1, root)
        rel = str(p.relative_to(root))
        if not p.exists():
            probs.append(f"{rel} missing (run `make r6-data`)")
        elif last.get(rel) != hashlib.sha256(p.read_bytes()).hexdigest():
            probs.append(f"{rel}: sha256 differs from the manifest")
    return probs


def parse(payload: dict) -> pd.Series:
    rows = {}
    for s in payload["Results"]["series"]:
        for x in s["data"]:
            if not (x["period"].startswith("M") and x["period"] != "M13"):
                continue
            m = pd.Period(f"{x['year']}-{x['period'][1:]}", "M")
            v = x["value"].strip()
            rows[m] = float(v) if v not in ("-", "") else np.nan
    return pd.Series(rows, dtype=float).sort_index()


def read(root: pathlib.Path | None = None) -> pd.Series:
    """Monthly CPI (PeriodIndex, every month from the first to the last published; missing = NaN)."""
    parts = [parse(json.loads(chunk_path(y0, y1, root).read_text())) for y0, y1 in CHUNKS]
    s = pd.concat(parts)
    if s.index.duplicated().any():
        raise ValueError("overlapping CPI chunks")
    s = s.sort_index()
    full = pd.period_range(s.index[0], s.index[-1], freq="M")
    return s.reindex(full).rename("cpi")


def state(cpi: pd.Series) -> pd.DataFrame:
    """pi, v, med, high by reference month (high NaN where v or med is undefined)."""
    g = spec()["candidates"]["R6c"]["inflation_gate"]
    assert "12 months" in g["v"] and "120 months" in g["median"]  # the registered windows, read once
    pi = np.log(cpi / cpi.shift(1))
    v = pi.rolling(12, min_periods=10).std(ddof=1)
    med = v.rolling(120, min_periods=100).median()
    high = (v > med).astype(float).where(v.notna() & med.notna())
    return pd.DataFrame({"cpi": cpi, "pi": pi, "v": v, "med": med, "high": high})


def keep(index: pd.DatetimeIndex, rows: np.ndarray, st: pd.DataFrame) -> np.ndarray:
    """(T, 2) keep on decision rows: the decision of month M (its last session) reads high_{M−1}."""
    k = np.full((len(index), 2), np.nan)
    months = index.to_period("M")
    for t in np.flatnonzero(rows):
        m = months[t] - 1
        h = st["high"].get(m, np.nan)
        if np.isfinite(h):
            k[t] = (1.0, 0.0 if h > 0 else 1.0)
    return k
