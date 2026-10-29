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
