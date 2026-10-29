"""Makefile contract: pipefail; every command through `uv run --frozen --no-sync`; caches kept in-repo; the DAG
targets; unbuilt targets refuse. Adapted from naive-vs-optimal `tests/test_makefile.py` @ b5f6278 (← resid-book @ 9a1e939;
COPIED.md): this charter's DAG targets."""

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
MK = (ROOT / "Makefile").read_text()


def test_pipeline_failure_fails_make(tmp_path):
    mk = tmp_path / "Makefile"
    head = [ln for ln in MK.splitlines() if ln.startswith(("SHELL", ".SHELLFLAGS"))]
    mk.write_text("\n".join(head) + "\nt:\n\tfalse | tee /dev/null | tail -1\n")
    assert subprocess.run(["make", "-f", str(mk), "t"], capture_output=True).returncode != 0


def test_required_targets_exist():
    targets = set(re.findall(r"^([a-z][a-z-]*):", MK, flags=re.M))
    assert {"help", "doctor", "test", "test-nolegacy", "lint", "legacy", "fetch", "data", "reconcile", "ladder",
            "report-site", "report-site-local", "all", "pin", "verify-pin"} <= targets


def test_every_recipe_runs_through_uv_frozen_no_sync():
    assert "UV := uv run --frozen --no-sync" in MK
    for line in MK.splitlines():
        if not line.startswith("\t"):
            continue
        cmd = line.strip().lstrip("@")
        if cmd.startswith(("echo", "mkdir")):
            continue
        assert cmd.startswith(("$(PY)", "$(RUN)", "$(UV)")), line
        assert not re.search(r"(&&|;|\|)\s*(python3?|pytest|ruff|uv run(?! --frozen --no-sync))\b", cmd), line


def test_caches_exported_in_repo():
    assert "export PYTHONPYCACHEPREFIX := $(CURDIR)/.cache/pycache" in MK
    assert "export NUMBA_CACHE_DIR := $(CURDIR)/.cache/numba" in MK


def test_no_stub_left_and_ladder_draws_its_figures():
    """R0-R1 kept unbuilt targets as refusing stubs; R2 built the last one (ladder). No script may still be a stub, and
    `make ladder` chains its statistics figures (charter "Charts every phase")."""
    assert not [f.name for f in (ROOT / "scripts").glob("*.py") if "not built yet" in f.read_text()]
    recipe = MK.split("\nladder: ")[1].split("\nreport-site:")[0]
    assert "scripts/ladder.py" in recipe and "scripts/r2_figures.py" in recipe


def test_test_target_runs_legacy_and_nolegacy_deselects_explicitly():
    """D0.3: `make test` does not deselect the v1 characterization; only test-nolegacy does, by name."""
    test_recipe = MK.split("\ntest: ")[1].split("\n")[1]
    assert "-m" not in test_recipe.split("pytest")[1].split("2>&1")[0].split()  # no marker deselect token
    assert '-m "not legacy"' in MK.split("\ntest-nolegacy: ")[1].split("\n")[1]
