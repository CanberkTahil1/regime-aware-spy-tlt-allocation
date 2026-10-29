"""R0 characterization: frozen v1 (`legacy/`) reproduces its committed tables on its own cached data (E0.1-E0.4).

Two layers so a failure says where it is:
- fast: v1's committed parameters -> v1's test-period run -> test_metrics.csv (pre-registered, <= 1e-12) and the
  summary's test columns;
- full: v1's own `main()` (648-config grid on train + validation, selection, test, save) with every output redirected to
  tmp_path, compared with all three committed tables (D0.3). The committed tables are never written.
CSV floats: pandas' default parser must be round-trip exact (test_csv_parser_is_round_trip), so 1e-12 means 1e-12.
"""

from __future__ import annotations

import csv
import importlib

import numpy as np
import pandas as pd
import pytest

from tests.legacy_support import EXCLUDED, V1_TABLES, check_v1_data

pytestmark = pytest.mark.legacy
TOL = 1e-12  # pre-registered (ledger E0.1, E0.3); never widened
PARAMS = ["z", "th", "sw", "sth", "ddw", "ddt", "cw"]


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(V1_TABLES / name)


@pytest.fixture
def v1(no_yahoo, monkeypatch, tmp_path):
    """legacy.run with v1's data path pointed at the hash-checked cached file and every output sent to tmp_path."""
    monkeypatch.setenv("MPLBACKEND", "Agg")
    try:
        data_path = check_v1_data()
    except (FileNotFoundError, ValueError) as e:
        pytest.fail(str(e))  # D0.3: fail, never skip
    run = importlib.import_module("legacy.run")
    data = importlib.import_module("legacy.data")
    monkeypatch.setattr(data, "DATA_PATH", data_path)
    out = {
        "GRID_SEARCH_RESULTS_FILE": tmp_path / "grid_search_results.csv",
        "SUMMARY_METRICS_FILE": tmp_path / "summary_metrics.csv",
        "TEST_METRICS_FILE": tmp_path / "test_metrics.csv",
        "PLOT_FILENAME": tmp_path / "strategy_vs_spy.png",
    }
    for k, v in out.items():
        monkeypatch.setattr(run, k, v)
    return run, out


def _summary_params() -> pd.Series:
    s = _read("summary_metrics.csv").iloc[0]
    keys = ["z_window", "threshold", "slow_window", "slow_threshold", "dd_window", "dd_threshold", "crash_weight"]
    return pd.Series({p: s[k] for p, k in zip(PARAMS, keys, strict=True)})


def _assert_metrics_close(got: pd.DataFrame, want: pd.DataFrame) -> float:
    assert list(got["Metric"]) == list(want["Metric"])
    assert list(got.columns) == list(want.columns)
    diff = np.abs(got[["Strategy", "SPY Benchmark"]].to_numpy() - want[["Strategy", "SPY Benchmark"]].to_numpy())
    assert diff.max() <= TOL, f"max abs diff {diff.max():.3e} > {TOL}"
    return float(diff.max())


def test_test_metrics_reproduce_from_committed_params(v1):
    """E0.1 (pre-registered): 8 metrics x strategy/SPY, max abs diff <= 1e-12."""
    run, _ = v1
    prices, returns = run.prepare_data(start=run.START_DATE, force_download=False)
    context_prices = prices.loc[returns.index]
    *_, test_returns = run.split_data(prices, returns, run.TRAIN_END_DATE, run.VALIDATION_END_DATE)
    test_start = returns.index[returns.index > pd.Timestamp(run.VALIDATION_END_DATE)][0]
    perf, strat, crisis, turnover = run.run_final_test(
        run.build_strategy_from_params(_summary_params()), context_prices, returns, evaluation_start=test_start
    )
    s, b = run.compute_detailed_metrics(strat), run.compute_detailed_metrics(test_returns["SPY"])
    got = pd.DataFrame({"Metric": list(s), "Strategy": list(s.values()), "SPY Benchmark": [b[k] for k in s]})
    _assert_metrics_close(got, _read("test_metrics.csv"))
    summ = _read("summary_metrics.csv").iloc[0]  # the summary's test columns, after v1's own rounding (E0.2)
    assert round(perf["sharpe"], 4) == summ["test_sharpe"]
    assert round(perf["annual_return"], 4) == summ["test_annual_return"]
    assert round(perf["volatility"], 4) == summ["test_volatility"]
    assert round(perf["max_drawdown"], 4) == summ["test_max_drawdown"]
    assert round(crisis, 4) == summ["test_crisis_return"]
    assert round(turnover, 2) == summ["turnover"]


def test_v1_selection_rule_picks_the_summary_row():
    """E0.3 (cheap half): v1's own selection rule on the committed grid picks the committed parameters."""
    from legacy.run import _select_robust_parameters  # importing legacy.config needs no data

    best = _select_robust_parameters(_read("grid_search_results.csv"))
    assert best[PARAMS].tolist() == _summary_params().tolist()


@pytest.mark.slow
def test_v1_main_reproduces_all_three_tables(v1):
    """E0.1-E0.3 end to end: v1's main() -> grid (648 rows), summary and test metrics, all against the committed files."""
    run, out = v1
    run.main()
    grid, want = pd.read_csv(out["GRID_SEARCH_RESULTS_FILE"]), _read("grid_search_results.csv")
    assert len(grid) == len(want) == 648
    assert list(grid.columns) == list(want.columns)
    pd.testing.assert_frame_equal(grid[PARAMS], want[PARAMS], check_exact=True)
    floats = [c for c in want.columns if c not in PARAMS]
    gdiff = np.abs(grid[floats].to_numpy() - want[floats].to_numpy())
    assert gdiff.max() <= TOL, f"grid max abs diff {gdiff.max():.3e}"
    got_s = pd.read_csv(out["SUMMARY_METRICS_FILE"])
    pd.testing.assert_frame_equal(got_s, _read("summary_metrics.csv"), check_exact=True)
    _assert_metrics_close(pd.read_csv(out["TEST_METRICS_FILE"]), _read("test_metrics.csv"))
    assert out["PLOT_FILENAME"].is_file()


def test_download_path_fails_loudly(v1):
    """E0.4 / D0.2: a forced download reaches the stub and fails with the exclusion message (no Yahoo path survives)."""
    run, _ = v1
    data = importlib.import_module("legacy.data")
    with pytest.raises(RuntimeError, match="excluded by the charter"):
        data.load_data(force_download=True)
    assert "Yahoo" in EXCLUDED


def test_data_guard_fails_on_missing_or_changed_file(tmp_path):
    """D0.3: a missing or edited cached file is an error naming the path and the blob, never a skip."""
    with pytest.raises(FileNotFoundError, match="900f1dbf"):
        check_v1_data(tmp_path / "prices.csv")
    f = tmp_path / "prices.csv"
    f.write_bytes(b"Date,SPY\n")
    with pytest.raises(ValueError, match="changed"):
        check_v1_data(f)
    assert check_v1_data().name == "prices.csv"  # the real local copy matches 5ccc12c


def test_csv_parser_is_round_trip():
    """pandas >= 3 deprecates float_precision; its default parse must equal Python's float() on every committed value."""
    for name in ("test_metrics.csv", "grid_search_results.csv"):
        with open(V1_TABLES / name, newline="") as fh:
            rows = list(csv.reader(fh))
        text = np.array([[float(x) for x in r[1:] if x] if name == "test_metrics.csv" else [float(x) for x in r] for r in rows[1:]])
        df = _read(name)
        got = df.iloc[:, 1:].to_numpy(dtype=float) if name == "test_metrics.csv" else df.to_numpy(dtype=float)
        assert np.array_equal(got, text), name
