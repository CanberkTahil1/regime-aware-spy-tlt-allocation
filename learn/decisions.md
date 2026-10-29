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

## R1

- **D1.1 (advisor): cash is the Fed's 3-month T-bill**, converted from its discount quote and lagged a day. Borrowing is
  charged at the bill's (slightly higher) money-market yield plus 25 bp, so leverage is never cheaper than cash.
- **D1.2 (advisor): the TLT stand-in is a 25-year Treasury rebuilt every day from the Fed's fitted curve**, exactly as
  the sibling repo validated it (coupon from the fitted curve, not the published one; that detail moves daily returns).
- **D1.3 (advisor): one accounting function for everything**: decide at today's close, trade at tomorrow's close, pay
  costs on what you actually trade (including drift and vol-scaling), earn bills on cash, pay bills + 25 bp on leverage,
  quote Sharpe on returns above bills.
- **D1.4 (advisor): the v1 → v2 bridge goes one fix at a time** in a fixed order, and swaps VIX out while v1 is still on
  its own data, so no row mixes excluded and permitted data. The last row is v1 on the new data (L1).
- **D1.5 (advisor): VIX is replaced by 20-day realised volatility**, the same substitute v1 already used elsewhere.
- **D1.6 (advisor): the proxies are checked against the real ETFs with pass marks fixed in advance**: monthly
  correlation ≥ 0.98, tracking error ≤ 1.5%/yr (stocks) and ≤ 3%/yr (bonds).
- **O1.1 (owner): statistics stay public, curves stay on your machine.** Tables of numbers (every reconciliation row,
  the proxy checks) remain in git. Any chart that traces a return or wealth path built from Yahoo, Cboe or Ken French
  data is no longer tracked; `make report-site-local` draws those charts into ignored folders, and a test fails if the
  folders ever stop being ignored. You will scrub the old copies from history with the price file before pushing.

## R2
- **O2.1 (owner): quantkit moves to v0.19.2** for its new headline-chart function; R1's headline chart is redrawn with it.
  Nothing else in quantkit changed for this repo. Curve charts still live only on your machine.
