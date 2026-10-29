"""R6: improvements suggested by R5 (spec/prereg_r6.yaml; owner O6.1: outside R5's lock, so nothing under src/rspy/ is
edited or added). Every number is descriptive: development "in-sample", test "disclosed reuse: ideas inspired by this
window"; an R6 verdict promotes or demotes nothing."""

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
