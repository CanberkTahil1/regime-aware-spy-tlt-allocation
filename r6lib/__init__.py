"""R6: improvements suggested by R5 (spec/prereg_r6.yaml; owner O6.1: outside R5's lock). No R5-locked file is edited or
added: the locked engine modules under src/rspy/ are imported unchanged; the page module src/rspy/site.py (not locked)
carries the R6 section; the R6 make targets live in Makefile.r6 (owner O6.4). Every number is descriptive: development
"in-sample", test "disclosed reuse: ideas inspired by this window"; an R6 verdict promotes or demotes nothing."""

from __future__ import annotations

from functools import lru_cache

import yaml

from rspy import paths

SPEC = paths.ROOT / "spec" / "prereg_r6.yaml"


@lru_cache(maxsize=1)
def spec() -> dict:
    return yaml.safe_load(SPEC.read_text())


def data_dir():
    return paths.data_dir() / "r6"
