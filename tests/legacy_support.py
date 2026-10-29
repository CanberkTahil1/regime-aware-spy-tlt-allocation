"""Support for the v1 characterization tests (D0.1-D0.3). Not part of `rspy`: v1 is frozen and lives in `legacy/`.

- `yfinance_stub()`: the one raising stand-in for v1's top-level `import yfinance` (D0.2). Yahoo is excluded by the
  charter; v1 reads its cached prices, so any attribute access means a download was attempted and must fail loudly.
- `check_v1_data(path)`: the cached file must exist and hash to the blob v1 committed in 5ccc12c (D0.3: hashed from the
  file's bytes, not from `HEAD:`, so the check survives the owner untracking it).
"""

from __future__ import annotations

import hashlib
import pathlib
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
V1_DATA = ROOT / "data" / "prices.csv"
V1_BLOB = "900f1dbf0cab27f32da7926aa6bca5ef3a5dee03"  # git blob of data/prices.csv @ 5ccc12c
V1_TABLES = ROOT / "legacy" / "results" / "tables"
EXCLUDED = "yfinance is excluded by the charter (Yahoo; LICENSES.md); legacy v1 runs from the cached data/prices.csv only"


def yfinance_stub() -> types.ModuleType:
    mod = types.ModuleType("yfinance")

    def __getattr__(name: str):
        raise AttributeError(f"{EXCLUDED} (attribute {name!r} requested)")

    mod.__getattr__ = __getattr__
    return mod


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def check_v1_data(path: pathlib.Path = V1_DATA, want: str = V1_BLOB) -> pathlib.Path:
    if not path.is_file():
        raise FileNotFoundError(
            f"v1 data missing: {path} (want git blob {want}). The legacy tests need the local copy; "
            'deselect them explicitly with -m "not legacy" (make test-nolegacy) on a machine without it.'
        )
    got = git_blob_sha1(path.read_bytes())
    if got != want:
        raise ValueError(f"v1 data changed: {path} is blob {got}, want {want} (5ccc12c)")
    return path
