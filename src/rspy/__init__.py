"""rspy (regime-aware-spy-tlt-allocation v2): a regime-aware SPY/TLT/cash allocation built as a pre-registered ladder,
judged against SPY + T-bills mixed to the same volatility.

Importing the package first keeps every cache inside this repo, even outside make: bytecode under .cache/pycache
(PYTHONPYCACHEPREFIX) and numba's on-disk cache under .cache/numba (numba ignores PYTHONPYCACHEPREFIX; quantkit's
@njit(cache=True) would otherwise write into site-packages or a sibling). Siblings are read-only (CLAUDE.md).
Copied from naive-vs-optimal `src/nvo/__init__.py` @ b5f6278 (← resid-book @ 9a1e939; COPIED.md).
"""

import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ.setdefault("PYTHONPYCACHEPREFIX", str(_ROOT / ".cache" / "pycache"))
if sys.pycache_prefix is None:
    sys.pycache_prefix = os.environ["PYTHONPYCACHEPREFIX"]
os.environ.setdefault("NUMBA_CACHE_DIR", str(_ROOT / ".cache" / "numba"))
