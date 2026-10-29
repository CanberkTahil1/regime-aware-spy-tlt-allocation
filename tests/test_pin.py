"""Copied from naive-vs-optimal `tests/test_pin.py` @ b5f6278 (COPIED.md), renamed; the real-pin test re-targeted.

The quantkit content pin: changed or missing pinned files fail; new unpinned files only warn."""

import json
import os
import pathlib
from types import SimpleNamespace

from rspy import __main__, pin

_LOADED_FILES = pin.loaded_files


def _tree(tmp_path):
    root = tmp_path / "quantkit"
    (root / "src" / "quantkit").mkdir(parents=True)
    (root / "src" / "quantkit" / "stats.py").write_text("x = 1\n")
    (root / "pyproject.toml").write_text("[project]\nname='quantkit'\n")
    return root


def test_pin_roundtrip_clean(tmp_path):
    root, f = _tree(tmp_path), tmp_path / "pin.json"
    rec = pin.pin(root, f)
    assert set(rec["files"]) == {"src/quantkit/stats.py", "pyproject.toml"}
    assert pin.verify_pin(root, f) == []


def test_pin_detects_changed_missing(tmp_path):
    root, f = _tree(tmp_path), tmp_path / "pin.json"
    pin.pin(root, f)
    (root / "src" / "quantkit" / "stats.py").write_text("x = 2\n")
    assert pin.verify_pin(root, f) == ["changed: src/quantkit/stats.py"]
    (root / "pyproject.toml").unlink()
    assert "missing: pyproject.toml" in pin.verify_pin(root, f)


def test_new_unpinned_file_warns_not_fails(tmp_path):
    root, f = _tree(tmp_path), tmp_path / "pin.json"
    pin.pin(root, f)
    (root / "src" / "quantkit" / "alloc").mkdir()
    (root / "src" / "quantkit" / "alloc" / "new.py").write_text("")
    assert pin.verify_pin(root, f) == []
    assert pin.unpinned_files(root, f) == ["new: src/quantkit/alloc/new.py"]
    (root / "src" / "quantkit" / "stats.py").write_text("x = 2\n")  # a changed pinned file still fails
    assert pin.verify_pin(root, f) == ["changed: src/quantkit/stats.py"]


def test_missing_pin_file_is_a_problem(tmp_path):
    assert pin.verify_pin(_tree(tmp_path), tmp_path / "nope.json")[0].startswith("no pin")


def test_pin_ignores_pycache(tmp_path):
    root, f = _tree(tmp_path), tmp_path / "pin.json"
    (root / "src" / "quantkit" / "__pycache__").mkdir()
    (root / "src" / "quantkit" / "__pycache__" / "x.py").write_text("")
    assert "__pycache__" not in json.dumps(pin.pin(root, f))


# ---- loaded-module check (copied from bond-flows/resid-arb): only files the run actually loaded are compared
def _mods(root, *rels):
    return {f"quantkit.m{i}": SimpleNamespace(__file__=str(root / r)) for i, r in enumerate(rels)}


def test_loaded_files_filters_package_and_skips_fileless(tmp_path):
    root = _tree(tmp_path)
    mods = {
        "quantkit": SimpleNamespace(__file__=str(root / "src" / "quantkit" / "stats.py")),
        "quantkit.ns": SimpleNamespace(__file__=None),  # namespace package
        "quantkitx": SimpleNamespace(__file__=str(tmp_path / "other.py")),  # a different package with the same prefix
        "numpy": SimpleNamespace(__file__=str(tmp_path / "np.py")),
    }
    assert pin.loaded_files(mods) == [(root / "src" / "quantkit" / "stats.py").resolve()]


def test_changed_file_fails_only_when_loaded(tmp_path):
    root, f = _tree(tmp_path), tmp_path / "pin.json"
    (root / "src" / "quantkit" / "ml.py").write_text("y = 1\n")
    pin.pin(root, f)
    (root / "src" / "quantkit" / "ml.py").write_text("y = 2\n")  # changed, but this run never imported it
    loaded = pin.loaded_files(_mods(root, "src/quantkit/stats.py"))
    assert pin.verify_loaded(loaded, root, f) == []
    assert pin.verify_pin(root, f) == ["changed: src/quantkit/ml.py"]  # the full-tree check still sees it
    loaded = pin.loaded_files(_mods(root, "src/quantkit/stats.py", "src/quantkit/ml.py"))
    assert pin.verify_loaded(loaded, root, f) == ["loaded and changed: src/quantkit/ml.py"]


def test_loaded_unpinned_or_outside_tree_fails(tmp_path):
    root, f = _tree(tmp_path), tmp_path / "pin.json"
    pin.pin(root, f)
    (root / "src" / "quantkit" / "new.py").write_text("")
    (tmp_path / "elsewhere.py").write_text("")
    loaded = [root / "src" / "quantkit" / "new.py", tmp_path / "elsewhere.py"]
    probs = pin.verify_loaded(loaded, root, f)
    assert probs[0] == "loaded but not pinned: src/quantkit/new.py"
    assert probs[1].startswith("loaded outside the pinned tree:")
    assert pin.verify_loaded([], root, tmp_path / "nope.json")[0].startswith("no pin")


def test_run_wrapper_fails_on_a_changed_loaded_file(tmp_path, monkeypatch, capsys):
    root, f = _tree(tmp_path), tmp_path / "pin.json"
    pin.pin(root, f)
    monkeypatch.setattr(pin.paths, "PIN", f)
    monkeypatch.setenv("RSPY_QUANTKIT_ROOT", str(root))
    script = tmp_path / "job.py"
    script.write_text("import sys\nsys.exit(0)\n")
    fake = {"quantkit.stats": SimpleNamespace(__file__=str(root / "src" / "quantkit" / "stats.py"))}
    monkeypatch.setattr(pin, "loaded_files", lambda modules=None, package="quantkit": _LOADED_FILES(fake))
    assert __main__.run(str(script), []) == 0
    (root / "src" / "quantkit" / "stats.py").write_text("x = 3\n")
    assert __main__.run(str(script), []) == 1
    assert "loaded and changed: src/quantkit/stats.py" in capsys.readouterr().out
    script.write_text("import sys\nsys.exit(3)\n")  # the script's own failure is kept when the pin is clean
    (root / "src" / "quantkit" / "stats.py").write_text("x = 1\n")
    assert __main__.run(str(script), []) == 3


def test_numba_cache_stays_out_of_quantkit():
    """Numba ignores PYTHONPYCACHEPREFIX; quantkit's @njit(cache=True) would probe/write ../quantkit/**/__pycache__
    (bond-flows review P6 F3). NUMBA_CACHE_DIR must point under this repo's .cache before numba is imported."""
    import numba

    want = pathlib.Path(__file__).resolve().parents[1] / ".cache" / "numba"
    assert os.environ.get("NUMBA_CACHE_DIR") == str(want)
    assert pathlib.Path(numba.config.CACHE_DIR) == want


def test_run_wrapper_keeps_caches_in_repo_without_make(tmp_path):
    """`python -m rspy run` outside make (no PYTHONPYCACHEPREFIX / NUMBA_CACHE_DIR in the environment) must still
    send bytecode and numba caches under this repo's .cache (bond-flows review P5 M5, P6 F3)."""
    import subprocess
    import sys

    repo = pathlib.Path(__file__).resolve().parents[1]
    script = tmp_path / "probe.py"
    script.write_text(
        "import os, sys, numba\n"
        "print(sys.pycache_prefix)\n"
        "print(os.environ['PYTHONPYCACHEPREFIX'])\n"
        "print(numba.config.CACHE_DIR)\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPYCACHEPREFIX", "NUMBA_CACHE_DIR")}
    out = subprocess.run(
        [sys.executable, "-m", "rspy", "run", str(script)], cwd=tmp_path, env=env, capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    lines = out.stdout.splitlines()
    assert lines[:3] == [str(repo / ".cache" / "pycache")] * 2 + [str(repo / ".cache" / "numba")]


# ---- install source (G0.6): quantkit must be a non-editable install of the pinned tag and commit
def test_install_problems_bite():
    good = {"url": "file:///x/quantkit", "vcs_info": {"vcs": "git", "commit_id": "abc", "requested_revision": "v0.18"}}
    assert pin.install_problems(good, "abc", "v0.18") == []
    assert "missing" in pin.install_problems(None, "abc", "v0.18")[0]
    editable = {"url": "file:///x/quantkit", "dir_info": {"editable": True}}
    assert "editable" in pin.install_problems(editable, "abc", "v0.18")[0]
    assert "path/archive" in pin.install_problems({"url": "file:///x", "dir_info": {}}, "abc", "v0.18")[0]
    assert any("revision v0.17" in p for p in pin.install_problems(
        {"vcs_info": {"commit_id": "abc", "requested_revision": "v0.17"}}, "abc", "v0.18"))
    assert any("commit def" in p for p in pin.install_problems(
        {"vcs_info": {"commit_id": "def", "requested_revision": "v0.18"}}, "abc", "v0.18"))


def test_real_pin_is_v0191_and_clean():
    """Charter: quantkit pinned non-editable at v0.19.1."""
    meta = json.loads(pin.paths.PIN.read_text())
    assert meta["quantkit_tag_at_pin"] == "v0.19.1"
    assert meta["quantkit_head_at_pin"] == "d68e3745d724ab31c5ce168b92a1336a369cdfa0"
    assert pin.verify_pin() == []


def test_pin_env_override_ignored_outside_pytest(tmp_path):
    """P0 review MINOR: RSPY_PIN / RSPY_QUANTKIT_ROOT cannot repoint the pin check in a make run (no pytest loaded)."""
    import subprocess
    import sys

    env = {**os.environ, "RSPY_PIN": str(tmp_path / "fake.json"), "RSPY_QUANTKIT_ROOT": str(tmp_path)}
    code = "from rspy import paths; print(paths.PIN); print(paths.quantkit_root())"
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout
    assert str(tmp_path) not in out


def test_nvo_run_shows_a_refusal_reason(tmp_path, capsys):
    """A script's sys.exit("refused: …") keeps exit code 1 and its reason reaches stderr (D2.9 re-run guard)."""
    from rspy import __main__ as cli

    f = tmp_path / "s.py"
    f.write_text('import sys\nsys.exit("refused: already ran")\n')
    assert cli.run(str(f), []) == 1
    assert "refused: already ran" in capsys.readouterr().err
