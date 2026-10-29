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
- **D2.1 (advisor): one 5-point no-trade band, checked against where the weights have actually drifted**, trading only
  to the edge of the band. 60/40, inverse-vol and the vol-targeted mixes use it; the v1-style vol-targeted SPY does not
  (v1 never had one).
- **D2.2 (advisor): the vol target's forecasting model is picked once a year** from five candidates by how well each
  forecast tomorrow's variance so far; among the ones statistically tied with the best, the simplest wins.
- **D2.3 (advisor): L2 is exactly v1's own volatility scaling on SPY alone** (15% target, 20 days, up to 2×), now paying
  for leverage and trades — the thing that was really driving v1.
- **D2.4 (advisor): a rung moves up only if it clears all four parts of the charter's rule**: +0.05 Sharpe or 15% less
  deep drawdown at equal risk, a one-sided significance test, no loss with doubled costs, dearer financing or any one
  crisis removed, and a place in the 90% best-model set. No tolerances beyond what the charter says.
- **D2.5 (advisor): the official book rebalances on the first trading day of each month**; all 21 possible rebalance
  days are shown beside it to measure calendar luck, and none is ever picked.
- **D2.6 (advisor): with two assets, equal risk contribution is the same as inverse volatility** — proved by a test and
  reported, not run twice.
- **D2.7 (advisor): inverse-vol weights use plain 63-day volatility**, as pre-registered.
- **D2.8 (advisor): each rung's benchmark is SPY + T-bills scaled to the rung's trailing 63-day risk**, using only
  yesterday's data; the exact full-sample match is shown for reference.
- **O2.2 (yours): short chart labels stay, with a key underneath**: SPY, v1, VT SPY, 60/40, InvVol, InvVol+VT,
  SPY+bills. Room for longer labels is noted as an optional request for quantkit's next version (Q15); this repo does
  not change quantkit.
- **O2.3 (yours): each rung is now judged against the rung it actually builds on.** The charter says every rung adds
  one layer, but the original walk put 60/40 after vol-targeted SPY, which it does not build on (the order came from
  your plan listing v1 first). The charter was amended first, openly labelled as a change made after seeing results.
  v1 becomes a yardstick every rung is compared with, not a step. Two chains: SPY → vol-targeted SPY, and SPY → 60/40 →
  inverse-vol → + vol target (→ R3's layers). The original walk's result stays on record next to the new one, and the
  new walk counts as an extra trial when the deflated Sharpe is computed.
- **O2.4 (yours): a known flaw in the crisis check is written down, with a fairer side-view.** Comparing Sharpe ratios
  inside a crisis can penalise the calmer portfolio when both lose money. A descriptive row now shows each crisis's
  return with the parent scaled to the same risk; it cannot change any verdict. For R3, the new layers are judged in the
  ablation table (each vs its parent, vs 60/40 and vs v1, with intervals), not by the walk, whose verdict stands.
- **D3.1 (advisor): the correlation layer does one thing**: when the trailing 6-month stock-bond correlation is above
  zero at a month-end, the bond slice goes to T-bills next day; stocks are not topped up. A slice told to go to zero
  now leaves completely (before, the 5-point trading band would have left a small stub).
- **D3.2 (advisor): the trend layer is Faber's 10-month moving-average rule from quantkit**, on the same total-return
  series we trade; a slice below its trend goes to T-bills. A "trend only" row shows its effect without the
  correlation layer.
- **D3.3 (advisor): the crash rule is quantkit's off-the-shelf drawdown brake** (cut exposure from a 10% loss, down to
  a quarter at 25%), tested against the same book without it and against a copy with the brake's timing shuffled.
- **D3.4 (advisor): each on/off rule is tested against a fake version with its timing scrambled** in one-year blocks,
  so it keeps how often and how long it is on; a rule only counts as working if it beats the real parent and the fake
  does not. We also show where it ranks among 100 fakes.
- **D3.5 (advisor): every layer is compared at the same risk** with its parent, 60/40, v1 and SPY + T-bills, with 95%
  intervals on both the Sharpe difference and the drawdown ratio (quantkit's paired bootstrap).
- **D3.6 (advisor): the "zoo" rows quantkit already defines are built now** (two market-state switches, a
  minimum-drawdown mix, and max-diversification, which equals inverse-vol for two assets); v1's spread/Bollinger
  overlays and the machine-learning row need definitions of their own and move to R4.
- **O3.1 (yours, resolved: move to R4 with a condition): three "zoo" rows were not built in R3** — v1's spread and Bollinger signals as overlays on
  the core mix, and the machine-learning risk row. The advisor moved them to R4 because each needs a definition nobody
  has written yet; the reviewer says cutting your phase list is your call. Options: accept R4, build them in an R3
  amendment before the tag, or drop them from the charter.
  **Your answer:** move them to R4. Their definitions are written into the pre-registration and hashed at R4 start,
  before any number. They are exploratory, cannot change any verdict, and count toward the multiple-testing total.

## R4 (advisor decisions, before any R4 number)
- **D4.1 (advisor): v1's two signals are used as "go to cash for a day" switches on the core mix.** When v1's spread
  or Bollinger signal fires, the sleeve it would sell goes to T-bills; on every other day the book is the core mix
  unchanged. v1 used each signal only in one market state, judged by VIX; we use them every day, and we say so.
- **D4.2 (advisor): the machine-learning row predicts next month's volatility with a gradient-boosted model, but may
  only move half-way from our existing forecast** (that is the "50% haircut"). It is refit once a year on data whose
  answers were already known, with no tuning. The unshrunk version is shown beside it.
- **D4.3 (advisor): we install the machine-learning add-on the pinned quantkit version already declares.** It is the
  same version and the same checked code; the libraries are standard open-source ones, and no data terms change.
- **D4.4 (advisor): nothing was promoted, so every rung gets the same stress tests,** to show where each loses: costs,
  financing, a single crisis, a decade. Nothing here can reopen a verdict.
- **D4.5 (advisor): bond maturity, trading band and rebalancing calendar are each changed one at a time** against the
  registered choice. The 10-, 20- and 30-year bond series were never checked against a real ETF, and the labels say so.
- **D4.6 (advisor): the multiple-testing count includes every registered trial,** including v1's 648-setting search
  re-run on the new data. Near-copies are grouped so they don't inflate the count.
- **D4.7 (advisor): the "probability of backtest overfitting" is computed over the zoo of core-mix variants,** with
  exact copies removed, splitting history into 16 blocks as in the original paper.
