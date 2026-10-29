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
