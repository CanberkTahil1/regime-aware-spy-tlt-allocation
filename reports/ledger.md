# Ledger: expectations before code, results after

Status: `open` → `held` / `failed` / `not tested`, each closed with the command and the number that decided it.
`spec/prereg.yaml` does not exist yet (R1 writes it and hashes it here before any rung result).

## R0 — scaffold, licences, safety (expectations committed before any R0 code)

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E0.1 | v1 characterization reproduces `results/tables/test_metrics.csv` (8 metrics × strategy/SPY = 16 numbers) on the cached `data/prices.csv` (blob 900f1dbf0cab27f32da7926aa6bca5ef3a5dee03, from 5ccc12c): max abs diff ≤ 1e-12 | BUILD_PROMPTS R0 pre-registered | **held** — `make legacy`: max abs diff 1.22e-15 (16 numbers) ≤ 1e-12; also from v1's own main() |
| E0.2 | `summary_metrics.csv` reproduces: selected parameters and strategy string exactly; every float equal after v1's own rounding (4 dp, turnover 2 dp) | D0.3 | **held** — v1 main() → summary_metrics.csv equal (byte-identical file); selection rule on the committed grid picks the summary params |
| E0.3 | `grid_search_results.csv` reproduces: 648 rows; parameter columns exact; float columns ≤ 1e-12 abs; argmax of selection_score's train-shortlist rule picks the summary row | D0.3 | **held** — 648 rows, params exact, float max abs diff 1.05e-14 ≤ 1e-12 (pandas 3.1.0 / numpy 2.5.4 vs v1's unrecorded versions) |
| E0.4 | `make test lint` green; v2 code imports no Yahoo/Cboe client (a `force_download=True` call fails with the exclusion message) | BUILD_PROMPTS R0 exit; D0.2 | **held** — `make test` 52 passed, `make lint` pass; `test_download_path_fails_loudly`; doctor: yfinance absent |
| E0.5 | perf: `make test` ≤ 60 s wall, peak RSS ≤ 1.5 GB (reports/perf.md) | performance contract | **held** — `make test` 8.3 s wall; max single-process RSS 185 MB (legacy run, no xdist) |

Note (D0.1): importing `legacy.config` creates `legacy/data/` and `legacy/results/{plots,tables}/` (v1's
`config.validate()`); `/legacy/data/` is gitignored.

A miss is recorded here with its cause; the 1e-12 band is never widened (D0.3 amendment 4).

Broken-input checks (2026-10-28): planting `COST_PER_UNIT * 1.0000001` in legacy/backtest.py fails
`test_legacy_module_is_v1_except_imports[backtest.py]`, `test_test_metrics_reproduce_from_committed_params` and
`test_v1_main_reproduces_all_three_tables`; restored from a copy (empty diff). Missing / edited data file → error naming
the blob (`test_data_guard_fails_on_missing_or_changed_file`).
