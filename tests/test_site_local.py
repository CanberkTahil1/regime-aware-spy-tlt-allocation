"""Owner O1.1 (as naive-vs-optimal O4.2 @ 7d48e5b, COPIED.md): the local chart outputs are gitignored and refused by the
pre-commit hook; no committed file traces a series; the rolling Sharpe matches a plain loop; crisis panels rebase to 1."""

import subprocess

import numpy as np
import pandas as pd

from rspy import paths, site_local

LOCAL = ("reports/site_local/index.html", "reports/site_local/svg/equity-light.svg",
         "reports/figures_local/R1/growth_and_drawdown.png", "reports/figures_local/R1/exposure_l1.svg",
         "reports/figures_local/R2/anything.png")
CURVES = ("growth_and_drawdown", "rolling_5y_excess_sharpe", "crisis_small_multiples", "exposure_l1")


def test_local_outputs_are_gitignored():
    for rel in LOCAL:
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=paths.ROOT)
        assert r.returncode == 0, f"{rel} is not gitignored (owner O1.1)"


def test_precommit_refuses_local_outputs():
    hook = (paths.ROOT / ".githooks" / "pre-commit").read_text()
    assert "reports/site_local/*" in hook and "reports/figures_local/*" in hook


def test_no_curve_figure_is_tracked():
    tracked = subprocess.run(["git", "ls-files", "reports"], cwd=paths.ROOT, capture_output=True, text=True).stdout
    assert not [f for f in tracked.splitlines() if any(c in f for c in CURVES)]
    assert not [f for f in tracked.splitlines() if f.startswith(("reports/site_local/", "reports/figures_local/"))]


def test_rolling_sharpe_matches_loop():
    idx = pd.bdate_range("2000-01-03", periods=1400)
    rng = np.random.default_rng(0)
    r, b = pd.Series(rng.normal(4e-4, 0.01, 1400), idx), pd.Series(rng.uniform(0, 2e-4, 1400), idx)
    s = site_local.rolling_sharpe(r, b, 1260)
    assert s.index[0] == idx[1259] and len(s) == 141
    for t in (1259, 1300, 1399):
        x = (r - b).to_numpy()[t - 1259:t + 1]
        assert abs(s.loc[idx[t]] - x.mean() / x.std(ddof=1) * np.sqrt(252)) <= 1e-12


def test_rebased_starts_with_the_first_return():
    df = pd.DataFrame({"a": [0.01] * 5}, index=pd.bdate_range("2020-02-03", periods=5))
    w = site_local.rebased(df)["a"].to_numpy()
    assert np.allclose(w, 1.01 ** np.arange(1, 6))
