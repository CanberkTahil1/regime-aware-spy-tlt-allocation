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
