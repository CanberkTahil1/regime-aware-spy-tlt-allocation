# Ledger: expectations before code, results after

Status: `open` → `held` / `failed` / `not tested`, each closed with the command and the number that decided it.
`spec/prereg.yaml` does not exist yet (R1 writes it and hashes it here before any rung result).

## R0 — scaffold, licences, safety (expectations committed before any R0 code)

| ID | Expectation (band) | Source | Status |
|---|---|---|---|
| E0.1 | v1 characterization reproduces `results/tables/test_metrics.csv` (8 metrics × strategy/SPY = 16 numbers) on the cached `data/prices.csv` (blob 900f1dbf0cab27f32da7926aa6bca5ef3a5dee03, from 5ccc12c): max abs diff ≤ 1e-12 | BUILD_PROMPTS R0 pre-registered | open |
| E0.2 | `summary_metrics.csv` reproduces: selected parameters and strategy string exactly; every float equal after v1's own rounding (4 dp, turnover 2 dp) | D0.3 | open |
| E0.3 | `grid_search_results.csv` reproduces: 648 rows; parameter columns exact; float columns ≤ 1e-12 abs; argmax of selection_score's train-shortlist rule picks the summary row | D0.3 | open |
| E0.4 | `make test lint` green; v2 code imports no Yahoo/Cboe client (a `force_download=True` call fails with the exclusion message) | BUILD_PROMPTS R0 exit; D0.2 | open |
| E0.5 | perf: `make test` ≤ 60 s wall, peak RSS ≤ 1.5 GB (reports/perf.md) | performance contract | open |

Note (D0.1): importing `legacy.config` creates `legacy/data/` and `legacy/results/{plots,tables}/` (v1's
`config.validate()`); `/legacy/data/` is gitignored.

A miss is recorded here with its cause; the 1e-12 band is never widened (D0.3 amendment 4).
