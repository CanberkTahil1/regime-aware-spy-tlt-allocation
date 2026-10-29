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
