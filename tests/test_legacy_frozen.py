"""D0.1: every v1 module in legacy/ equals its v1 original (7b02cee) once the `legacy.` import prefix is undone, and the
committed v1 tables are the v1 bytes. Any other edit to v1 fails here. Needs no data (not marked legacy)."""

import re
import subprocess

import pytest

from tests.legacy_support import ROOT

V1 = "7b02cee"
MODULES = ["config.py", "data.py", "utils.py", "backtest.py", "run.py", "signals/__init__.py", "signals/bollinger.py",
           "signals/regime.py", "signals/spread.py", "signals/regime_allocation.py"]
TABLES = ["results/tables/test_metrics.csv", "results/tables/summary_metrics.csv", "results/tables/grid_search_results.csv"]


def _v1(path: str) -> bytes:
    return subprocess.run(["git", "show", f"{V1}:{path}"], cwd=ROOT, capture_output=True, check=True).stdout


def unprefix(text: str) -> str:
    return re.sub(r"^from legacy\.", "from ", text, flags=re.M)


@pytest.mark.parametrize("path", MODULES)
def test_legacy_module_is_v1_except_imports(path):
    assert unprefix((ROOT / "legacy" / path).read_text()) == _v1(path).decode()


@pytest.mark.parametrize("path", TABLES)
def test_committed_v1_tables_unchanged(path):
    assert (ROOT / "legacy" / path).read_bytes() == _v1(path)


def test_unprefix_would_catch_a_logic_edit():
    """The comparison bites: a changed constant survives unprefixing and differs from v1."""
    edited = (ROOT / "legacy" / "config.py").read_text().replace("target_vol: float = 0.15", "target_vol: float = 0.10")
    assert unprefix(edited) != _v1("config.py").decode()
