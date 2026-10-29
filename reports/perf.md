# Performance budgets (set before code) and measurements

Charter targets: data build ≤ 30 s; one rung full evaluation ≤ 10 s; whole ladder + zoo ≤ 5 min; peak RSS ≤ 1.5 GB.
Measured on the owner's Mac (Apple silicon), `/usr/bin/time -l` for peak RSS.

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

Note: the grid test is marked `slow` (runtime recorded above, D0.3 amendment 5) and stays in `make test`.
