"""Repository paths. Data lives under $RSPY_DATA (default ./data), never in git.
Adapted from naive-vs-optimal `src/nvo/paths.py` @ b5f6278 (← resid-book @ 9a1e939; COPIED.md): seal, freeze and spec
accessors dropped; R1 adds rules()/prereg() and their hashes."""

from __future__ import annotations

import hashlib
import os
import pathlib
import sys
from functools import lru_cache

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _test_env(name: str) -> str | None:
    """Overrides that could repoint the pin check are honoured only inside pytest."""
    return os.environ.get(name) if "pytest" in sys.modules else None


PIN = pathlib.Path(_test_env("RSPY_PIN") or ROOT / "spec" / "quantkit_pin.json")  # env: planted-change tests only
PREREG = ROOT / "spec" / "prereg.yaml"
RULES = ROOT / "spec" / "rules.yaml"
REPORTS = ROOT / "reports"
LOGS = ROOT / "logs"
GITHUB = ROOT.parent


def data_dir() -> pathlib.Path:
    return pathlib.Path(os.environ.get("RSPY_DATA", ROOT / "data"))


def quantkit_root() -> pathlib.Path:
    """Directory that holds the INSTALLED quantkit package (site-packages): the code every run imports. quantkit is a
    non-editable install of git tag v0.19.1, so edits in ../quantkit never reach here."""
    env = _test_env("RSPY_QUANTKIT_ROOT")
    if env:
        return pathlib.Path(env).resolve()
    import importlib.util

    spec_ = importlib.util.find_spec("quantkit")  # locates without importing
    if spec_ is None or spec_.origin is None:
        return ROOT / ".venv" / "missing-quantkit"
    return pathlib.Path(spec_.origin).resolve().parents[1]


def sibling(name: str) -> pathlib.Path:
    """A read-only sibling repo under ~/github (CLAUDE.md)."""
    return (GITHUB / name).resolve()


@lru_cache(maxsize=1)
def rules() -> dict:
    return yaml.safe_load(RULES.read_text())


@lru_cache(maxsize=1)
def prereg() -> dict:
    return yaml.safe_load(PREREG.read_text())


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
