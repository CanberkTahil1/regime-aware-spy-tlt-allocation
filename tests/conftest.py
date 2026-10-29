"""Copied from naive-vs-optimal `tests/conftest.py` @ b5f6278 (COPIED.md), renamed; the SEC-lock lines dropped (no EDGAR
here); the v1 yfinance stub fixture added (D0.2).

Pin check for every pytest run: the quantkit files the tests loaded must match spec/quantkit_pin.json.

Under xdist each worker reports the quantkit files it loaded (workeroutput); the controller adds its own, checks the
union at session end (rspy.pin.verify_loaded) and turns a passing run into a failure if any loaded file changed
or is unpinned. Tests of the pin itself use their own temporary trees and are unaffected.
"""

from __future__ import annotations

import os
import pathlib
import sys

# Before any further import: bytecode goes under .cache/pycache, never into ../quantkit (resid-arb review P3 N7). The env var
# reaches xdist workers and loky children; sys.pycache_prefix covers this process when pytest is run without make.
_PYCACHE = str(pathlib.Path(__file__).resolve().parents[1] / ".cache" / "pycache")
os.environ.setdefault("PYTHONPYCACHEPREFIX", _PYCACHE)
if sys.pycache_prefix is None:
    sys.pycache_prefix = os.environ["PYTHONPYCACHEPREFIX"]
# numba ignores PYTHONPYCACHEPREFIX: its cache must point here before numba is first imported (bond-flows P6 F3).
os.environ.setdefault("NUMBA_CACHE_DIR", str(pathlib.Path(__file__).resolve().parents[1] / ".cache" / "numba"))
import pytest  # noqa: E402

from rspy import pin  # noqa: E402

_WORKER_FILES: set[str] = set()


def pytest_sessionfinish(session):
    files = {str(p) for p in pin.loaded_files()}
    wo = getattr(session.config, "workeroutput", None)
    if wo is not None:  # xdist worker: hand the list to the controller
        wo["quantkit_loaded"] = sorted(files)
        return
    probs = pin.verify_loaded([pathlib.Path(f) for f in sorted(files | _WORKER_FILES)])
    session.config._quantkit_pin = (len(files | _WORKER_FILES), probs)
    if probs and session.exitstatus == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):  # xdist controller only
    _WORKER_FILES.update(getattr(node, "workeroutput", {}).get("quantkit_loaded", []))


def pytest_terminal_summary(terminalreporter, config):
    res = getattr(config, "_quantkit_pin", None)
    if res is not None:
        n, probs = res
        terminalreporter.write_line(
            f"quantkit pin (loaded modules): OK ({n} files)" if not probs else "quantkit pin (loaded modules): FAIL"
        )
        for p in probs:
            terminalreporter.write_line(f"  {p}")


@pytest.fixture
def no_yahoo(monkeypatch):
    """D0.2: v1 imports yfinance at module top; a raising stub stands in, so v1 can never re-download (Yahoo excluded)."""
    from tests.legacy_support import yfinance_stub

    monkeypatch.setitem(sys.modules, "yfinance", yfinance_stub())
