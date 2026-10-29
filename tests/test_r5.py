"""R5 (D5.1–D5.5): the freeze lock and run-once guard on a scratch git repo, the dry run's and the runner's refusals,
the test-window matching invariant, the registered family / headline rule, the DSR trial variance and the vol-zoo pick
guard. The full pipeline (build + identity + evaluation) is exercised by `make dry-run` (synthetic) and asserted by
scripts/r5.py itself (development rows bit for bit)."""

import json
import math
import os
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from rspy import evaluate as ev
from rspy import freeze, paths, testwin

ROOT = paths.ROOT


def _git(root, *a):
    subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True)


@pytest.fixture
def scratch(tmp_path):
    """A copy of the locked tree in a fresh git repo, with a small synthetic data directory."""
    root = tmp_path / "repo"
    for f in (*freeze.SPEC, *freeze.engine_files(ROOT)):
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / f, root / f)
    data = tmp_path / "data"
    data.mkdir()
    testwin.synthetic_panel(0, start="2018-01-02").to_parquet(data / "panel.parquet")
    (data / "build.json").write_text(json.dumps({"key": {"raw": {"x": "1"}, "code": {}, "rules": "r"}}))
    _git(root, "init", "-q")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    freeze.write(root, data)
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "lock")
    return root, data


def test_lock_covers_specs_engine_and_data(scratch):
    root, data = scratch
    lock = freeze.read(root)
    for f in ("spec/prereg.yaml", "spec/rules.yaml", "spec/quantkit_pin.json", "uv.lock", "Makefile",
              "src/rspy/testwin.py", "src/rspy/robust.py", "src/rspy/accounting.py", "tests/legacy_support.py"):
        assert f in lock["files"], f
    assert not set(freeze.NOT_ENGINE) & set(lock["files"])
    assert any(f.startswith("legacy/") for f in lock["files"])
    tw = lock["data"]["test_window"]
    assert (tw["first"], tw["last"]) == ("2020-01-02", "2026-09-30")
    assert freeze.verify(root, data) == []
    with pytest.raises(freeze.GuardError, match="re-freeze"):
        freeze.write(root, data)


def test_verify_catches_engine_spec_and_data_changes(scratch):
    root, data = scratch
    f = root / "src/rspy/rungs.py"
    f.write_text(f.read_text() + "\n# planted\n")
    probs = freeze.verify(root, data)
    assert any("locked file changed: src/rspy/rungs.py" in p for p in probs)
    assert any("uncommitted change" in p and "rungs.py" in p for p in probs)
    (root / "src/rspy/new_engine.py").write_text("x = 1\n")
    assert any("not in the lock: src/rspy/new_engine.py" in p for p in freeze.verify(root, data, git=False))
    p = pd.read_parquet(data / "panel.parquet")
    p.iloc[-1, 0] += 1e-9
    p.to_parquet(data / "panel.parquet")
    assert any("panel_sha256" in q for q in freeze.verify(root, data, git=False))


def test_verify_catches_a_later_kf_month(scratch):
    root, data = scratch
    p = pd.read_parquet(data / "panel.parquet")
    extra = testwin.synthetic_panel(1, start="2026-10-01", end="2026-10-30")
    pd.concat([p, extra]).to_parquet(data / "panel.parquet")
    probs = freeze.verify(root, data, git=False)
    assert any("last_session" in q for q in probs) and any("panel_sha256" in q for q in probs)


def test_guard_needs_env_and_refuses_a_second_run(scratch, monkeypatch):
    root, data = scratch
    monkeypatch.delenv(freeze.ENV, raising=False)
    with pytest.raises(freeze.GuardError, match="RSPY_TEST_RUN"):
        freeze.guard(root, data)
    monkeypatch.setenv(freeze.ENV, freeze.ENV_VALUE)
    freeze.guard(root, data)  # every condition holds
    rec = freeze.start_record(root)
    assert rec["status"] == "started" and rec["lock_sha256"] == paths.sha256(root / freeze.LOCK)
    with pytest.raises(freeze.GuardError, match="has been run"):
        freeze.guard(root, data)
    with pytest.raises(FileExistsError):
        freeze.start_record(root)
    done = freeze.complete_record({"reports/r5/x.csv": "h"}, {"total": 1.0}, root)
    assert done["status"] == "completed"
    with pytest.raises(freeze.GuardError, match="not 'started'"):
        freeze.complete_record({}, {}, root)


def test_loaded_unlocked_flags_an_unlocked_repo_module():
    lock = {"files": {}}
    assert "src/rspy/testwin.py" in freeze.loaded_unlocked(lock)
    full = {"files": {f: "h" for f in freeze.engine_files(ROOT)}}
    assert "src/rspy/testwin.py" not in freeze.loaded_unlocked(full)


def _script(*args, env):
    e = {k: v for k, v in os.environ.items() if k != freeze.ENV} | env
    return subprocess.run([sys.executable, str(ROOT / "scripts/r5.py"), *args], capture_output=True, text=True,
                          env=e, cwd=ROOT, timeout=120)


def test_dry_run_refuses_beside_the_real_run():
    r = _script("--mode", "dry", env={freeze.ENV: freeze.ENV_VALUE})
    assert r.returncode != 0 and "dry run refused" in r.stderr


def test_real_run_refuses_without_the_env_and_writes_nothing():
    before = (ROOT / freeze.RECORD).exists()
    r = _script("--mode", "run", env={})
    assert r.returncode != 0 and "test run refused" in r.stderr
    assert (ROOT / freeze.RECORD).exists() == before


def test_matched_reference_has_the_childs_scored_window_vol():
    """D5.2: below 1× (no financing) the rescaled reference's excess vol equals the child's exactly; above 1× the
    financing (mmy + 25 bp on k − 1, a varying rate) moves it by a small amount, reported in facts.json."""
    rng = np.random.default_rng(3)
    T = 1695
    c = np.full(T, 0.0001) + rng.normal(0, 1e-6, T)
    rate, dt = np.full(T, 0.04) + rng.normal(0, 1e-3, T), np.full(T, 1 / 360)
    x = c + rng.normal(0, 0.006, T)
    for scale in (0.012, 0.003):  # k < 1 and k > 1
        y = c + rng.normal(0, scale, T)
        vx = float(np.std(x - c, ddof=1) * math.sqrt(252))
        ym = ev.rescale(y, c, vx, rate, dt, spread_bp=25.0)
        err = abs(float(np.std(ym - c, ddof=1) * math.sqrt(252)) - vx)
        assert err <= (1e-10 if scale > 0.006 else 1e-3), (scale, err)


def test_family_is_the_registered_24_rows():
    f = testwin.family_rows()
    assert len(f) == 24 and len(set(f)) == 24
    assert ("L4", "L3", "parent") in f and ("L8", "line", "line") in f and ("L3", "L2", "rung") in f
    assert all(c in testwin.OFFICIAL for c, _, _ in f)


def test_headline_needs_effect_and_holm():
    fam = pd.DataFrame({"child": ["L3", "L4", "L5"], "reference": ["L2", "L2", "line"],
                        "dsharpe": [0.30, 0.04, 0.20], "p_one_sided": [0.001, 0.0001, 0.01],
                        "holm_p": [0.02, 0.001, 0.2]})
    h = testwin.headline(fam)
    assert h["beat plain vol-targeted SPY (L2)"]["answer"] == "yes"
    assert h["beat plain vol-targeted SPY (L2)"]["holm_hits"] == ["L3"]  # L4: p tiny but effect < 0.05
    assert h["beat SPY + T-bills at matched risk (line)"]["answer"] == "not shown in the test window"
    assert h["beat SPY + T-bills at matched risk (line)"]["raw_flags"] == ["L5"]
    assert h["beat 60/40 (L3)"]["answer"] == "not shown in the test window"


def test_trial_variance_is_never_below_the_null():
    assert testwin.trial_var(5.38e-5, 1695) == (1 / 1694, "null 1/(T-1)")
    assert testwin.trial_var(1e-2, 1695) == (1e-2, "V_dev (development pool)")
    x = np.random.default_rng(0).normal(0.0004, 0.006, 1695)
    rows = testwin.dsr_rows(x, 5, 751, 1e-2, 3)
    assert abs(rows[1]["trial_var"] - 1e-2) < 1e-15 and rows[1]["trial_var_source"].startswith("V_dev")
    rows = testwin.dsr_rows(x, 5, 751, 5.38e-5, 3)
    assert abs(rows[0]["trial_var"] - 1 / 1694) < 1e-15 and abs(rows[1]["trial_var"] - 1 / 1694) < 1e-15


def test_require_picks_refuses_a_missing_year():
    picks = {y: {"pick": "ewma_slow"} for y in range(1989, 2026)}
    testwin.require_picks(picks, 2020, 2026)
    del picks[2022]
    with pytest.raises(RuntimeError, match=r"\[2023\]"):
        testwin.require_picks(picks, 2020, 2026)


def test_synthetic_panel_is_seeded_and_shaped_like_the_real_one():
    a, b = testwin.synthetic_panel(0, start="2019-01-02"), testwin.synthetic_panel(0, start="2019-01-02")
    pd.testing.assert_frame_equal(a, b)
    assert set(a.columns) == {"hi20", "tlt25", "tlt10", "tlt20", "tlt30", "bill", "mmy", "dt", "disc_used"}
    assert a.notna().all().all() and a.index[-1] == pd.Timestamp("2026-09-30")


def test_dev_identity_flags_a_moved_development_row():
    """D5.1 amendment 3: one changed development row in one book turns that book's check False."""
    from types import SimpleNamespace as NS

    idx = pd.bdate_range("2019-12-25", "2020-01-08")
    n = 4  # rows <= 2019-12-31 (the development-only build's length)
    rng = np.random.default_rng(1)
    full = {r: NS(net=rng.normal(size=len(idx)), held=rng.normal(size=(len(idx), 2))) for r in ("L0", "L5")}
    picks = {y: {"pick": "ewma_slow"} for y in range(1989, 2026)}
    B = {"books": {r: {"1x": b} for r, b in full.items()}, "core": NS(inp=NS(index=idx)), "picks": picks}
    dev = {"idx": idx[:n], "net": {r: b.net[:n].copy() for r, b in full.items()},
           "held": {r: b.held[:n].copy() for r, b in full.items()},
           "picks": {y: v for y, v in picks.items() if y <= 2018}}
    assert all(testwin.dev_identity(B, dev).values())
    dev["net"]["L5"][2] += 1e-16
    dev["picks"][2007] = {"pick": "gjr_garch_t"}
    out = testwin.dev_identity(B, dev)
    assert out["L5_net"] is False and out["L0_net"] is True and out["picks_1989_2018"] is False
