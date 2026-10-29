"""Download raw source files into data/raw/<source>/ (gitignored) and append one manifest line per file (UTC, URL,
bytes, sha256) to data/raw/manifest.jsonl. Each series from its source agency (LICENSES.md). A download is bytes on
disk: nothing here parses a value. No credentials are needed for any source.
Adapted from naive-vs-optimal `src/nvo/data/fetch.py` @ b29bb37 (COPIED.md): KF, GSW nominal and H.15 only.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

from rspy import paths

UA = "regime-aware-spy-tlt-allocation research (private, non-commercial)"
RAW = {
    "kf_size_daily": "kf/Portfolios_Formed_on_ME_daily_CSV.zip",
    "gsw_nominal": "fed/feds200628.csv",
    "h15": "fed/FRB_H15.zip",
}


def _manifest(root: Path, url: str, path: Path) -> dict:
    b = path.read_bytes()
    line = {"utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "url": url,
            "path": str(path.relative_to(root)), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
    with open(root / "manifest.jsonl", "a") as f:
        f.write(json.dumps(line, sort_keys=True) + "\n")
    return line


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def fetch_public(root: Path | None = None) -> list[dict]:
    """KF size portfolios (daily), GSW nominal curve, H.15. Returns the manifest lines written."""
    root = root or paths.data_dir() / "raw"
    src = paths.rules()["sources"]
    out = []
    for key, rel in RAW.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_get(src[key]))
        out.append(_manifest(root, src[key], path))
    return out
