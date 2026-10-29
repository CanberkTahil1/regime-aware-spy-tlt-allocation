# Performance budgets (set before code) and measurements

Charter targets: data build ≤ 30 s; one rung full evaluation ≤ 10 s; whole ladder + zoo ≤ 5 min; peak RSS ≤ 1.5 GB.
Measured on the owner's Mac (Apple silicon, 16 cores). Peak RSS method from D0.4 on: `python scripts/rss_peak.py <cmd>`
(summed RSS of the whole process tree sampled every 0.1 s; an upper bound). Rows before D0.4 used `/usr/bin/time -l`,
which reports one process only and is not a valid measure of the "total" budget.

## R0 budgets

| Step | Time budget | Peak RSS budget | Complexity note |
|---|---|---|---|
| legacy test-period reproduction (selected params, 1 run) | ≤ 5 s | ≤ 500 MB | v1 pandas rolling ops, O(T·k) for k rolling features, T ≈ 5,400 days |
| legacy grid reproduction (648 configs × train + validation windows) | ≤ 60 s | ≤ 800 MB | 1,296 v1 runs, each O(T); v1 itself reported ~15 s per grid pass; not optimised (frozen code) |
| `make test` (whole suite, -n auto) | ≤ 60 s wall | ≤ 1.5 GB total | dominated by the grid test |
| `make lint` | ≤ 5 s | — | ruff |

## Measurements

| Date | Step | Wall | Peak RSS | Within budget |
|---|---|---|---|---|
| 2026-10-28 | legacy test-period reproduction | 0.03 s (call) | ≤ 185 MB (shared run) | yes (≤ 5 s) |
| 2026-10-28 | legacy grid reproduction (v1 main, 1,296 runs) | 6.8–7.3 s | 185 MB (single process) | yes (≤ 60 s, ≤ 800 MB) |
| 2026-10-28 | `make test` (52 tests, -n auto) | 8.3 s wall | max single process 158 MB as reported by `time -l` | yes (≤ 60 s) |
| 2026-10-28 | `make lint` | < 1 s | — | yes |
| 2026-10-28 | correction (D0.4): `make test` at `-n auto` (16 workers), rss_peak | 8.57 s | **1952 MB** summed (upper bound) | **no** (> 1.5 GB) |
| 2026-10-28 | `make test` after D0.4 (`-n auto --maxprocesses 4`), rss_peak | 8.14 s | 625 MB summed over 12 processes | yes |

Worker count vs memory (descriptive, rss_peak, pytest -q only): -n 16: 1952 MB / 8.57 s; -n 8: 1093 MB / 8.45 s;
-n 4: 665 MB / 8.31 s. Wall time is set by the ~7 s v1 grid test, so more workers buy nothing at R0.

Note: the grid test is marked `slow` (runtime recorded above, D0.3 amendment 5) and stays in `make test`.

## R1 budgets (charter targets) and measurements (rss_peak = summed tree RSS, upper bound)

| Date | Step | Budget | Wall | Peak RSS | Within | Complexity |
|---|---|---|---|---|---|---|
| 2026-10-28 | `make fetch` (download 3 files + build) | — | 2.4 s | — | — | network-bound |
| 2026-10-28 | `make data` build (26,338 sessions; 4 bond legs, bills) | ≤ 30 s | 1.9 s | — | yes | O(n·m·M) per leg (quantkit.bonds), n ≈ 16k curve days |
| 2026-10-28 | `make reconcile` (8 steps × 3 windows + QA) | ≤ 10 s | 1.4 s | 617 MB | yes | O(T·N) per step, numba walk |
| 2026-10-28 | `make test` (69 tests, -n auto, max 4) | ≤ 60 s, ≤ 1.5 GB | 9.4 s | 1,140 MB | yes | — |
| 2026-10-28 | `make report-site` | — | ~3 s | — | — | vl-convert SVG per chart × 2 themes |
| 2026-10-28 | `make test` after the R1 review fixes (71 tests) | ≤ 60 s, ≤ 1.5 GB | 11.6 s | 1,219 MB | yes (headroom shrinking: numba + quantkit imports per worker) | — |

## R2 budgets (set before the first `make ladder` run)

| Step | Time budget | Peak RSS budget | Complexity note |
|---|---|---|---|
| rung targets (L0–L5, L4b, L2-u) on 1986–2019 | ≤ 3 s | ≤ 600 MB | O(T) rolling σ; ERC 2×2 per month-end; L1/L2 via v1's pandas code |
| vol zoo, 2 series × 5 models, first run / cached | ≤ 30 s / ≤ 1 s | ≤ 800 MB | GJR/EGARCH refits every 21 days (≈ 400 fits per series); Parquet cache keyed by series + config + quantkit + code hashes |
| one rung full evaluation (4 books, line, LW 1,000 draws, 21 offsets) | ≤ 10 s | ≤ 600 MB | numba walk O(T·N) per book; LW O(draws·T) ≈ 0.2 s |
| promotion walk L1→L5 (prefix MCS + LW, 1,000 reps) | ≤ 30 s | ≤ 800 MB | MCS O(reps·T·k) per prefix |
| whole `make ladder` | ≤ 5 min | ≤ 1.5 GB | single process |

## R2 measurements

| Date | Step | Wall | Peak RSS | Within budget |
|---|---|---|---|---|
| 2026-10-28 | `make ladder`, first run | 29.6 s | **2,227 MB** summed | **no** (RSS; E2.11) |
| 2026-10-28 | `make ladder` after the E2.11 fix, forecast cache cleared | 28.2 s | 957 MB | yes |
| 2026-10-28 | `make ladder`, warm cache | 15.6 s | 914 MB | yes |
| 2026-10-28 | parts (facts.json timing_s, warm): targets + zoo selection 5.7 s; 56 books 1.5 s; metrics + 14 lines (LW 1,000) + walk 4.7 s; timing luck 3 rungs × 21 offsets 2.3 s | — | — | yes (per rung < 2 s ≤ 10 s) |
| 2026-10-28 | `make test` (94 tests, -n auto, 4 workers) | 9.3 s | — | yes |
| 2026-10-29 | `make ladder` with the post-hoc chain walk (2 chains) + vs-L1 table (7 LW), warm | 19.9 s | 911 MB | yes (E2.15) |
| 2026-10-29 | `make test` (98 tests, -n auto) | 8.7 s | — | yes |

## R3 budgets (set at the expectation commit, E3.14) and measurements

| Step | Budget | Measured | Within | Complexity |
|---|---|---|---|---|
| `make ladder` (R2 + R3), warm | ≤ 5 min, ≤ 1.5 GB | 62.9 s, 955 MB (rss_peak) | yes | — |
| `make ladder`, cold (.cache/r3 and .cache/volzoo cleared) | ≤ 5 min, ≤ 1.5 GB | 110.9 s, 937 MB | yes | HMM refits ≈ 21 s (now cached), min-CDaR LPs + its vol zoo ≈ 15 s |
| R3 part, warm (facts.json timing_s) | — | 40 s: targets 3.5, zoo 2.3, books 0.9, ablation 17.0, crisis + placebos 16.8 | yes | 20 ablation rows × (LW 1,000 + 2 dd_ratio_ci 1,000); 4 gates × 102 placebo books |
| one rung's evaluation (4 references) | ≤ 10 s | ≈ 3.4 s | yes | O(draws·T) per interval |
| `make test` (118 tests, -n auto) | ≤ 60 s | 10.9 s | yes | — |

## R4 budgets (set at the expectation commit, E4.17)

| Step | Budget | Complexity |
|---|---|---|
| overlay signals (v1 spread / Bollinger) | ≤ 2 s, ≤ 400 MB | v1's pandas rolling O(T) |
| GBM: features + 30 walk-forward LightGBM fits (200 trees, ≤ 8,600 rows × 8 features) | ≤ 30 s, ≤ 600 MB | O(fits · trees · rows · features) histogram GBM, threads 1 per fit |
| sensitivity books: 7 maturity × (L4 vol zoo + targets) + 20 band/calendar targets | ≤ 60 s cold, ≤ 10 s warm (vol zoo Parquet cache) | 7 extra vol-zoo series (GARCH refits) cached by series hash |
| v1 grid on permitted data (648 configs) | ≤ 90 s, ≤ 1.2 GB (process pool, 4 workers) | 648 × (v1 signals O(T) + numba book O(T·N)) |
| DSR (effective_trials, N ≈ 800, T ≈ 7,560) | ≤ 10 s, ≤ 300 MB | exact clustering O(N²) correlations |
| PBO (S = 16, 12,870 splits, N ≤ 60) | ≤ 5 s | block moment sums, chunked |
| robustness tables (costs, LOCO, decades, rolling, power, waterfall) on 10 rungs | ≤ 40 s | LW 1,000 draws per comparison |
| whole R4 part, warm | ≤ 150 s; `make ladder` total ≤ 5 min, ≤ 1.5 GB | — |

## R4 measurements (2026-10-29)

| Step | Budget | Measured | Within | Note |
|---|---|---|---|---|
| R4 part, first runs, v1 grid in 4 loky workers | ≤ 1.5 GB | **2,264 MB** summed, 8 processes (85 s) | **no** | each loky worker ≈ 500 MB (pandas, numba, v1's code) |
| v1 grid moved to the start, 4 / 2 workers | ≤ 1.5 GB | 2,364 / 1,775 MB summed | **no** | the pool, not the main process, dominates |
| v1 grid in-process (fix), grid cold | ≤ 150 s, ≤ 1.5 GB | 107 s, **1,076 MB** (2 processes) | yes | grid ≈ 31 s serial (≤ 90 s budget), then cached by panel + code hash |
| R4 part, warm (facts.json timing_s) | ≤ 150 s | 72 s: base 0.8, zoo + GBM 8.3, costs + waterfall 25.3, LOCO/decades/rolling/power 0.1, sensitivity 31.9, trial pool 4.5, DSR 0.7, PBO 0.1 | yes | 33 + 41 + 8 matched comparisons with LW 1,000 + 2 dd_ratio_ci |
| GBM (30 walk-forward fits, 8,213 rows × 8 features) | ≤ 30 s | ≈ 7 s inside the zoo step | yes | threads 1 |
| `make ladder` (R2 + R3 + R4 + figures), warm | ≤ 5 min, ≤ 1.5 GB | **145 s, 1,122 MB** (rss_peak) | yes | — |
| `make test` (134 tests, -n auto) | ≤ 60 s | 10.9 s | yes | — |

## R5 budgets (set at the expectation commit, E5.17) and measurements

| Step | Budget | Complexity | Measured (2026-10-29) | Within |
|---|---|---|---|---|
| `make dry-run` (synthetic panel, cold vol zoo: 3 extended + 3 development-only series) | ≤ 120 s, ≤ 1.5 GB | build O(T·N) per book + GARCH refits every 21 rows; evaluation O(draws·T_test) per matched row | **78.7 s, 889 MB** summed over 6 processes (rss_peak) | yes |
| `make dry-run`, warm | — | — | 9.2 s (build 2.2, identity 0.5, evaluate 6.6) | yes |
| `make test-run` (cold: 3 extended vol-zoo series; development-only rebuild cached from R4) | ≤ 120 s, ≤ 1.5 GB | as above | (after the run) | — |
| `make test` (147 tests) | ≤ 60 s | — | 10.6 s | yes |
| D5.8 test placebos (3 gates × 100 books over 1986–2026) | ≤ 20 s inside the run | 300 numba walks O(T·N) | dry run: evaluate 21 s incl. placebos (warm build) | yes |
| `make dry-run` after review M1 / D5.8 (new synthetic series: cold) | ≤ 120 s | — | 70.3 s | yes |
