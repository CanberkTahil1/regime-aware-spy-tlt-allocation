# Decisions in plain language

## R0

- **D0.1 (advisor): v1 moves into a `legacy` folder that is a proper Python package.** Only the import lines change
  (`from config` becomes `from legacy.config`). That stops v1's generic file names (`config`, `data`, `utils`) from
  clashing with the new code. The move and the import edits are separate commits, so anyone can check that nothing
  else changed.
- **D0.2 (advisor): no Yahoo client is installed.** v1 imports `yfinance` but only uses it when its cached file is
  missing. The tests swap in a fake `yfinance` that refuses every call, so v1 can never quietly re-download.
- **D0.3 (advisor): the tests pin everything v1 committed** (headline test metrics, the one-row summary, and all 648
  grid rows) against the exact data file v1 used, checked by hash. A missing file is a red test, not a silent skip.
- **D0.4 (advisor, after a miss): the test suite used too much memory in total.** I first checked one process
  (185 MB) but the budget is for the whole run; with 16 parallel workers it peaks near 2 GB. Recorded as a failed
  expectation, then capped the workers at 4 (same speed, ~0.7 GB) instead of redefining the budget.
- **O0.1 (owner): the Yahoo/Cboe price file is no longer tracked by git.** It stays on disk for the v1 tests. It is
  still in the repo's history; you will rewrite that yourself before the next push.
