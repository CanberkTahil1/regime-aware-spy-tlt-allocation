# Interview questions (one block per phase)

## R0
1. **Why reproduce the old strategy exactly before improving it?** So every later difference has a known cause. If v1
   didn't reproduce, I couldn't tell whether a change in results came from the new data, the new accounting or a bug.
   Matching to 1e-15 means the baseline row in the ladder is really v1.
2. **Why did you stop using Yahoo and VIX data?** Their terms bar automated collection (Yahoo) and storing or
   redistributing (Cboe), and v1 had committed both to a public repository. v2 uses public-domain Fed data, a disclosed
   Ken French proxy kept out of git, and realised volatility instead of VIX.
3. **How do you make sure a shared library doesn't change your results?** quantkit is installed from a git tag, not
   editable, and every run hashes each quantkit file it loaded against a pinned list. If a loaded file differs, the run
   fails.

## R1
1. **How did you make sure the old result and the new one are comparable?** I reproduced v1 exactly first, then changed
   one thing per row in an order fixed before seeing any numbers. Each row's difference is then caused by that one
   change, and the caption says the attribution depends on the order.
2. **One of your pre-registered expectations failed. What did you do?** "Trading a day later hurts a fast signal" failed
   in 2005–14: it helped. I logged the failure before looking for a cause, found no bug, and showed that one-day timing
   has no stable sign for this signal. I left the expectation failed and changed nothing.
3. **Why rebuild TLT from the Fed curve instead of using the ETF?** The ETF price data couldn't be stored under its
   terms. A 25-year constant-maturity par bond off the Fed's public-domain curve tracks TLT at 0.994 monthly correlation
   and 1.5%/yr tracking error over 2005–25, and it gives history back to 1986.

## R2 — The core mix

1. **Your stock-bond mix looks far better than v1. Why didn't it get promoted?** The walk is a fixed sequence chosen
   before results: each rung must beat the one before it, and it stops at the first failure. Vol-targeted SPY didn't
   beat v1 by +0.05 with significance, so the later rungs were never tested. The raw gap (excess Sharpe 0.83 vs 0.51)
   has no test behind it, and 1990–2019 was a bond bull market. Promoting anyway would choose the order after seeing
   the results.
2. **How do you compare an 8%-vol portfolio with SPY at 17%?** Against SPY + T-bills scaled to the portfolio's own
   trailing 63-day volatility, using only data available the day before. The exact full-sample match is shown only
   for reference.
3. **Why does the vol target barely matter here?** The inverse-vol mix already runs below 10% vol on 84% of days, so
   the 1.0× cap binds and the layer acts only in high-vol spells: +0.01 Sharpe and −7% CDaR at matched vol.

## R3 — The regime layer

1. **Your strategy is named after the correlation regime. Does it work?** In 1990–2019 it did what it was built for
   once: in 1994, when bonds and stocks fell together, it saved 5.9 pp at matched risk. The rest of the time it sat in
   bills through long positive-correlation spells while bonds rallied, costing −0.08 Sharpe [−0.23, +0.07]. The 2022
   case for it is in the test window, which isn't opened until R5.
2. **Trend following cut your GFC loss by 12 points. Why not keep it?** The same rule lost in 1994, 2011, 2015–16 and
   Q4 2018 by selling dips that recovered or dropping the bond hedge just before it paid. Net −0.17 Sharpe over 30
   years, and no smaller drawdowns at equal risk. Judging a crash rule by its best crisis is selection.
3. **How do you know a regime gate isn't just "less risk"?** Compare at matched volatility, and against the same gate
   with its timing shuffled in 12-month blocks. These gates failed both: no better than the parent at equal risk, and
   inside the distribution of their shuffled copies.

## R4 — Robustness and costs

1. **You added three more models in R4. How do you stop that from being a fishing trip?** Their definitions were
   written into the pre-registration and hashed before any number existed. They are zoo rows, so they can never be
   promoted, and they count toward the multiple-testing total. None beat the core mix: the v1 spread overlay came in at
   −0.07 Sharpe, the Bollinger overlay −0.04 and the GBM sizing −0.003, all inside their intervals.
2. **Your DSR says 0.99 for the core mix. Is the deflation meaningful?** Barely. 787 trial series cluster into about 3
   independent bets, because everything is a long-only SPY/TLT mix, so the bar is low (SR0 0.19). At the raw register
   count (748), SR0 is 0.37. The core mix still clears it (DSR 0.99), but v1 falls to 0.78 and SPY to 0.73. I report
   both, because the true effective count is in between.
3. **Would more data settle whether inverse-vol beats 60/40?** Not soon. If the measured +0.13 Sharpe were the truth,
   with ρ 0.89 between the two daily return series, 80% power at α 0.05 needs about 87 years of daily data. Thirty
   years is a third of that, and the vol-target layer's +0.01 would need about 900.

## R5 — Freeze, test, write-up

1. **Your test window says nothing worked. Was the strategy wrong or the window unlucky?** Both readings fit, and 6.75
   years can't separate them. Even the best development layer needs about 30 years for 80% power. What the test does
   show is that the edge depended on long Treasuries hedging stocks. 2022 broke that, and the rule meant to detect the
   break (a 126-day correlation) first fired at the end of August 2022, after most of the year's bond loss.
2. **How do you know you didn't peek at the test before freezing?** Every rule and comparison was hashed into the
   ledger first. The lock hashes 39 code and spec files plus the data. The runner writes a "started" record before
   computing anything and refuses a second run. The window is still labelled "seen by owner in v1", because the owner
   saw 2020–25 in the old project.
3. **The trend layer did well in 2022. Why not promote it?** Because promotion happens only in development, and there
   trend lowered Sharpe by 0.17 against its parent. On the test its 2022 gain is inside the range of random timing
   shuffles. One good crisis out of two, in a window chosen after the fact, is an anecdote.
